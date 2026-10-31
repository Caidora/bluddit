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
python3 - "$domain" <<'PY'
import json
import socket
import ssl
import sys
import urllib.error
import urllib.request

domain = sys.argv[1]
for label, url, kind in [
    ("Internal web", "http://127.0.0.1:18080/", "web"),
    ("Internal API", "http://127.0.0.1:18080/api/health", "api"),
    ("Public HTTPS web", f"https://{domain}/", "web"),
    ("Public HTTPS API", f"https://{domain}/api/health", "api"),
]:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Bluddit-Healthcheck/1.0"})
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read()
            valid = json.loads(body) == {"status": "ok"} if kind == "api" else b"Shared progress." in body
            print(f"{label}: HTTP {response.status}; expected response {'present' if valid else 'missing'}")
    except urllib.error.HTTPError as error:
        print(f"{label}: HTTP {error.code}")
    except urllib.error.URLError as error:
        reason = error.reason
        if isinstance(reason, ssl.SSLCertVerificationError):
            category = "certificate verification failed"
        elif isinstance(reason, socket.gaierror):
            category = "DNS resolution failed"
        elif isinstance(reason, (TimeoutError, socket.timeout)):
            category = "connection timed out"
        elif isinstance(reason, ConnectionRefusedError):
            category = "connection refused"
        else:
            category = "connection failed"
        print(f"{label}: {category}")
    except (OSError, ValueError):
        print(f"{label}: check failed")
PY
