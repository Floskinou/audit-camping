import hashlib
import re
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.export_to_escale import ESCALE_ORIGIN, SECTION_PATH, export


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ExportToEscaleTests(unittest.TestCase):
    """Le miroir publié sur escale-ads.com/tracking-camping doit être autonome
    et respecter les contraintes SEO du dépôt Escale-Ads2026."""

    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).resolve().parents[1]
        cls.tmp = Path(tempfile.mkdtemp(prefix="escale-export-"))
        # Le dépôt cible fournit robots.txt, sitemap.xml (CRLF) et les favicons.
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

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @property
    def section(self) -> Path:
        return self.tmp / "tracking-camping"

    def test_copies_the_whole_site_under_the_section_directory(self):
        source_details = list((self.source / "campings").glob("*/index.html"))
        copied_details = list((self.section / "campings").glob("*/index.html"))
        self.assertTrue((self.section / "index.html").is_file())
        self.assertEqual(len(copied_details), len(source_details))
        self.assertGreaterEqual(len(copied_details), 283)
        for relative in (
            "assets/css/style.css",
            "assets/css/redesign.css",
            "assets/js/app.js",
            "assets/images/logo-escale-ads.png",
            "assets/images/favicon/favicon.ico",
        ):
            self.assertTrue((self.section / relative).is_file(), relative)

    def test_copied_text_files_never_mention_the_github_pages_host(self):
        stale = []
        for path in self.section.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".html", ".css", ".js", ".xml", ".txt"}:
                content = path.read_text(encoding="utf-8", errors="ignore")
                if "floskinou" in content or "github.io" in content:
                    stale.append(str(path.relative_to(self.section)))
        self.assertEqual(stale, [])

    def test_every_page_declares_exactly_one_escale_canonical(self):
        pages = [self.section / "index.html", *sorted((self.section / "campings").glob("*/index.html"))]
        self.assertEqual(len(pages), 284)
        for page in pages:
            html = page.read_text(encoding="utf-8")
            canonicals = re.findall(r'<link rel="canonical" href="([^"]+)"', html)
            og_urls = re.findall(r'<meta property="og:url" content="([^"]+)"', html)
            self.assertEqual(len(canonicals), 1, page)
            self.assertEqual(canonicals, og_urls, page)
            self.assertTrue(
                canonicals[0].startswith(f"{ESCALE_ORIGIN}{SECTION_PATH}/"),
                canonicals[0],
            )
        home = (self.section / "index.html").read_text(encoding="utf-8")
        self.assertIn(f'<link rel="canonical" href="{ESCALE_ORIGIN}{SECTION_PATH}/"', home)
        detail = next((self.section / "campings").glob("*/index.html"))
        slug = detail.parent.name
        self.assertIn(
            f'<link rel="canonical" href="{ESCALE_ORIGIN}{SECTION_PATH}/campings/{slug}/"',
            detail.read_text(encoding="utf-8"),
        )

    def test_homepage_internal_anchor_targets_resolve_to_real_files(self):
        # Miroir de la règle du validateur Escale-Ads2026 : une cible interne
        # doit être un fichier existant — une URL de répertoire échouerait.
        html = (self.section / "index.html").read_text(encoding="utf-8")
        issues = []
        for href in re.findall(r'<a\b[^>]*href="([^"]*)"', html):
            if not href or href.startswith(("#", "http://", "https://", "//", "mailto:", "tel:", "javascript:", "data:")):
                continue
            path_part = href.split("#", 1)[0].split("?", 1)[0]
            if path_part.endswith("/"):
                issues.append(href)
                continue
            if not (self.section / path_part).resolve().is_file():
                issues.append(href)
        self.assertEqual(issues, [])

    def test_detail_pages_return_to_the_section_without_index_html(self):
        # Le retour vers la section ne dépend d'aucune réécriture d'hébergeur.
        detail = next((self.section / "campings").glob("*/index.html"))
        html = detail.read_text(encoding="utf-8")
        self.assertIn('href="../../#classements"', html)
        self.assertIn('href="../../#offre"', html)
        self.assertNotIn('href="../../index.html', html)

    def test_export_is_idempotent(self):
        before = {p: sha(p) for p in self.section.rglob("*") if p.is_file()}
        self.export_again = export(self.source, self.tmp)
        after = {p: sha(p) for p in self.section.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        robots = (self.tmp / "robots.txt").read_text(encoding="utf-8")
        self.assertEqual(robots.count("tracking-camping/sitemap.xml"), 1)
        root_sitemap = (self.tmp / "sitemap.xml").read_text(encoding="utf-8")
        self.assertEqual(
            root_sitemap.count(f"<loc>{ESCALE_ORIGIN}{SECTION_PATH}/</loc>"), 1
        )

    def test_sub_sitemap_targets_escale_and_resolves_every_page(self):
        sitemap = self.section / "sitemap.xml"
        xml = sitemap.read_text(encoding="utf-8")
        locations = re.findall(r"<loc>(.*?)</loc>", xml)
        self.assertEqual(len(locations), 284)
        base = f"{ESCALE_ORIGIN}{SECTION_PATH}/"
        for location in locations:
            self.assertTrue(location.startswith(base), location)
            relative = location[len(base):]
            target = sitemap.parent / relative / "index.html"
            self.assertTrue(target.is_file(), location)

    def test_root_files_keep_their_line_endings_and_gain_one_reference_each(self):
        robots = (self.tmp / "robots.txt").read_bytes()
        self.assertEqual(robots.count(b"tracking-camping/sitemap.xml"), 1)
        self.assertEqual(robots.count(b"\r\n"), 0)  # robots.txt du cible : LF
        sitemap = (self.tmp / "sitemap.xml").read_bytes()
        self.assertEqual(sitemap.count(b"\r\n"), 961 - 961 + sitemap.count(b"\n"))
        ET.parse(self.tmp / "sitemap.xml")  # reste du XML valide
        entry_start = sitemap.find(f"{ESCALE_ORIGIN}{SECTION_PATH}/".encode())
        self.assertGreater(entry_start, 0)
        block = sitemap[sitemap.rfind(b"<url>", 0, entry_start):sitemap.find(b"</url>", entry_start)]
        self.assertEqual(block.count(b"\r\n"), block.count(b"\n"))
        self.assertIn(b"\r\n", block)  # l'entrée ajoutée respecte le CRLF du fichier

    def test_reported_statistics_match_the_copied_tree(self):
        html_pages = list(self.section.rglob("*.html"))
        self.assertEqual(self.stats["pages"], len(html_pages))
        self.assertEqual(self.stats["pages"], 284)
        self.assertEqual(self.stats["canonicals_added"], 284)
        self.assertEqual(self.stats["sub_sitemap_urls"], 284)
        self.assertTrue(self.stats["robots_updated"])
        self.assertTrue(self.stats["root_sitemap_updated"])


if __name__ == "__main__":
    unittest.main()
