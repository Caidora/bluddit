#!/usr/bin/env bash
set -euo pipefail
app_path=$1
domain=$2
echo 'Reporting readiness only; host metadata and configuration contents are suppressed.'
if docker info >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo 'Docker and Compose: ready'
else
  echo 'Docker and Compose: setup required'
fi
if systemctl is-active --quiet nginx; then
  echo 'Ingress: existing host Nginx; integrate a dedicated virtual host'
elif ss -lntH | awk '{print $4}' | grep -Eq ':(80|443)$'; then
  echo 'Ingress: occupied; further integration required before deployment'
else
  echo 'Ingress: public HTTP/HTTPS ports available'
fi
if [[ -d $app_path && -w $app_path ]]; then
  echo 'Application directory: writable'
elif [[ ! -e $app_path ]]; then
  echo 'Application directory: creation required'
else
  echo 'Application directory: permission setup required'
fi
if getent ahostsv4 "$domain" >/dev/null; then
  echo 'Application DNS: resolves (target match still requires verification)'
else
  echo 'Application DNS: unresolved'
fi
if [[ $(id -u) == 0 ]] || sudo -n true 2>/dev/null; then
  echo 'Host setup permissions: available'
else
  echo 'Host setup permissions: limited; prerequisites must already exist'
fi
