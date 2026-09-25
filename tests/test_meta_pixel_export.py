import hashlib
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.export_to_escale import export

PIXEL_ID = "1169155973124323"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MetaPixelExportTests(unittest.TestCase):
    """Le miroir escale-ads.com/tracking-camping doit mesurer : c'est la
    destination des publicités Meta (ad set optimisé sur le pixel Lead).

    Le pixel est injecté par l'export (étape « escale-isation ») ; le dépôt
    source GitHub Pages ne doit pas en porter la trace."""

    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).resolve().parents[1]
        cls.tmp = Path(tempfile.mkdtemp(prefix="escale-pixel-"))
        (cls.tmp / "robots.txt").write_bytes(
            b"User-agent: *\nAllow: /\n\nSitemap: https://escale-ads.com/sitemap.xml\n"
        )
        (cls.tmp / "sitemap.xml").write_bytes(
            b'<?xml version="1.0" encoding="UTF-8"?>\r\n'
            b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\r\n'
            b"    <url>\r\n"
            b"        <loc>https://escale-ads.com/</loc>\r\n"
            b"        <lastmod>2026-02-10</lastmod>\r\n"
            b"    </url>\r\n"
            b"</urlset>\r\n"
        )
        favicon_dir = cls.tmp / "assets" / "images" / "favicon"
        favicon_dir.mkdir(parents=True)
        (favicon_dir / "favicon.ico").write_bytes(b"\x00\x00\x01\x00")
        cls.stats = export(cls.source, cls.tmp)
        cls.section = cls.tmp / "tracking-camping"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def pages(self):
        return [self.section / "index.html", *sorted((self.section / "campings").glob("*/index.html"))]

    def test_every_page_initialises_the_meta_pixel_exactly_once(self):
        pages = self.pages()
        self.assertEqual(len(pages), 284)
        for page in pages:
            html = page.read_text(encoding="utf-8")
            self.assertEqual(html.count("fbevents.js"), 1, page)
            self.assertIn(f"fbq('init', '{PIXEL_ID}')", html, page)
            self.assertIn("fbq('track', 'PageView')", html, page)
            # L'img noscript de secours porte un alt (validateur Escale-Ads2026).
            self.assertIn('alt="" src="https://www.facebook.com/tr?', html, page)

    def test_calendly_cta_clicks_fire_the_lead_event(self):
        for page in (self.section / "index.html", next((self.section / "campings").glob("*/index.html"))):
            html = page.read_text(encoding="utf-8")
            self.assertIn('addEventListener(\'click\'', html, page)
            self.assertIn("calendly.com", html, page)
            self.assertIn("fbq('track', 'Lead')", html, page)
            # La capture de clic couvre tous les CTA du lien calendly.
            self.assertRegex(html, r"closest\('a\[href\*=\"calendly\.com\"\]'\)")

    def test_detail_pages_fire_viewcontent_for_the_report(self):
        detail = next((self.section / "campings").glob("*/index.html"))
        html = detail.read_text(encoding="utf-8")
        self.assertIn("DOMContentLoaded", html)
        self.assertIn("'.camping-detail'", html)
        self.assertIn("fbq('track', 'ViewContent'", html)

    def test_source_pages_do_not_carry_the_pixel(self):
        # Le pixel appartient au miroir publié, pas au dépôt source GitHub Pages.
        for page in [self.source / "index.html", *list((self.source / "campings").glob("*/index.html"))[:5]]:
            html = page.read_text(encoding="utf-8")
            self.assertNotIn("fbevents.js", html, page)

    def test_export_remains_idempotent_with_the_pixel(self):
        before = {p: sha(p) for p in self.section.rglob("*") if p.is_file()}
        export(self.source, self.tmp)
        after = {p: sha(p) for p in self.section.rglob("*") if p.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
