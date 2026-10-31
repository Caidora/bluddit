from email.message import Message
from io import BytesIO
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlsplit

from infra import smoke


class Response(BytesIO):
    status = 200

    def __init__(self, body, content_type="text/html"):
        super().__init__(body)
        self.headers = Message()
        self.headers["Content-Type"] = content_type


class SmokeTests(unittest.TestCase):
    def run_check(self, shell, *, nested=None):
        paths = []

        def urlopen(request, timeout):
            path = urlsplit(request.full_url).path
            paths.append(path)
            if path == "/assets/__missing_smoke__.js":
                error = HTTPError(request.full_url, 404, "Not found", {}, BytesIO())
                self.addCleanup(error.close)
                raise error
            if path == "/assets/app.js":
                return Response(b"console.log('app')", "text/javascript")
            if path.startswith("/api/"):
                return Response(b'{"status":"ok"}', "application/json")
            return Response(nested if nested is not None and path != "/" else shell)

        with patch.object(smoke.urllib.request, "urlopen", side_effect=urlopen):
            smoke.check("https://example.com")
        return paths

    def test_blank_spa_checks_assets_fallback_and_api(self):
        paths = self.run_check(
            b'<main data-bluddit-shell=""></main><script src="/assets/app.js"></script>'
        )
        self.assertEqual(
            set(paths),
            {
                "/",
                "/assets/app.js",
                "/__spa_smoke__/nested",
                "/assets/__missing_smoke__.js",
                "/api/health",
                "/api/ready",
            },
        )

    def test_previous_spa_release_remains_supported(self):
        self.run_check(
            b'<main>Loading Bluddit</main><script src="/assets/app.js"></script>'
        )

    def test_unrelated_html_is_rejected(self):
        with self.assertRaisesRegex(AssertionError, "Application shell is missing"):
            self.run_check(b'<main></main><script src="/assets/app.js"></script>')

    def test_broken_spa_fallback_is_rejected(self):
        with self.assertRaisesRegex(AssertionError, "did not fall back"):
            self.run_check(
                b'<main data-bluddit-shell></main><script src="/assets/app.js"></script>',
                nested=b"Wrong page",
            )
