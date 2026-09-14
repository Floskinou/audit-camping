#!/usr/bin/env python3
"""Consolidate the browser captures into one audited record per CSV row.

Single method for all 283 rows: one real-browser visit per site capturing the
rendered DOM, the loaded resource list, runtime dataLayer and consent globals,
plus the public GTM container configuration for every container found.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REDO = ROOT / "redo"
INPUT = ROOT / "audit-input.json"
OUT = ROOT / "audit-final.json"
TODAY = "2026-09-14"

CAPTURE_FILES = ("raw-capture-all.json", "raw-capture-ok.json", "raw-capture-b6.json",
                 "raw-v2.json", "raw-weak.json")

CMP_PATTERNS = {
    "Axeptio": r"axeptio",
    "Didomi": r"didomi",
    "Cookiebot": r"cookiebot",
    "OneTrust": r"onetrust|optanon",
    "Usercentrics": r"usercentrics|uc_ui",
    "Tarteaucitron": r"tarteaucitron",
    "Consent Manager": r"consentmanager|__cmp",
    "Sirdata": r"sirdata",
    "Iubenda": r"iubenda|_iub",
    "CCM19": r"ccm19",
    "Borlabs": r"borlabs",
    "Klaro": r"klaro",
    "CookieYes": r"cookieyes",
    "Osano": r"osano",
    "Pandectes": r"pandectes",
    "TCF v2 API": r"__tcfapi",
        "Scripts bloqués avant consentement": r"type=[\"']text/plain[\"'][^>]{0,80}data-category",
    }
CMP_COOKIES = {
    "Axeptio": r"^axeptio_",
    "Didomi": r"^didomi_",
    "Cookiebot": r"^CookieConsent$",
    "OneTrust": r"^Optanon",
    "TCF v2 API": r"^euconsent",
    "Usercentrics": r"^uc_",
    "Tarteaucitron": r"^tarteaucitron",
    "Sirdata": r"^sx$",
    "Consent Manager": r"^dp_cookieconsent",
    "Iubenda": r"^_iub",
}
# Cookies written by a tool prove it actually ran, which is stronger evidence
# than an identifier sitting unused in the page source.
TOOL_COOKIES = {
    "google_analytics": r"^_ga($|_)|^_gid$|^__utma$",
    "google_ads": r"^_gcl_|^_gac_",
    "meta_pixel": r"^_fb[pc]$",
    "bing_uet": r"^_uet(vid|sid)$",
    "matomo": r"^_pk_(id|ses)",
    "clarity": r"^_cl(ck|sk)$",
    "hotjar": r"^_hjSession",
    "ab_tasty": r"^abt_campaigns$",
}
OTHER_TOOLS = {
    "Matomo": r"matomo\.js|piwik\.js|_paq|mtm_|_pk_(id|ses)",
    "Microsoft Clarity": r"clarity\.ms|_clck|_clsk",
    "Hotjar": r"static\.hotjar|hotjar\.com|_hjSession",
    "Plausible": r"plausible\.io/js",
    "Umami": r"umami\.is/script",
    "Fathom": r"usefathom\.com",
    "Commanders Act": r"commandersact|tagcommander|_cq_duid",
    "AT Internet": r"aticdn\.net|xiti\.com|xtcore",
    "Eulerian": r"eulerian\.net|euleriancdn",
    "AB Tasty": r"abtasty\.com|abt_campaigns",
    "Contentsquare": r"contentsquare\.net|_cs_",
    "LinkedIn Insight": r"snap\.licdn\.com",
    "TikTok Pixel": r"analytics\.tiktok\.com",
    "Pinterest Tag": r"ct\.pinterest\.com",
    "Criteo": r"static\.criteo\.net|dis\.criteo\.com",
    "Segment": r"cdn\.segment\.com",
    "Taboola": r"cdn\.taboola\.com",
    "Outbrain": r"outbrain\.com/outbrain\.js",
}
INTERNAL_EVENTS = {"gtm.js", "gtm.dom", "gtm.load", "gtm.click", "gtm.historyChange", "gtm.linkClick", "gtm.scrollDepth"}
# consent globals seen in the page, as opposed to tool globals (gtag, fbq, uetq…)
RUNTIME_CMP = {"__tcfapi", "Axeptio", "tarteaucitron", "Cookiebot", "Didomi", "OneTrust", "Optanon",
               "UC_UI", "__cmp", "_iub", "klaro"}
RUNTIME_TOOLS = {"gtag": "google_analytics", "fbq": "meta_pixel", "uetq": "bing_uet",
                 "_paq": "matomo", "Matomo": "matomo", "clarity": "clarity", "hj": "hotjar"}
BOOKING_RE = re.compile(r"reserv|booking|book|sejour|séjour|dispo|devis|secureholiday|amenitiz|elloha|guestonline|open-system|siblu|yelloh|capfun", re.I)


def load_captures() -> dict[str, dict]:
    """Later files win, but only when that capture actually succeeded."""
    store: dict[str, dict] = {}
    for name in CAPTURE_FILES:
        path = REDO / name
        if not path.exists():
            continue
        for key, value in json.loads(path.read_text(encoding="utf-8")).items():
            if value.get("status") == "ok" or key not in store:
                store[key] = value
    return store


def load_containers() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for f in (REDO / "gtm").glob("GTM-*.js"):
        txt = f.read_text(encoding="utf-8", errors="replace")
        if len(txt) < 200:
            continue
        out[f.stem] = {
            "ga4": sorted(set(re.findall(r'"measurementId"\s*:\s*"([^"]+)"', txt)) | set(re.findall(r"\bG-[A-Z0-9]{8,}\b", txt))),
            "ads": sorted(set(re.findall(r'"conversionId"\s*:\s*"([^"]+)"', txt)) | set(re.findall(r"\bAW-\d{6,}\b", txt))),
            "ua": sorted(set(re.findall(r"\bUA-\d{4,}-\d+\b", txt))),
            "pixel": sorted(set(re.findall(r"[Pp]ixel[Ii]d['\"]?\s*:\s*['\"]?(\d{6,})", txt))),
            "bing": "bat.bing.com" in txt or "/bat.js" in txt,
            "cmp": [k for k, pat in CMP_PATTERNS.items() if re.search(pat, txt, re.I)],
            "size": len(txt),
        }
    return out


# A GTM container id is only trusted when its public configuration could be
# retrieved. "GTM-XSRF" is a token that merely matches the id pattern (its
# container returns 404); GTM-NMV4B7Q8 exists on page 191 but Google answers
# 403, so it is kept as an observation and flagged as unverified.
GTM_ID_EXCEPTIONS = {"GTM-NMV4B7Q8"}


def uniq(values) -> list[str]:
    out: list[str] = []
    for v in values:
        v = str(v).strip()
        if v and v not in out:
            out.append(v)
    return out


def analyse(capture: dict, containers: dict) -> dict:
    data = capture.get("data") or {}
    html = data.get("html") or ""
    res = " ".join(data.get("res") or [])
    blob = f"{html} {res}"
    url = data.get("url") or capture.get("browse_url") or ""
    body_len = data.get("body_len")
    body_len = int(body_len) if isinstance(body_len, (int, float)) else None

    gtm_page = uniq(sorted(set(re.findall(r"GTM-[A-Z0-9]{6,}", blob)))
                    + [k for k in (data.get("gtm_keys") or []) if re.fullmatch(r"GTM-[A-Z0-9]{6,}", str(k))])
    validated = {k for k in gtm_page if k in containers}
    unverified = [k for k in gtm_page if k not in containers and k in GTM_ID_EXCEPTIONS]
    gtm = uniq(sorted(validated) + unverified)
    ga4_page = uniq(sorted(set(re.findall(r"\bG-[A-Z0-9]{8,}\b", blob))))
    ads_page = uniq(sorted(set(re.findall(r"AW-\d{6,}", blob))))
    ga4_cfg, ads_cfg, px_cfg, ua_cfg, bing_cfg, cmp_cfg = [], [], [], [], False, []
    for gid in gtm:
        c = containers.get(gid)
        if not c:
            continue
        ga4_cfg += c["ga4"]; ads_cfg += c["ads"]; px_cfg += c["pixel"]
        ua_cfg += c["ua"]; bing_cfg = bing_cfg or c["bing"]; cmp_cfg += c["cmp"]

    pixel = uniq(sorted(set(re.findall(r"fbq\(\s*['\"]init['\"]\s*,\s*['\"](\d{5,})", blob)))
                 + sorted(set(re.findall(r"facebook\.com/tr\?id=(\d{5,})", blob)))
                 + px_cfg)
    bing = uniq(sorted(set(re.findall(r"ti\s*:\s*['\"](\d{6,9})['\"]", blob))) + (["UET"] if ("bat.bing" in blob or bing_cfg) else []))
    runtime_all = uniq(list(data.get("consent") or []))
    runtime_cmp = [g for g in runtime_all if g in RUNTIME_CMP]
    runtime_globals = {RUNTIME_TOOLS[g] for g in runtime_all if g in RUNTIME_TOOLS}
    cookies = [c for c in (data.get("cookies") or []) if c and c != "__denied__"]
    cookie_tools = {k for k, pat in TOOL_COOKIES.items() if any(re.match(pat, c) for c in cookies)} | runtime_globals
    cmp_cookies = [k for k, pat in CMP_COOKIES.items() if any(re.match(pat, c) for c in cookies)]
    cmp_names = uniq([k for k, pat in CMP_PATTERNS.items() if re.search(pat, blob, re.I)] + cmp_cfg + runtime_cmp + cmp_cookies)
    other_tools = uniq([k for k, pat in OTHER_TOOLS.items()
                        if re.search(pat, blob, re.I) or any(re.match(pat, c, re.I) for c in cookies)])

    dl_events = [e for e in (data.get("dl_events") or []) if e not in INTERNAL_EVENTS]
    dl_len = data.get("dl_len")

    # only count container-derived ids as "configured", page-level ones as "observed"
    ga4 = uniq(ga4_page + ga4_cfg)
    ads = uniq(ads_page + ads_cfg)

    broken = (body_len is None) or (body_len < 300) or url.startswith("chrome-error")
    status = "unreachable" if broken else "ok"

    evidence: list[str] = []
    if ga4:
        evidence.append("identifiant GA4 présent dans la page ou le conteneur GTM")
    elif "google_analytics" in cookie_tools:
        evidence.append("Google Analytics s'exécute : cookie _ga écrit (identifiant non exposé)")
    if ads:
        evidence.append("identifiant Google Ads présent")
    elif "google_ads" in cookie_tools:
        evidence.append("la liaison Google Ads s'exécute : cookie _gcl_* écrit (identifiant non exposé)")
    if pixel:
        evidence.append("identifiant Meta Pixel présent")
    elif "meta_pixel" in cookie_tools:
        evidence.append("le pixel Meta s'exécute : cookie _fbp écrit (identifiant non exposé)")
    if bing or "bing_uet" in cookie_tools:
        evidence.append("suivi Bing UET actif")
    for tool in other_tools:
        evidence.append(f"outil complémentaire détecté : {tool}")
    if cmp_names:
        evidence.append("consentement : " + ", ".join(cmp_names[:4]))

    has_ga = bool(ga4) or "google_analytics" in cookie_tools
    has_ads = bool(ads) or "google_ads" in cookie_tools
    has_pixel = bool(pixel) or "meta_pixel" in cookie_tools
    has_bing = bool(bing) or "bing_uet" in cookie_tools

    score = None
    if status == "ok":
        score = (3 if gtm else 0) + (2 if has_ga else 0) + (2 if has_ads else 0) + (2 if cmp_names else 0) + (1 if has_pixel else 0)

    return {
        "status": status,
        "final_url": url,
        "title": (data.get("title") or "").strip(),
        "gtm_ids": gtm,
        "gtm_unverified": unverified,
        "ga4_ids": ga4,
        "ga4_observed_on_page": ga4_page,
        "ga4_in_gtm_config": uniq(ga4_cfg),
        "google_ads_ids": ads,
        "google_ads_in_gtm_config": uniq(ads_cfg),
        "has_google_analytics": has_ga,
        "has_google_ads": has_ads,
        "has_meta_pixel": has_pixel,
        "has_bing_uet": has_bing,
        "other_tools": other_tools,
        "cookies_seen": cookies[:20],
        "evidence": evidence,
        "legacy_ua_ids": uniq(ua_cfg + sorted(set(re.findall(r"\bUA-\d{4,}-\d+\b", blob)))),
        "meta_pixel_ids": pixel,
        "bing_uet_ids": bing,
        "consent_detected": bool(cmp_names),
        "consent_evidence": ", ".join(cmp_names),
        "data_layers": ([f"dataLayer ({dl_len} entrées)"] if dl_len else []),
        "event_names": dl_events[:20],
        "booking_links": uniq(data.get("booking") or [])[:6],
        "body_len": body_len,
        "score": score,
        "issues": [],
        "priority_actions": [],
        "limitations": [],
    }


def enrich(rec: dict, row: dict) -> dict:
    """Rule-based issues, actions and limits, written for a campsite owner."""
    issues, actions, limits = [], [], []
    score = rec["score"]
    if rec["status"] == "unreachable":
        issues.append("La page n'a pas pu être chargée correctement lors du contrôle (contenu vide, domaine injoignable ou URL erronée).")
        actions.append("Vérifier que l'adresse du site répond bien, puis relancer un contrôle du taggage.")
        limits.append("Aucune conclusion sur le taggage n'est possible pour cette adresse.")
        rec["issues"], rec["priority_actions"], rec["limitations"] = issues, actions, limits
        return rec

    if not rec["gtm_ids"]:
        issues.append("Aucun conteneur Google Tag Manager détecté : chaque outil doit être modifié séparément dans le code du site.")
        actions.append("Centraliser le plan de taggage dans Google Tag Manager pour pouvoir tester et corriger sans intervention technique lourde.")
    if not rec["ga4_ids"]:
        if rec.get("has_google_analytics"):
            issues.append("Google Analytics s'exécute bien (cookie de mesure écrit) mais aucune propriété GA4 n'est identifiable publiquement : impossible de vérifier laquelle reçoit les données ni quels événements sont suivis.")
            actions.append("Confirmer la propriété GA4 réellement utilisée, puis documenter et tester les événements attendus.")
        else:
            issues.append("Aucune propriété Google Analytics 4 identifiée : le trafic et les parcours ne sont pas mesurés.")
            actions.append("Installer GA4 et définir les événements clés : vue d'offre, clic sur réserver, début de réservation, réservation confirmée.")
    elif not rec["ga4_observed_on_page"]:
        issues.append("La propriété GA4 n'apparaît que dans la configuration du conteneur GTM : son déclenchement réel n'a pas pu être confirmé depuis la page.")
        limits.append("Les identifiants GA4 issus de la configuration publique du conteneur prouvent une intention de mesure, pas un déclenchement observé.")
    if not rec["google_ads_ids"]:
        if rec.get("has_google_ads"):
            issues.append("Google Ads est relié au site (cookie de liaison écrit) mais aucune balise de conversion identifiable : on ne peut pas vérifier quelle action est comptée.")
            actions.append("Documenter l'action de conversion utilisée par Google Ads et vérifier qu'elle correspond à un vrai signal d'intérêt.")
        else:
            issues.append("Aucune balise Google Ads détectée : les campagnes ne peuvent pas optimiser sur des conversions fiables.")
            actions.append("Relier Google Ads à des conversions qui correspondent à un vrai signal d'intérêt (devis, demande, réservation) et non à une simple page vue.")
    elif not rec["google_ads_in_gtm_config"] and not re.findall(r"AW-\d{6,}", rec.get("final_url") or ""):
        limits.append("La balise Google Ads a été repérée sans qu'il soit possible de vérifier quelle action de conversion la déclenche.")
    if not rec["consent_detected"]:
        issues.append("Aucune plateforme de consentement identifiable : des tags marketing peuvent se déclencher avant le choix du visiteur.")
        actions.append("Mettre en place une CMP conforme (RGPD) et bloquer les tags non essentiels avant consentement, avec Consent Mode v2.")
    if not rec["meta_pixel_ids"]:
        if rec.get("has_meta_pixel"):
            issues.append("Le pixel Meta s'exécute (cookie _fbp écrit) mais aucun identifiant n'est exposé : impossible de vérifier quel pixel et quels événements sont envoyés.")
            actions.append("Vérifier l'identifiant du pixel Meta et les événements envoyés, avec consentement et déduplication.")
        else:
            issues.append("Aucun pixel Meta détecté : les campagnes Facebook et Instagram, si elles existent, ne peuvent pas être optimisées sur les demandes reçues.")
            actions.append("Ajouter le suivi Meta seulement si des campagnes Meta sont prévues, avec consentement et déduplication des événements.")
    if rec["legacy_ua_ids"]:
        issues.append("Une ancienne propriété Universal Analytics subsiste : elle ne collecte plus de données exploitables depuis 2023.")
        actions.append("Retirer les balises Universal Analytics pour éviter les appels inutiles et les écarts entre outils.")
    if not rec["event_names"]:
        issues.append("Aucun événement métier observé dans le dataLayer : seul le chargement de page est mesuré.")
        actions.append("Décrire un tunnel de réservation en événements (offre consultée, panier, coordonnées, confirmation) pour identifier où les visiteurs abandonnent.")
    if not rec["booking_links"]:
        issues.append("Aucun moteur de réservation identifiable depuis la page d'accueil : la mesure de la réservation est difficile à raccorder.")
        actions.append("Vérifier la continuité du suivi entre le site et le moteur de réservation, puis confirmer la remontée de la réservation finale.")
    if not actions:
        actions.append("Contrôler régulièrement la remontée des conversions et la cohérence entre GA4, Google Ads et le moteur de réservation.")
    if not issues:
        issues.append("Aucun manque structurel sur les signaux de base : l'enjeu porte désormais sur la qualité des événements de réservation, leur valeur et leur déduplication entre outils.")
        actions.append("Vérifier de bout en bout qu'une réservation réelle remonte une seule fois, avec le bon montant, dans GA4 comme dans Google Ads.")

    if rec.get("gtm_unverified"):
        limits.append("Le conteneur %s a été repéré sur la page mais sa configuration publique n'a pas pu être récupérée pour vérification." % ", ".join(rec["gtm_unverified"]))
    limits.append("Observation publique datée du %s : une seule visite par site, sans réservation ni paiement réel." % TODAY)
    limits.append("Un identifiant présent ne garantit pas que la conversion remonte correctement jusqu'à la plateforme.")
    if score is not None and score <= 4:
        limits.append("Score faible : le site cumule plusieurs manques structurels, une reprise complète du plan de taggage est à prévoir.")

    rec["issues"] = uniq(issues)[:8]
    rec["priority_actions"] = uniq(actions)[:5]
    rec["limitations"] = uniq(limits)[:6]
    return rec


def main() -> None:
    captures = load_captures()
    containers = load_containers()
    rows = json.loads(INPUT.read_text(encoding="utf-8"))
    out = []
    for row in rows:
        key = str(row["row"])
        cap = captures.get(key)
        if not cap:
            raise SystemExit(f"missing capture for row {key}")
        rec = analyse(cap, containers)
        rec = enrich(rec, row)
        rec.update({"row": int(row["row"]), "name": row["name"], "city": row["city"],
                    "postal_code": row["postal_code"], "source_url": row["source_url"],
                    "browse_url": row["browse_url"], "slug": row["slug"]})
        out.append(rec)
    if len(out) != len(rows):
        raise SystemExit(f"row count mismatch {len(out)} != {len(rows)}")

    # chain-level mutualisation: one container driving several establishments
    from collections import defaultdict
    usage: dict[str, list[int]] = defaultdict(list)
    for rec in out:
        for gid in rec["gtm_ids"]:
            usage[gid].append(rec["row"])
    for rec in out:
        shared = [g for g in rec["gtm_ids"] if len(usage[g]) > 1]
        if shared:
            rec["issues"] = uniq(rec["issues"] + [
                "Le conteneur %s est mutualisé : il pilote aussi d'autres établissements de ce fichier, donc toute modification de taggage les impacte." % ", ".join(shared)
            ])[:8]
    order = ["row", "name", "city", "postal_code", "source_url", "browse_url", "slug", "status",
             "final_url", "title", "gtm_ids", "ga4_ids", "ga4_observed_on_page", "ga4_in_gtm_config",
             "google_ads_ids", "google_ads_in_gtm_config", "has_google_analytics", "has_google_ads",
             "has_meta_pixel", "has_bing_uet", "other_tools", "cookies_seen", "evidence",
             "legacy_ua_ids", "meta_pixel_ids", "bing_uet_ids",
             "consent_detected", "consent_evidence", "data_layers", "event_names", "booking_links",
             "body_len", "score", "issues", "priority_actions", "limitations"]
    out = [{k: r.get(k) for k in order} for r in out]
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = [r for r in out if r["status"] == "ok"]
    print(f"records: {len(out)} | reached: {len(ok)} | unreachable: {len(out) - len(ok)}")
    print(f"GTM {sum(bool(r['gtm_ids']) for r in out)} | GA4 {sum(bool(r['ga4_ids']) for r in out)} | "
          f"Ads {sum(bool(r['google_ads_ids']) for r in out)} | Pixel {sum(bool(r['meta_pixel_ids']) for r in out)} | "
          f"CMP {sum(bool(r['consent_detected']) for r in out)}")
    if ok:
        print(f"average score (reached): {sum(r['score'] for r in ok) / len(ok):.2f}")
    print("written:", OUT)


if __name__ == "__main__":
    main()
