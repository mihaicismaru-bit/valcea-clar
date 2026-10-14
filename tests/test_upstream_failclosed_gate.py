"""Fail-closed upstream regression on actual public-sync modules (mocked HTTP)."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from scripts import sync_civora as sync

class MissingUpstreamRegression(unittest.TestCase):
    def test_upstream_404_preserves_projection_and_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            articles = root / "articles.json"
            receipt = root / "receipt.json"
            media = root / "media.json"
            for path in (articles, receipt, media):
                path.write_text(json.dumps({"sentinel": path.name}))
            before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (articles, receipt, media)}
            error = HTTPError("https://example.invalid/feed", 404, "Not Found", {}, None)
            with patch.object(sync, "ARTICLES_PATH", articles), patch.object(sync, "STATE_PATH", receipt), patch.object(sync, "MEDIA_PATH", media), patch.object(sync, "SYNC_DIR", root), patch.object(sync, "urlopen", side_effect=error):
                with self.assertRaises(HTTPError):
                    sync.main()
            after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (articles, receipt, media)}
            self.assertEqual(before, after)
