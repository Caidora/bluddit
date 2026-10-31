"""Small public-contract smoke check shared by local development and CI/CD."""
import json
import sys
import urllib.request


def check(base):
    headers = {"User-Agent": "Bluddit-Healthcheck/1.0"}
    with urllib.request.urlopen(urllib.request.Request(base + "/", headers=headers), timeout=15) as response:
        assert response.status == 200
        assert b"Shared progress." in response.read(), "Skeleton page is missing"
    with urllib.request.urlopen(urllib.request.Request(base + "/api/health", headers=headers), timeout=15) as response:
        assert response.status == 200
        assert json.load(response) == {"status": "ok"}, "Unexpected health response"
    print("Web and API smoke checks passed")


if __name__ == "__main__":
    try:
        check(sys.argv[1].rstrip("/"))
    except Exception:
        # A secret hostname must not leak via exception URLs into public logs.
        print("Web/API smoke check failed; verify DNS, HTTPS, routing, and service health", file=sys.stderr)
        sys.exit(1)
