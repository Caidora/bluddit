#!/usr/bin/env bash
set -euo pipefail
action=${1:?Production action is required}
target=${2:-}
case "$action" in deploy|rollback|verify|backup|restart) ;; *) echo 'Unsupported production action'; exit 1;; esac
for name in GH_TOKEN GH_ACTOR; do
  [[ -n ${!name:-} ]] || { echo "::error::Missing $name"; exit 1; }
done
if [[ $action == deploy ]]; then
  for name in POSTGRES_PASSWORD BATTLE_NET_CLIENT_ID BATTLE_NET_CLIENT_SECRET BATTLE_NET_TOKEN_ENCRYPTION_KEY WEB_IMAGE API_IMAGE DB_IMAGE NGINX_IMAGE RELEASE_ID TLS_EMAIL; do
    [[ -n ${!name:-} ]] || { echo "::error::Missing deployment configuration: $name"; exit 1; }
  done
fi
umask 077
stage=$(mktemp -d)
archive="$RUNNER_TEMP/bluddit-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}.tgz"
trap 'rm -rf "$stage"; rm -f "$archive"' EXIT
cp -R infra "$stage/infra"
STAGE="$stage" python3 - <<'PY'
import json
import os
from pathlib import Path

stage = Path(os.environ["STAGE"])
for name, variable in [("registry_token", "GH_TOKEN"), ("registry_actor", "GH_ACTOR"), ("postgres_password", "POSTGRES_PASSWORD"), ("battlenet_client_id", "BATTLE_NET_CLIENT_ID"), ("battlenet_client_secret", "BATTLE_NET_CLIENT_SECRET"), ("battlenet_token_encryption_key", "BATTLE_NET_TOKEN_ENCRYPTION_KEY")]:
    (stage / name).write_text(os.environ.get(variable, ""))
if os.environ.get("RELEASE_ID"):
    manifest = {key: os.environ[key] for key in ("WEB_IMAGE", "API_IMAGE", "DB_IMAGE", "NGINX_IMAGE")}
    manifest["release_id"] = os.environ["RELEASE_ID"]
    (stage / "manifest.json").write_text(json.dumps(manifest))
PY
tar -czf "$archive" -C "$stage" .
# Transfer into a restrictive, unpredictable directory instead of an open shared /tmp filename.
remote_work=$(ssh -F "$RUNNER_TEMP/ssh/config" production 'umask 077; mktemp -d /tmp/bluddit.XXXXXXXXXX')
[[ $remote_work =~ ^/tmp/bluddit\.[a-zA-Z0-9]+$ ]] || { echo 'Invalid remote staging directory'; exit 1; }
trap 'ssh -F "$RUNNER_TEMP/ssh/config" production "rm -rf -- $remote_work" >/dev/null 2>&1 || true; rm -rf "$stage"; rm -f "$archive"' EXIT
scp -F "$RUNNER_TEMP/ssh/config" "$archive" "production:$remote_work/payload.tgz"
printf -v remote 'bash -s -- %q %q %q %q %q %q' "$remote_work" "$action" "$DEPLOY_PATH" "$APP_DOMAIN" "${TLS_EMAIL:-}" "$target"
ssh -F "$RUNNER_TEMP/ssh/config" production "$remote" <<'REMOTE'
set -euo pipefail
work=$1
action=$2
root=$3
domain=$4
email=$5
target=$6
tar -xzf "$work/payload.tgz" -C "$work"
if [[ $(id -u) == 0 ]]; then
  python3 "$work/infra/deploy.py" "$action" "$root" "$work" "$domain" "$email" "$target"
else
  sudo -n python3 "$work/infra/deploy.py" "$action" "$root" "$work" "$domain" "$email" "$target"
fi
REMOTE
