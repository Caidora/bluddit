"""Production operations. Executed only by GitHub Actions over verified SSH.

No command output is forwarded: public workflow logs contain status messages only.
Release metadata contains no credentials; database credentials live in shared/.
"""

import contextlib
import fcntl
import hashlib
import json
import os
import platform
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid

if __package__:
    from .smoke import check as smoke_check
else:
    from smoke import check as smoke_check


class DeploymentError(RuntimeError):
    pass


def run(args, *, input=None, stdout=subprocess.PIPE, env=None):
    result = subprocess.run(args, input=input, stdout=stdout, stderr=subprocess.PIPE, env=env)
    if result.returncode:
        # Arguments and output can contain host metadata or credentials.
        raise DeploymentError(f"{Path(args[0]).name} failed (exit {result.returncode}); inspect private server logs")
    return result.stdout or b""


def write_private(path: Path, value: str):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value)
    temporary.chmod(0o600)
    temporary.replace(path)


class Deployment:
    def __init__(self, root: Path, payload: Path, domain: str, email: str):
        if not re.fullmatch(r"/[A-Za-z0-9_./-]+", str(root)) or ".." in root.parts or str(root) == "/":
            raise DeploymentError("DEPLOY_PATH must be an absolute application directory")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]+\.[A-Za-z]{2,}", domain):
            raise DeploymentError("APP_DOMAIN must be a hostname")
        self.root, self.payload, self.domain, self.email = root.resolve(), payload.resolve(), domain.lower(), email
        self.shared = self.root / "shared"
        self.releases = self.root / "releases"
        self.environment = os.environ.copy()
        self.environment["DOCKER_CONFIG"] = str(payload / "docker-auth")

    def compose(self, release, *args, **kwargs):
        return run(["docker", "compose", "--project-name", "bluddit", "--env-file", str(release / "release.env"),
                    "-f", str(release / "compose.production.yaml"), *args], env=self.environment, **kwargs)

    @contextlib.contextmanager
    def locked(self):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (self.root / "deploy.lock").open("w") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise DeploymentError("Another production operation holds the deployment lock") from None
            self.shared.mkdir(exist_ok=True, mode=0o700)
            self.releases.mkdir(exist_ok=True, mode=0o700)
            yield

    def prerequisites(self):
        # Install only missing prerequisites; never upgrade unrelated host packages.
        packages = []
        if not shutil.which("docker"):
            packages += ["docker.io"]
        if not shutil.which("nginx"):
            listeners = run(["ss", "-lntH"]).decode()
            if re.search(r":(?:80|443)\s", listeners):
                raise DeploymentError("Existing non-Nginx ingress detected; integration is required before deployment")
            packages += ["nginx"]
        if not shutil.which("certbot"):
            packages += ["certbot"]
        if packages:
            if not shutil.which("apt-get"):
                raise DeploymentError("Install Docker Compose, Nginx, and Certbot through the host's supported package manager")
            env = {**os.environ, "DEBIAN_FRONTEND": "noninteractive"}
            run(["apt-get", "update"], env=env)
            run(["apt-get", "install", "-y", *packages], env=env)
        run(["systemctl", "enable", "--now", "docker"])
        run(["docker", "info"])
        compose_check = subprocess.run(["docker", "compose", "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if compose_check.returncode:
            self.install_compose()
        run(["docker", "compose", "version"])
        run(["nginx", "-t"])

    @staticmethod
    def install_compose():
        # Official release checksums recorded from Docker's GitHub release API.
        checksums = {
            "x86_64": "47737f4236e6d3ccea7291995203f8f018058783b4c3a9469119811a0b5db8c0",
            "aarch64": "42cfa75f51ad0ccf290bad37899e0038a8c10a0069e85233ecc1d53e3ff1347d",
        }
        architecture = platform.machine()
        if architecture not in checksums:
            raise DeploymentError("Docker Compose bootstrap supports amd64/arm64 hosts")
        destination = Path("/usr/local/lib/docker/cli-plugins/docker-compose")
        if destination.exists():
            raise DeploymentError("Existing Docker Compose plugin is unusable; review before replacing it")
        url = f"https://github.com/docker/compose/releases/download/v5.6.1/docker-compose-linux-{architecture}"
        with urllib.request.urlopen(url, timeout=120) as response:
            binary = response.read()
        if hashlib.sha256(binary).hexdigest() != checksums[architecture]:
            raise DeploymentError("Docker Compose checksum verification failed")
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        destination.parent.chmod(0o755)
        destination.write_bytes(binary)
        destination.chmod(0o755)

    def authenticate(self):
        token = (self.payload / "registry_token").read_bytes()
        actor = (self.payload / "registry_actor").read_text().strip()
        run(["docker", "login", "ghcr.io", "--username", actor, "--password-stdin"],
            input=token, env=self.environment)

    def resolve_release(self, release_id):
        if not re.fullmatch(r"[a-f0-9]{40}-[0-9]+", release_id):
            raise DeploymentError("Release ID must be a recorded commit SHA followed by its workflow run ID")
        release = self.releases / release_id
        if not (release / "manifest.json").is_file():
            raise DeploymentError("Requested release is not present on this host")
        if not (release / "healthy.json").is_file():
            raise DeploymentError("Requested release has no successful health-verification record")
        return release

    def current(self):
        if not (self.root / "current").is_symlink():
            raise DeploymentError("No successful release is recorded")
        release = (self.root / "current").resolve()
        if release.parent != self.releases:
            raise DeploymentError("Invalid current release reference")
        return self.resolve_release(release.name)

    def activate(self, release):
        current = self.root / "current"
        if current.is_symlink() and current.resolve() != release.resolve():
            previous = self.root / "previous"
            previous.unlink(missing_ok=True)
            previous.symlink_to(current.resolve())
        temporary = self.root / "current.new"
        temporary.unlink(missing_ok=True)
        temporary.symlink_to(release)
        temporary.replace(current)

    def stage(self):
        manifest = json.loads((self.payload / "manifest.json").read_text())
        release_id = manifest["release_id"]
        if not re.fullmatch(r"[a-f0-9]{40}-[0-9]+", release_id):
            raise DeploymentError("Invalid release ID")
        for key in ("WEB_IMAGE", "API_IMAGE", "DB_IMAGE", "NGINX_IMAGE"):
            if not re.fullmatch(r"[a-z0-9./:_-]+@sha256:[a-f0-9]{64}", manifest[key]):
                raise DeploymentError(f"{key} must use an immutable image digest")
        manifest["APP_ROOT"] = str(self.root)
        password = (self.payload / "postgres_password").read_bytes()
        if not password or b"\n" in password or b"\r" in password:
            raise DeploymentError("POSTGRES_PASSWORD must be nonempty and contain no line breaks")
        password_path = self.shared / "postgres_password"
        if password_path.exists():
            if password_path.read_bytes() != password:
                raise DeploymentError("POSTGRES_PASSWORD differs from the initialized database; explicit rotation is required")
        else:
            # Refuse to silently adopt a database whose credentials/ownership are unknown.
            containers = run(["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=bluddit"])
            if containers.strip():
                raise DeploymentError("Unmanaged Bluddit Compose project exists; review ownership before adoption")
            existing = subprocess.run(["docker", "volume", "inspect", "bluddit_postgres_data"],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if existing.returncode == 0:
                raise DeploymentError("Unmanaged database volume exists; review ownership before adoption")
            password_path.write_bytes(password)
            password_path.chmod(0o600)
        # File-backed Compose secrets retain host ownership: the API runs as UID 10001.
        api_password = self.shared / "api_postgres_password"
        write_private(api_password, password.decode())
        os.chown(api_password, 10001, 10001)
        api_password.chmod(0o400)
        run(["docker", "volume", "create", "bluddit_postgres_data"])
        release = self.releases / release_id
        if release.exists():
            recorded = json.loads((release / "manifest.json").read_text())
            if any(recorded[key] != manifest[key] for key in ("WEB_IMAGE", "API_IMAGE", "DB_IMAGE", "NGINX_IMAGE")):
                raise DeploymentError("Release ID already exists with different image digests")
            return release
        release.mkdir(mode=0o700)
        shutil.copy2(self.payload / "infra/compose.production.yaml", release)
        shutil.copytree(self.payload / "infra/nginx", release / "nginx")
        shutil.copy2(self.payload / "infra/deploy.py", release / "deploy.py")
        shutil.copy2(self.payload / "infra/smoke.py", release / "smoke.py")
        write_private(release / "manifest.json", json.dumps(manifest, indent=2) + "\n")
        write_private(release / "release.env", "".join(f"{key}={manifest[key]}\n" for key in
                      ("WEB_IMAGE", "API_IMAGE", "DB_IMAGE", "NGINX_IMAGE", "APP_ROOT"))
                      + f"AUTH_ALLOWED_ORIGINS=https://{self.domain}\n")
        return release

    def configure_ingress(self):
        config = Path("/etc/nginx/conf.d/bluddit.conf")
        marker = "# Managed by Bluddit CI/CD\n"
        if config.exists() and not config.read_text().startswith(marker):
            raise DeploymentError("Existing unmanaged Bluddit ingress file; refusing to overwrite")
        current_config = run(["nginx", "-T"]).decode()
        # A different vhost owning this exact hostname must be integrated explicitly.
        for block in current_config.split("# configuration file "):
            if block.startswith(str(config) + ":"):
                continue
            if any(self.domain in names.split() for names in re.findall(r"server_name\s+([^;]+);", block)):
                raise DeploymentError("Application domain already has an unmanaged Nginx virtual host; integration required")
        cert_root = Path("/etc/letsencrypt/live") / self.domain
        # Nginx workers need traversal access to the ACME directory, not application secrets.
        webroot = Path("/var/lib/bluddit-acme")
        webroot.mkdir(exist_ok=True, mode=0o755)
        webroot.chmod(0o755)
        for directory in (webroot / ".well-known", webroot / ".well-known/acme-challenge"):
            directory.mkdir(exist_ok=True, mode=0o755)
            directory.chmod(0o755)
        challenge = f"location /.well-known/acme-challenge/ {{ root {webroot}; }}"
        common = """location / {
  proxy_pass http://127.0.0.1:18080;
  proxy_set_header Host $host;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;
  proxy_http_version 1.1;
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";
}"""
        http = f"server {{ listen 80; listen [::]:80; server_name {self.domain}; {challenge} location / {{ return 301 https://$host$request_uri; }} }}\n"
        if not (cert_root / "fullchain.pem").is_file():
            if not self.email or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", self.email):
                raise DeploymentError("TLS_EMAIL must be configured for initial HTTPS certificate issuance")
            initial = marker + f"server {{ listen 80; listen [::]:80; server_name {self.domain}; {challenge} location / {{ return 503; }} }}\n"
            self.install_nginx(config, initial)
            run(["certbot", "certonly", "--webroot", "--webroot-path", str(webroot), "--domain", self.domain,
                 "--email", self.email, "--agree-tos", "--non-interactive", "--keep-until-expiring"])
        https = f"""server {{
listen 443 ssl;
listen [::]:443 ssl;
server_name {self.domain};
ssl_certificate {cert_root}/fullchain.pem;
ssl_certificate_key {cert_root}/privkey.pem;
ssl_protocols TLSv1.2 TLSv1.3;
server_tokens off;
{common}
}}
"""
        self.install_nginx(config, marker + http + https)
        hook = Path("/etc/letsencrypt/renewal-hooks/deploy/bluddit-nginx")
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text("#!/bin/sh\nnginx -t && systemctl reload nginx\n")
        hook.chmod(0o755)
        run(["systemctl", "enable", "--now", "certbot.timer"])

    @staticmethod
    def install_nginx(config, content):
        before = config.read_bytes() if config.exists() else None
        config.write_text(content)
        try:
            run(["nginx", "-t"])
            run(["systemctl", "enable", "--now", "nginx"])
            run(["systemctl", "reload", "nginx"])
        except DeploymentError:
            if before is None:
                config.unlink(missing_ok=True)
            else:
                config.write_bytes(before)
            raise

    def healthy(self, release):
        readiness = "migrate:" in (release / "compose.production.yaml").read_text()
        for attempt in range(12):
            try:
                for base in ("http://127.0.0.1:18080", f"https://{self.domain}"):
                    smoke_check(base, readiness=readiness)
                print("Internal and public HTTPS checks passed", flush=True)
                return
            except (OSError, ValueError, AssertionError):
                if attempt == 11:
                    raise DeploymentError("Application health checks failed; previous release remains recorded for workflow rollback") from None
                time.sleep(5)

    def migrate(self, release):
        # This service is profiled out of ordinary up/restart/rollback operations.
        self.compose(release, "up", "-d", "--wait", "--wait-timeout", "180", "db")
        status = json.loads(self.compose(release, "run", "--rm", "--no-deps", "-T", "migrate",
                           "python", "-m", "bluddit_api.migrate", "status"))
        if status["pending"]:
            # Includes databases predating the migration ledger. Backup must succeed first.
            self.backup(release)
        self.compose(release, "run", "--rm", "--no-deps", "-T", "migrate")

    def rollout(self, release, *, migrate=False):
        self.compose(release, "config", "--quiet")
        self.compose(release, "pull")
        if migrate:
            self.migrate(release)
        self.compose(release, "up", "-d", "--wait", "--wait-timeout", "180")
        # Refresh upstream DNS after web/API container replacement.
        self.compose(release, "up", "-d", "--force-recreate", "--no-deps", "--wait", "--wait-timeout", "120", "nginx")
        self.healthy(release)
        write_private(release / "healthy.json", json.dumps({"verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}) + "\n")
        self.activate(release)
        print(f"Healthy release: {release.name}", flush=True)

    def sql(self, release, statement):
        return self.compose(release, "exec", "-T", "db", "psql", "-U", "bluddit", "-d", "bluddit",
                            "-v", "ON_ERROR_STOP=1", "-Atc", statement).decode().strip()

    def verify_persistence(self, release):
        nonce = uuid.uuid4().hex
        table = f"foundation_probe_{nonce}"
        self.sql(release, f"CREATE TABLE {table} (value text); INSERT INTO {table} VALUES ('{nonce}');")
        try:
            self.compose(release, "restart", "db", "api", "web", "nginx")
            self.compose(release, "up", "-d", "--wait", "--wait-timeout", "180")
            if self.sql(release, f"SELECT value FROM {table}") != nonce:
                raise DeploymentError("Database persistence check failed")
            self.healthy(release)
        finally:
            self.sql(release, f"DROP TABLE IF EXISTS {table}")
        print("Container restart and database persistence checks passed", flush=True)

    def verify_network(self, release):
        for service in ("db", "api", "web"):
            container = self.compose(release, "ps", "-q", service).decode().strip()
            if not container:
                raise DeploymentError("A required private service is not running")
            inspection = json.loads(run(["docker", "inspect", container]))[0]
            if inspection["HostConfig"].get("PortBindings"):
                raise DeploymentError("A private application/database port is unexpectedly published")
        container = self.compose(release, "ps", "-q", "nginx").decode().strip()
        inspection = json.loads(run(["docker", "inspect", container]))[0]
        if inspection["HostConfig"].get("PortBindings") != {"80/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18080"}]}:
            raise DeploymentError("Application ingress must bind only to the configured loopback port")
        print("Private database/application network checks passed", flush=True)

    def backup(self, release):
        directory = self.root / "backups"
        directory.mkdir(exist_ok=True, mode=0o700)
        path = directory / f"bluddit-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{uuid.uuid4().hex[:8]}.dump"
        temporary = path.with_suffix(".partial")
        try:
            with temporary.open("wb") as output:
                self.compose(release, "exec", "-T", "db", "pg_dump", "-U", "bluddit", "-d", "bluddit", "-Fc", stdout=output)
            temporary.chmod(0o600)
            probe = "restore_probe_" + uuid.uuid4().hex
            self.sql(release, f"CREATE DATABASE {probe}")
            try:
                self.compose(release, "exec", "-T", "db", "pg_restore", "-U", "bluddit", "-d", probe,
                             "--exit-on-error", input=temporary.read_bytes())
            finally:
                self.sql(release, f"DROP DATABASE {probe}")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        print("Database backup created and restored successfully in a disposable database", flush=True)

    def execute(self, action, target=""):
        with self.locked():
            if action == "deploy":
                self.prerequisites()
                self.authenticate()
                release = self.stage()
                self.compose(release, "config", "--quiet")
                self.compose(release, "pull")
                self.configure_ingress()
                self.rollout(release, migrate=True)
            elif action == "rollback":
                release = self.resolve_release(target)
                self.authenticate()
                current = self.current()
                old = json.loads((release / "manifest.json").read_text())
                new = json.loads((current / "manifest.json").read_text())
                if old["DB_IMAGE"] != new["DB_IMAGE"]:
                    raise DeploymentError("Database image changes require explicit compatibility review; automatic rollback refused")
                self.rollout(release)
            elif action == "verify":
                self.verify_network(self.current())
                self.verify_persistence(self.current())
                self.backup(self.current())
            elif action == "backup":
                self.backup(self.current())
            elif action == "restart":
                release = self.current()
                self.compose(release, "restart")
                self.compose(release, "up", "-d", "--wait", "--wait-timeout", "180")
                self.healthy(release)
            else:
                raise DeploymentError("Unsupported production operation")


def main():
    os.umask(0o077)
    action, root, payload, domain, email, target = sys.argv[1:]
    deploy = Deployment(Path(root), Path(payload), domain, email)
    try:
        deploy.execute(action, target)
    finally:
        shutil.rmtree(Path(payload) / "docker-auth", ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except (DeploymentError, OSError, ValueError, KeyError) as error:
        # Never interpolate arbitrary subprocess errors or paths into public logs.
        message = str(error) if isinstance(error, DeploymentError) else type(error).__name__ + ": operation failed; inspect private server state"
        print(f"::error::{message}", file=sys.stderr)
        sys.exit(1)
