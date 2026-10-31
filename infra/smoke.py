"""Small public-contract smoke check shared by local development and CI/CD."""

import json
import re
import sys
import urllib.error
import urllib.request


def check(base, *, readiness=True):
    headers = {"User-Agent": "Bluddit-Healthcheck/1.0"}
    with urllib.request.urlopen(
        urllib.request.Request(base + "/", headers=headers), timeout=15
    ) as response:
        assert response.status == 200
        shell = response.read()
        # Use a stable marker instead of visible copy. Keep the previous marker
        # for smoke checks when rolling back to an older SPA release.
        spa = b"data-bluddit-shell" in shell or b"Loading Bluddit" in shell
        assert spa or (not readiness and b"Shared progress." in shell), (
            "Application shell is missing"
        )
        assets = set(re.findall(rb'(?:src|href)="(/assets/[^"?]+)', shell))
        assert any(asset.endswith(b".js") for asset in assets), (
            "SPA scripts are missing"
        )
    for asset in assets:
        with urllib.request.urlopen(
            urllib.request.Request(base + asset.decode(), headers=headers), timeout=15
        ) as response:
            assert response.status == 200
            assert response.headers.get_content_type() != "text/html", (
                "Asset returned the SPA shell"
            )
    if spa:
        with urllib.request.urlopen(
            urllib.request.Request(base + "/__spa_smoke__/nested", headers=headers),
            timeout=15,
        ) as response:
            assert response.status == 200
            assert response.read() == shell, (
                "Frontend route did not fall back to the SPA shell"
            )
    try:
        urllib.request.urlopen(
            urllib.request.Request(
                base + "/assets/__missing_smoke__.js", headers=headers
            ),
            timeout=15,
        )
    except urllib.error.HTTPError as error:
        assert error.code == 404, "Unexpected missing-asset status"
    else:
        raise AssertionError("Missing asset must return 404")
    with urllib.request.urlopen(
        urllib.request.Request(base + "/api/health", headers=headers), timeout=15
    ) as response:
        assert response.status == 200
        assert json.load(response) == {"status": "ok"}, "Unexpected health response"
    if readiness:
        with urllib.request.urlopen(
            urllib.request.Request(base + "/api/ready", headers=headers), timeout=15
        ) as response:
            assert response.status == 200
            assert json.load(response) == {"status": "ok"}, "Database is not ready"
    print("Web and API smoke checks passed")


if __name__ == "__main__":
    try:
        check(sys.argv[1].rstrip("/"), readiness="--process-only" not in sys.argv[2:])
    except Exception:
        # A secret hostname must not leak via exception URLs into public logs.
        print(
            "Web/API smoke check failed; verify DNS, HTTPS, routing, and service health",
            file=sys.stderr,
        )
        sys.exit(1)
