import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from infra import deploy

MODULE = Path(__file__).resolve().parents[1] / "deploy.py"


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "app"
        self.payload = Path(self.temp.name) / "payload"
        self.payload.mkdir()
        self.operation = deploy.Deployment(
            self.root, self.payload, "example.com", "ops@example.com"
        )

    def test_lock_rejects_overlapping_operations(self):
        other = deploy.Deployment(
            self.root, self.payload, "example.com", "ops@example.com"
        )
        with self.operation.locked():
            with self.assertRaisesRegex(deploy.DeploymentError, "deployment lock"):
                with other.locked():
                    self.fail("Second operation acquired lock")

    def test_invalid_path_and_domain_rejected_before_mutation(self):
        for path, domain in [
            ("/", "example.com"),
            ("relative", "example.com"),
            ("/opt/../etc", "example.com"),
            ("/opt/bluddit", "https://example.com"),
        ]:
            with (
                self.subTest(path=path, domain=domain),
                self.assertRaises(deploy.DeploymentError),
            ):
                deploy.Deployment(Path(path), self.payload, domain, "")

    def test_pull_failure_does_not_start_services_or_advance_current(self):
        calls = []

        def compose(release, *args):
            calls.append(args)
            if args == ("pull",):
                raise deploy.DeploymentError("pull failed")

        with (
            patch.object(self.operation, "compose", side_effect=compose),
            patch.object(self.operation, "activate") as activate,
        ):
            with self.assertRaisesRegex(deploy.DeploymentError, "pull failed"):
                self.operation.rollout(self.root / "release")
        self.assertFalse(any(args[0] == "up" for args in calls))
        activate.assert_not_called()

    def test_unhealthy_release_does_not_advance_successful_reference(self):
        with (
            patch.object(self.operation, "compose"),
            patch.object(
                self.operation,
                "healthy",
                side_effect=deploy.DeploymentError("unhealthy"),
            ),
            patch.object(self.operation, "activate") as activate,
        ):
            with self.assertRaisesRegex(deploy.DeploymentError, "unhealthy"):
                self.operation.rollout(self.root / "release")
            activate.assert_not_called()

    def test_backup_or_migration_failure_prevents_application_rollout(self):
        for failure in ("backup", "migration"):
            with self.subTest(failure=failure):
                calls = []

                def compose(release, *args, **kwargs):
                    calls.append(args)
                    if args[-1] == "status":
                        return b'{"pending": ["0001_accounts_and_sessions.sql"]}'
                    if failure == "migration" and args == (
                        "run",
                        "--rm",
                        "--no-deps",
                        "-T",
                        "migrate",
                    ):
                        raise deploy.DeploymentError("migration failed")
                    return b""

                backup_error = (
                    deploy.DeploymentError("backup failed")
                    if failure == "backup"
                    else None
                )
                with (
                    patch.object(self.operation, "compose", side_effect=compose),
                    patch.object(self.operation, "backup", side_effect=backup_error),
                    patch.object(self.operation, "activate") as activate,
                ):
                    with self.assertRaises(deploy.DeploymentError):
                        self.operation.rollout(self.root / "release", migrate=True)
                    activate.assert_not_called()
                self.assertFalse(
                    any(args[0] == "up" and args[-1] != "db" for args in calls)
                )

    def test_previous_release_and_idempotent_activation(self):
        with self.operation.locked():
            first = self.operation.releases / "first"
            second = self.operation.releases / "second"
            first.mkdir()
            second.mkdir()
            self.operation.activate(first)
            self.operation.activate(second)
            self.operation.activate(second)
            self.assertEqual((self.root / "current").resolve(), second.resolve())
            self.assertEqual((self.root / "previous").resolve(), first.resolve())

    def test_rollback_refuses_different_database_image(self):
        self.root.mkdir()
        old, new = self.root / "old", self.root / "new"
        old.mkdir()
        new.mkdir()
        (old / "manifest.json").write_text(json.dumps({"DB_IMAGE": "old"}))
        (new / "manifest.json").write_text(json.dumps({"DB_IMAGE": "new"}))
        with (
            patch.object(self.operation, "authenticate"),
            patch.object(self.operation, "resolve_release", return_value=old),
            patch.object(self.operation, "current", return_value=new),
            patch.object(self.operation, "rollout") as rollout,
        ):
            with self.assertRaisesRegex(deploy.DeploymentError, "compatibility"):
                self.operation.execute("rollback", "target")
            rollout.assert_not_called()

    def test_rollback_cannot_traverse_release_directory(self):
        with self.assertRaisesRegex(deploy.DeploymentError, "Release ID"):
            self.operation.resolve_release("../../etc")

    def test_failed_release_cannot_be_selected_as_rollback_target(self):
        release_id = "b" * 40 + "-456"
        with self.operation.locked():
            release = self.operation.releases / release_id
            release.mkdir()
            (release / "manifest.json").write_text("{}")
            with self.assertRaisesRegex(
                deploy.DeploymentError, "no successful health-verification"
            ):
                self.operation.resolve_release(release_id)

    def test_command_failures_do_not_leak_output_or_arguments(self):
        result = subprocess.CompletedProcess([], 1, b"private-host", b"secret-password")
        with patch.object(subprocess, "run", return_value=result):
            with self.assertRaises(deploy.DeploymentError) as error:
                deploy.run(["docker", "secret-argument"])
        self.assertNotIn("secret", str(error.exception))
        self.assertNotIn("private-host", str(error.exception))

    def test_missing_ssh_configuration_names_missing_secret(self):
        script = MODULE.parent / "scripts/ssh-setup.sh"
        result = subprocess.run(
            ["bash", str(script)],
            env={"PATH": os.environ["PATH"]},
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing repository secret: DEPLOY_HOST", result.stdout)

    def prepare_stage(self):
        manifest = {
            key: "example/image@sha256:" + "a" * 64
            for key in ("WEB_IMAGE", "API_IMAGE", "DB_IMAGE", "NGINX_IMAGE")
        }
        manifest["release_id"] = "a" * 40 + "-123"
        (self.payload / "manifest.json").write_text(json.dumps(manifest))
        (self.payload / "postgres_password").write_text("test-password")
        for name, value in (
            ("battlenet_client_id", "synthetic-client"),
            ("battlenet_client_secret", "synthetic-secret"),
            (
                "battlenet_token_encryption_key",
                "eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHg=",
            ),
        ):
            (self.payload / name).write_text(value)
        return manifest

    def test_mutable_image_tags_are_rejected(self):
        manifest = self.prepare_stage()
        manifest["WEB_IMAGE"] = "example/image:latest"
        (self.payload / "manifest.json").write_text(json.dumps(manifest))
        with self.operation.locked(), patch.object(deploy, "run") as command:
            with self.assertRaisesRegex(
                deploy.DeploymentError, "immutable image digest"
            ):
                self.operation.stage()
            command.assert_not_called()

    def test_successful_stage_prepares_non_root_api_secret(self):
        manifest = self.prepare_stage()
        manifest["BLIZZARD_CLIENT_ID"] = "synthetic-client"
        (self.payload / "manifest.json").write_text(json.dumps(manifest))
        (self.payload / "blizzard_client_secret").write_text("synthetic-secret")
        for relative in (
            "compose.production.yaml",
            "deploy.py",
            "smoke.py",
            "nginx/application.conf",
        ):
            destination = self.payload / "infra" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((MODULE.parent / relative).read_bytes())
        with (
            self.operation.locked(),
            patch.object(deploy, "run"),
            patch.object(os, "chown") as chown,
        ):
            deploy.write_private(
                self.operation.shared / "postgres_password", "test-password"
            )
            release = self.operation.stage()
        api_password = self.operation.shared / "api_postgres_password"
        chown.assert_any_call(api_password, 10001, 10001)
        provider_secret = self.operation.shared / "blizzard_client_secret"
        chown.assert_any_call(provider_secret, 10001, 10001)
        self.assertEqual(provider_secret.read_text(), "synthetic-secret")
        self.assertEqual(provider_secret.stat().st_mode & 0o777, 0o400)
        self.assertEqual(chown.call_count, 5)
        for name in (
            "battlenet_client_id",
            "battlenet_client_secret",
            "battlenet_token_encryption_key",
        ):
            target = self.operation.shared / name
            self.assertEqual(target.read_text(), (self.payload / name).read_text())
            self.assertEqual(target.stat().st_mode & 0o777, 0o400)
        self.assertEqual(api_password.read_text(), "test-password")
        self.assertEqual(api_password.stat().st_mode & 0o777, 0o400)
        self.assertEqual(
            json.loads((release / "manifest.json").read_text())["release_id"],
            manifest["release_id"],
        )
        self.assertIn(
            "AUTH_ALLOWED_ORIGINS=https://example.com\n",
            (release / "release.env").read_text(),
        )
        self.assertIn(
            "BATTLE_NET_REDIRECT_URI=https://example.com/api/oauth-redirect\n",
            (release / "release.env").read_text(),
        )
        self.assertNotIn("synthetic-secret", (release / "release.env").read_text())
        self.assertIn(
            "BLIZZARD_CLIENT_ID=synthetic-client\n",
            (release / "release.env").read_text(),
        )
        self.assertNotIn("synthetic-secret", (release / "manifest.json").read_text())
        self.assertFalse((self.root / "current").exists())

    def test_battlenet_encryption_key_cannot_be_silently_rotated(self):
        self.prepare_stage()
        with (
            self.operation.locked(),
            patch.object(deploy, "run"),
            patch.object(os, "chown"),
        ):
            (self.operation.shared / "postgres_password").write_text("test-password")
            (self.operation.shared / "battlenet_token_encryption_key").write_text(
                "different-existing-key"
            )
            with self.assertRaisesRegex(deploy.DeploymentError, "explicit rotation"):
                self.operation.stage()
            self.assertEqual(
                (self.operation.shared / "battlenet_token_encryption_key").read_text(),
                "different-existing-key",
            )

    def test_database_password_cannot_be_silently_rotated(self):
        self.prepare_stage()
        with self.operation.locked(), patch.object(deploy, "run") as command:
            (self.operation.shared / "postgres_password").write_text(
                "existing-password"
            )
            with self.assertRaisesRegex(deploy.DeploymentError, "rotation"):
                self.operation.stage()
            self.assertEqual(
                (self.operation.shared / "postgres_password").read_text(),
                "existing-password",
            )
            command.assert_not_called()

    def test_unmanaged_database_volume_is_not_adopted(self):
        self.prepare_stage()
        with (
            self.operation.locked(),
            patch.object(deploy, "run", return_value=b""),
            patch.object(
                subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
            ),
        ):
            with self.assertRaisesRegex(
                deploy.DeploymentError, "Unmanaged database volume"
            ):
                self.operation.stage()
            self.assertFalse((self.operation.shared / "postgres_password").exists())

    def test_unmanaged_compose_project_is_not_replaced(self):
        self.prepare_stage()
        with (
            self.operation.locked(),
            patch.object(deploy, "run", return_value=b"existing-container"),
        ):
            with self.assertRaisesRegex(
                deploy.DeploymentError, "Unmanaged Bluddit Compose project"
            ):
                self.operation.stage()
            self.assertFalse((self.operation.shared / "postgres_password").exists())

    def test_verification_rejects_public_database_port(self):
        inspection = [
            {
                "HostConfig": {
                    "PortBindings": {
                        "5432/tcp": [{"HostIp": "0.0.0.0", "HostPort": "5432"}]
                    }
                }
            }
        ]
        with (
            patch.object(self.operation, "compose", return_value=b"db-id"),
            patch.object(deploy, "run", return_value=json.dumps(inspection).encode()),
        ):
            with self.assertRaisesRegex(
                deploy.DeploymentError, "unexpectedly published"
            ):
                self.operation.verify_network(self.root)

    def test_compose_download_checksum_failure_never_installs_binary(self):
        with (
            patch.object(deploy.platform, "machine", return_value="x86_64"),
            patch.object(Path, "exists", return_value=False),
            patch.object(deploy.urllib.request, "urlopen") as request,
            patch.object(Path, "write_bytes") as write,
        ):
            request.return_value.__enter__.return_value.read.return_value = (
                b"untrusted download"
            )
            with self.assertRaisesRegex(deploy.DeploymentError, "checksum"):
                self.operation.install_compose()
            write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
