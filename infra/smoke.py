"""Small public-contract smoke check shared by local development and CI/CD."""
import json
import re
import sys
import urllib.error
import urllib.request


def check(base):
    headers = {"User-Agent": "Bluddit-Healthcheck/1.0"}
    with urllib.request.urlopen(urllib.request.Request(base + "/", headers=headers), timeout=15) as response:
        assert response.status == 200
        shell = response.read()
        assert b"Loading Bluddit" in shell, "SPA loading shell is missing"
        assets = set(re.findall(rb'(?:src|href)="(/assets/[^"?]+)', shell))
        assert any(asset.endswith(b".js") for asset in assets), "SPA scripts are missing"
    for asset in assets:
        with urllib.request.urlopen(urllib.request.Request(base + asset.decode(), headers=headers), timeout=15) as response:
            assert response.status == 200
            assert response.headers.get_content_type() != "text/html", "Asset returned the SPA shell"
    with urllib.request.urlopen(urllib.request.Request(base + "/__spa_smoke__/nested", headers=headers), timeout=15) as response:
        assert response.status == 200
        assert response.read() == shell, "Frontend route did not fall back to the SPA shell"
    try:
        urllib.request.urlopen(urllib.request.Request(base + "/assets/__missing_smoke__.js", headers=headers), timeout=15)
    except urllib.error.HTTPError as error:
        assert error.code == 404, "Unexpected missing-asset status"
    else:
        raise AssertionError("Missing asset must return 404")
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
