#!/usr/bin/env python3
"""F0 S5 generated-link closure gate; never performs network calls or publishes.

This is a test-only proposal. Local file closure and independently supplied
HTTP receipts are distinct criteria. A local PASS is not public delivery.

Usage for an authorized, already-generated site:
  python tests/test_reboot_s5_route_closure.py --site-root /path/to/site --receipt /path/to/evidence.json
  python -m unittest discover -s tests -p 'test_reboot_s5_route_closure.py' -v
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlparse
from xml.etree import ElementTree

SITE_ORIGIN = "https://valceaclar.ro"
VENUE_PREFIX = "/unde-iesim/local/"
INDEX_ROUTE = "/unde-iesim/verificat/"


class RouteClosureError(ValueError):
    """A route cannot be declared complete or delivered."""


class VenueCardLinks(HTMLParser):
    """Extract actual rendered venue links, not hypothetical draft entries."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.venue_depths: list[int] = []
        self.links: list[tuple[str, str]] = []
        self.cards: list[str] = []
        self.current_card: str | None = None
        self.ids: set[str] = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "article":
            if self.current_card is not None:
                self.venue_depths.append(self.depth)
            if "data-s5-venue" in attrs:
                venue_id = attrs["data-s5-venue"]
                if not venue_id or venue_id in self.ids:
                    raise RouteClosureError("Duplicate/blank venue identity")
                self.ids.add(venue_id)
                if self.current_card is not None:
                    raise RouteClosureError("Nested venue cards are ambiguous")
                self.current_card = venue_id
                self.cards.append(venue_id)
                self.venue_depths.append(self.depth)
            self.depth += 1
        elif tag == "a" and self.current_card is not None:
            href = attrs.get("href", "")
            if href.startswith(VENUE_PREFIX) or "/unde-iesim/local/" in href:
                self.links.append((self.current_card, href))

    def handle_endtag(self, tag):
        if tag == "article":
            self.depth -= 1
            if self.venue_depths and self.depth == self.venue_depths[-1]:
                self.venue_depths.pop()
                self.current_card = None


def _sitemap_paths(xml_path: Path) -> set[str]:
    if not xml_path.is_file():
        raise RouteClosureError("SITEMAP_MISSING")
    try:
        root = ElementTree.fromstring(xml_path.read_bytes())
    except ElementTree.ParseError as exc:
        raise RouteClosureError("SITEMAP_INVALID") from exc
    paths = set()
    for el in root.iter():
        if el.tag.split("}")[-1] != "loc" or not el.text:
            continue
        parsed = urlparse(el.text.strip())
        if f"{parsed.scheme}://{parsed.netloc}" == SITE_ORIGIN:
            paths.add(parsed.path)
    return paths


def _resolved_html(root: Path, route: str) -> Path:
    parsed = urlparse(route)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or ".." in parsed.path.split("/"):
        raise RouteClosureError(f"UNSAFE_ROUTE: {route}")
    if not route.startswith(VENUE_PREFIX) or not route.endswith("/"):
        raise RouteClosureError(f"UNEXPECTED_ROUTE: {route}")
    return root / route.strip("/") / "index.html"


def inspect(site_root: Path, receipts: dict | None = None) -> dict:
    """Fail closed on bad local graph; do not assert delivery without receipts.

    Receipts must come from an *independent* HTTP readback, not a generated
    file or CI build claim. This function validates their supplied shape,
    status, route correspondence and (where supplied) body digest.
    """
    hub = site_root / INDEX_ROUTE.strip("/") / "index.html"
    if not hub.is_file():
        raise RouteClosureError("S5_HUB_NOT_GENERATED")
    parser = VenueCardLinks()
    parser.feed(hub.read_text(encoding="utf-8"))
    paths = _sitemap_paths(site_root / "sitemap.xml")
    if INDEX_ROUTE not in paths:
        raise RouteClosureError("S5_HUB_MISSING_FROM_SITEMAP")
    if len(parser.links) != len(parser.cards):
        raise RouteClosureError("CARD_LINK_COUNT_MISMATCH")
    targets = {}
    for venue_id, route in parser.links:
        if route in targets:
            raise RouteClosureError(f"DUPLICATE_TARGET: {route}")
        target = _resolved_html(site_root, route)
        if not target.is_file() or target.stat().st_size < 20:
            raise RouteClosureError(f"GENERATED_CHILD_MISSING: {route}")
        if route not in paths:
            raise RouteClosureError(f"SITEMAP_CHILD_MISSING: {route}")
        targets[route] = (venue_id, target)
    result = {"route_count": len(targets), "generated_route_closed": True,
              "http_certified": False, "child_routes": sorted(targets)}
    if receipts is None:
        return result
    if not isinstance(receipts, dict) or not isinstance(receipts.get("routes"), dict):
        raise RouteClosureError("INDEPENDENT_HTTP_RECEIPTS_MISSING")
    for route, (_, target) in targets.items():
        proof = receipts["routes"].get(route)
        if not isinstance(proof, dict) or proof.get("url") != SITE_ORIGIN + route:
            raise RouteClosureError(f"HTTP_RECEIPT_MISSING: {route}")
        if proof.get("status") != 200 or not proof.get("checked_at"):
            raise RouteClosureError(f"HTTP_READBACK_NOT_PASS: {route}")
        observed_digest = proof.get("local_generated_sha256")
        if observed_digest and observed_digest != sha256(target.read_bytes()).hexdigest():
            raise RouteClosureError(f"RECEIPT_SOURCE_HASH_MISMATCH: {route}")
    result["http_certified"] = True
    return result


class TestS5RouteClosure(unittest.TestCase):
    ROUTE = VENUE_PREFIX + "spartan-ramnicu-valcea/"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.hub = self.root / INDEX_ROUTE.strip("/") / "index.html"
        self.hub.parent.mkdir(parents=True)
        self._sitemap([INDEX_ROUTE, self.ROUTE])
        self._hub([("spartan-shopping-city-ramnicu-valcea", self.ROUTE)])

    def _hub(self, cards):
        html = ''.join(f'<article class="card" data-s5-venue="{i}"><h3><a href="{r}">Venue</a></h3></article>' for i, r in cards)
        self.hub.write_text('<html><body>' + html + '</body></html>', encoding="utf-8")

    def _sitemap(self, routes):
        xml = ('<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
               + ''.join(f'<url><loc>{SITE_ORIGIN + r}</loc></url>' for r in routes) + '</urlset>')
        (self.root / 'sitemap.xml').write_text(xml, encoding="utf-8")

    def _child(self, route=None):
        route = route or self.ROUTE
        target = self.root / route.strip("/") / 'index.html'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('<html><body>Checked source metadata, not a publication authorization.</body></html>', encoding='utf-8')
        return target

    def _receipt(self, route=None, status=200, sha=None):
        route = route or self.ROUTE
        entry = {'url': SITE_ORIGIN + route, 'status': status, 'checked_at': '2026-10-11T18:44:00Z'}
        if sha:
            entry['local_generated_sha256'] = sha
        return {'routes': {route: entry}}

    def test_historical_pattern_hub_links_but_no_children_fails(self):
        """S5's retired venue renderer made links but not child files."""
        with self.assertRaisesRegex(RouteClosureError, 'GENERATED_CHILD_MISSING'):
            inspect(self.root)

    def test_missing_sitemap_entry_fails(self):
        self._child()
        self._sitemap([INDEX_ROUTE])
        with self.assertRaisesRegex(RouteClosureError, 'SITEMAP_CHILD_MISSING'):
            inspect(self.root)

    def test_no_receipts_is_only_local_completion_not_delivery(self):
        self._child()
        result = inspect(self.root)
        self.assertTrue(result['generated_route_closed'])
        self.assertFalse(result['http_certified'])

    def test_missing_readback_is_fail_closed_when_certification_requested(self):
        self._child()
        with self.assertRaisesRegex(RouteClosureError, 'HTTP_RECEIPT_MISSING'):
            inspect(self.root, {'routes': {}})

    def test_non_200_readback_fails(self):
        self._child()
        with self.assertRaisesRegex(RouteClosureError, 'HTTP_READBACK_NOT_PASS'):
            inspect(self.root, self._receipt(status=404))

    def test_valid_evidence_shape_passes_but_is_fixture_only(self):
        child = self._child()
        digest = sha256(child.read_bytes()).hexdigest()
        self.assertTrue(inspect(self.root, self._receipt(sha=digest))['http_certified'])

    def test_duplicate_card_identity_fails(self):
        self._hub([('same', self.ROUTE), ('same', VENUE_PREFIX + 'two/')])
        with self.assertRaisesRegex(RouteClosureError, 'Duplicate/blank venue'):
            inspect(self.root)

    def test_bad_source_hash_fails(self):
        self._child()
        with self.assertRaisesRegex(RouteClosureError, 'RECEIPT_SOURCE_HASH_MISMATCH'):
            inspect(self.root, self._receipt(sha='0'*64))

    def test_eight_retired_links_without_child_files_fail(self):
        routes = [VENUE_PREFIX + s + '/' for s in [
            'spartan-ramnicu-valcea', 'ristorante-damici', 'taverna-damici',
            'street-pub-ramnicu-valcea', 'old-city-garden', 'restaurant-autentic',
            'gyros-time', 'queens-pub']]
        self._hub([(f'fixture-{i}', route) for i, route in enumerate(routes)])
        self._sitemap([INDEX_ROUTE])
        with self.assertRaisesRegex(RouteClosureError, 'GENERATED_CHILD_MISSING'):
            inspect(self.root)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--site-root', type=Path, help='Inspect existing generated site without network or mutations')
    parser.add_argument('--receipt', type=Path, help='Independent HTTP readback JSON, supplied separately')
    args, _ = parser.parse_known_args()
    if args.site_root:
        try:
            receipts = json.loads(args.receipt.read_text(encoding='utf-8')) if args.receipt else None
            print(json.dumps(inspect(args.site_root, receipts), indent=2, ensure_ascii=False))
        except (RouteClosureError, OSError, ValueError) as exc:
            print(json.dumps({'status': 'HOLD', 'error': str(exc)}, ensure_ascii=False))
            raise SystemExit(1)
    else:
        unittest.main(argv=['test_reboot_s5_route_closure.py'], verbosity=2)
