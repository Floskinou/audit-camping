#!/usr/bin/env python3
"""Publie l'observatoire Audit Camping sous escale-ads.com/tracking-camping.

Le site source (audit-camping) reste la source de vérité pour GitHub Pages.
Cet export produit un miroir autonome dans le dépôt Escale-Ads2026 :

- copie stricte de l'accueil, des 283 fiches et des assets nécessaires ;
- liens internes réécrits en cibles fichier/répertoire propres (le validateur
  HTML d'Escale-Ads2026 exige qu'une cible interne soit un fichier existant) ;
- canonical + og:url injectés pour chaque page sous la URL publique cible ;
- sitemap de section généré, robots.txt et sitemap racine complétés.

Aucun fichier source n'est modifié ; les fichiers racine du dépôt cible ne
sont complétés que s'ils ne contiennent pas déjà la référence (idempotence).
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path, PurePosixPath

ESCALE_ORIGIN = "https://escale-ads.com"
SECTION_PATH = "/tracking-camping"
SECTION_DIR = "tracking-camping"
META_PIXEL_ID = "1169155973124323"

# Le miroir est la destination des publicités Meta (ad set optimisé sur le
# pixel Lead) : l'export injecte le pixel — le dépôt source GitHub Pages, lui,
# n'en porte pas. Le clic sur un CTA Calendly émet Lead (signal de
# conversion attendu par l'ad set) ; la fiche émet ViewContent.
META_PIXEL_SNIPPET = """<!-- Meta Pixel — injecté par scripts/export_to_escale.py -->
<noscript><img height="1" width="1" style="display:none" alt="" src="https://www.facebook.com/tr?id=__PIXEL_ID__&ev=PageView&noscript=1"/></noscript>
<script>
  !function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,document,'script','https://connect.facebook.net/fr_FR/fbevents.js');
  fbq('init', '__PIXEL_ID__');
  fbq('track', 'PageView');
  document.addEventListener('click', function (event) {
    var link = event.target && event.target.closest ? event.target.closest('a[href*="calendly.com"]') : null;
    if (link && !window.__escaleLeadTracked) {
      window.__escaleLeadTracked = true;
      fbq('track', 'Lead');
    }
  });
  document.addEventListener('DOMContentLoaded', function () {
    if (document.querySelector('.camping-detail')) {
      fbq('track', 'ViewContent', { content_name: document.title });
    }
  });
</script>
"""
ASSETS = (
    "assets/css/style.css",
    "assets/css/redesign.css",
    "assets/js/app.js",
    "assets/images/logo-escale-ads.png",
)
ROOT_SITEMAP_URL = f"{ESCALE_ORIGIN}{SECTION_PATH}/"
SUB_SITEMAP_LINE = f"Sitemap: {ESCALE_ORIGIN}{SECTION_PATH}/sitemap.xml"
ROOT_SITEMAP_MARKER = f"<loc>{ROOT_SITEMAP_URL}</loc>"


def _canonical_for(relative_page: str) -> str:
    """URL publique canonique d'une page du miroir (relative à la racine cible).

    ``tracking-camping/index.html`` -> ``.../tracking-camping/``
    ``tracking-camping/campings/x/index.html`` -> ``.../tracking-camping/campings/x/``
    """
    section_relative = PurePosixPath(relative_page).relative_to(SECTION_DIR)
    parent = section_relative.parent.as_posix()
    suffix = "" if parent == "." else f"{parent}/"
    return f"{ESCALE_ORIGIN}{SECTION_PATH}/{suffix}"


def _icon_prefix(relative_page: str) -> str:
    section_relative = PurePosixPath(relative_page).relative_to(SECTION_DIR)
    depth = len(section_relative.parent.parts) if str(section_relative.parent) != "." else 0
    return "../" * depth


def _rewrite_internal_links(html: str) -> str:
    # Les cartes et le classement pointent vers des répertoires ; le validateur
    # du dépôt cible exige un fichier. La fiche reste accessible via index.html.
    html = re.sub(r'href="(campings/[^"]+/)"', r'href="\1index.html"', html)
    # Les pages fiches retournent à la section sans passer par index.html :
    # la résolution relative fonctionne sans réécriture d'hébergeur.
    html = html.replace('href="../../index.html#', 'href="../../#')
    html = html.replace('href="../../index.html"', 'href="../../"')
    return html


def _inject_head(html: str, canonical: str, icon: bool) -> tuple[str, bool]:
    if 'rel="canonical"' in html:
        return html, False
    injected = []
    if icon:
        injected.append('  <link rel="icon" href="{prefix}assets/images/favicon/favicon.ico" type="image/x-icon">')
    injected.append(f'  <link rel="canonical" href="{canonical}">')
    injected.append(f'  <meta property="og:url" content="{canonical}">')
    prefix = _icon_prefix_from_canonical(canonical)
    block = "\n".join(line.format(prefix=prefix) for line in injected) + "\n</head>"
    return html.replace("</head>", block, 1), True


def _inject_meta_pixel(html: str) -> str:
    """Injecte le pixel Meta dans le <head> du miroir (une seule fois)."""
    if "fbevents.js" in html:
        return html
    snippet = META_PIXEL_SNIPPET.replace("__PIXEL_ID__", META_PIXEL_ID)
    block = "  " + snippet.replace("\n", "\n  ").rstrip() + "\n</head>"
    return html.replace("</head>", block, 1)


def _icon_prefix_from_canonical(canonical: str) -> str:
    """Préfixe relatif menant de la page à la racine de la section."""
    base = f"{ESCALE_ORIGIN}{SECTION_PATH}/"
    assert canonical.startswith(base), canonical
    depth = len([part for part in canonical[len(base):].split("/") if part])
    return "../" * depth


def _build_sub_sitemap(pages: list[str]) -> bytes:
    # pages : chemins relatifs (posix) uniques de toutes les fiches, accueil inclus.
    entries = []
    home = f"{SECTION_DIR}/index.html"
    if home in pages:
        entries.append(
            f'  <url><loc>{ROOT_SITEMAP_URL}</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>'
        )
    for relative in sorted(pages):
        if relative == home:
            continue
        section_relative = PurePosixPath(relative).relative_to(SECTION_DIR)
        parent = section_relative.parent.as_posix()
        entries.append(
            f'  <url><loc>{ESCALE_ORIGIN}{SECTION_PATH}/{parent}/</loc>'
            f'<changefreq>monthly</changefreq><priority>0.7</priority></url>'
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
    )
    return xml.encode("utf-8")


def _update_robots(target: Path) -> bool:
    path = target / "robots.txt"
    content = path.read_bytes()
    if SUB_SITEMAP_LINE.encode("utf-8") in content:
        return False
    lines = content.split(b"\n")
    anchor = next(
        (i for i, line in enumerate(lines) if line.rstrip(b"\r") == b"Sitemap: https://escale-ads.com/sitemap.xml"),
        None,
    )
    if anchor is None:
        raise SystemExit("robots.txt: ligne Sitemap racine introuvable — intégration refusée")
    ending = b"\r" if lines[anchor].endswith(b"\r") else b""
    lines.insert(anchor + 1, SUB_SITEMAP_LINE.encode("utf-8") + ending)
    path.write_bytes(b"\n".join(lines))
    return True


def _update_root_sitemap(target: Path) -> bool:
    path = target / "sitemap.xml"
    content = path.read_bytes()
    if ROOT_SITEMAP_MARKER.encode("utf-8") in content:
        return False
    anchor = content.find(b"</urlset>")
    if anchor < 0:
        raise SystemExit("sitemap.xml: balise </urlset> introuvable — intégration refusée")
    newline = b"\r\n" if b"\r\n" in content else b"\n"
    indent = "    " if newline == b"\r\n" else "    "
    block = newline.join(
        [
            f"{indent}<url>".encode("utf-8"),
            f"{indent}    <loc>{ROOT_SITEMAP_URL}</loc>".encode("utf-8"),
            f"{indent}    <lastmod>{date.today().isoformat()}</lastmod>".encode("utf-8"),
            f"{indent}    <changefreq>weekly</changefreq>".encode("utf-8"),
            f"{indent}    <priority>0.9</priority>".encode("utf-8"),
            f"{indent}</url>".encode("utf-8"),
            b"",
        ]
    )
    path.write_bytes(content[:anchor] + block + content[anchor:])
    return True


def export(source: Path, target: Path) -> dict:
    source, target = Path(source), Path(target)
    if not (source / "index.html").is_file() or not (source / "campings").is_dir():
        raise SystemExit(f"Source invalide (index.html/campings manquants) : {source}")
    for required in ("robots.txt", "sitemap.xml"):
        if not (target / required).is_file():
            raise SystemExit(f"Fichier racine manquant dans la cible {target} : {required}")

    section = target / SECTION_DIR
    if section.exists():
        shutil.rmtree(section)

    detail_pages = sorted(
        path for path in (source / "campings").glob("*/index.html") if path.is_file()
    )
    html_sources = [source / "index.html", *detail_pages]

    favicon_sources = []
    favicon_dir = target / "assets" / "images" / "favicon"
    if favicon_dir.is_dir():
        favicon_sources = sorted(path for path in favicon_dir.iterdir() if path.is_file())

    copied_pages: list[str] = []
    canonicals_added = 0
    icon = bool(favicon_sources)
    for page in html_sources:
        relative = (SECTION_DIR + "/" + page.relative_to(source).as_posix())
        html = page.read_bytes().decode("utf-8")
        html = _rewrite_internal_links(html)
        html, added = _inject_head(html, _canonical_for(relative), icon)
        canonicals_added += int(added)
        html = _inject_meta_pixel(html)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(html.encode("utf-8"))
        copied_pages.append(relative)

    for relative in ASSETS:
        src = source / relative
        if not src.is_file():
            raise SystemExit(f"Asset source manquant : {src}")
        destination = target / SECTION_DIR / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, destination)

    for src in favicon_sources:
        destination = section / "assets" / "images" / "favicon" / src.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix.lower() in {".svg", ".webmanifest", ".txt", ".xml"}:
            # Les fichiers textes du dépôt cible portent des espaces finaux que
            # git diff --check refuse dans un ajout ; la copie les normalise
            # (whitespace seul, sans effet sur le rendu).
            text = src.read_text(encoding="utf-8")
            normalized = "\n".join(line.rstrip() for line in text.splitlines()) + "\n"
            destination.write_bytes(normalized.encode("utf-8"))
        else:
            shutil.copy2(src, destination)

    sub_sitemap = _build_sub_sitemap(copied_pages)
    (section / "sitemap.xml").write_bytes(sub_sitemap)

    robots_updated = _update_robots(target)
    root_sitemap_updated = _update_root_sitemap(target)

    sub_urls = sub_sitemap.count(b"<loc>")
    return {
        "pages": len(copied_pages),
        "canonicals_added": canonicals_added,
        "sub_sitemap_urls": sub_urls,
        "robots_updated": robots_updated,
        "root_sitemap_updated": root_sitemap_updated,
    }


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: python scripts/export_to_escale.py SOURCE TARGET")
    print(json.dumps(export(Path(sys.argv[1]), Path(sys.argv[2])), ensure_ascii=False))
