#!/usr/bin/env bash
set -euo pipefail
for name in DEPLOY_HOST DEPLOY_USER DEPLOY_PORT DEPLOY_PATH APP_DOMAIN SSH_KEY SSH_KNOWN_HOSTS; do
  if [[ -z ${!name:-} ]]; then
    echo "::error::Missing repository secret: $name"
    exit 1
  fi
done
[[ $DEPLOY_HOST =~ ^[a-zA-Z0-9.:-]+$ ]] || { echo 'Invalid DEPLOY_HOST'; exit 1; }
[[ $DEPLOY_USER =~ ^[a-zA-Z_][a-zA-Z0-9_-]*$ ]] || { echo 'Invalid DEPLOY_USER'; exit 1; }
[[ $DEPLOY_PORT =~ ^[0-9]+$ ]] && (( DEPLOY_PORT > 0 && DEPLOY_PORT < 65536 )) || { echo 'Invalid DEPLOY_PORT'; exit 1; }
[[ $DEPLOY_PATH =~ ^/[a-zA-Z0-9_./-]+$ && $DEPLOY_PATH != / && $DEPLOY_PATH != *..* ]] || { echo 'Invalid DEPLOY_PATH'; exit 1; }
[[ $APP_DOMAIN =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]] || { echo 'Invalid APP_DOMAIN: use a hostname without https:// or a path'; exit 1; }
umask 077
mkdir -p "$RUNNER_TEMP/ssh"
printf '%s\n' "$SSH_KEY" > "$RUNNER_TEMP/ssh/key"
printf '%s\n' "$SSH_KNOWN_HOSTS" > "$RUNNER_TEMP/ssh/known_hosts"
cat > "$RUNNER_TEMP/ssh/config" <<EOF
Host production
  HostName $DEPLOY_HOST
  User $DEPLOY_USER
  Port $DEPLOY_PORT
  IdentityFile $RUNNER_TEMP/ssh/key
  UserKnownHostsFile $RUNNER_TEMP/ssh/known_hosts
  StrictHostKeyChecking yes
  IdentitiesOnly yes
  BatchMode yes
  ConnectTimeout 15
EOF
