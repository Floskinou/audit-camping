#!/usr/bin/env python3
"""Generate the static Audit Camping site from browser audit JSON batches."""
from __future__ import annotations

import html
import json
import math
import re
import shutil
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "audit-input.json"
FINAL = ROOT / "audit-final.json"
RESULTS = ROOT / "audit-results"
PAGES = ROOT / "campings"
TODAY = "2026-09-23"

REGIONS = {
    "01": "Auvergne-Rhône-Alpes", "02": "Hauts-de-France", "03": "Auvergne-Rhône-Alpes", "04": "Provence-Alpes-Côte d’Azur", "05": "Provence-Alpes-Côte d’Azur", "06": "Provence-Alpes-Côte d’Azur", "07": "Auvergne-Rhône-Alpes", "08": "Grand Est", "09": "Occitanie", "10": "Grand Est", "11": "Occitanie", "12": "Occitanie", "13": "Provence-Alpes-Côte d’Azur", "14": "Normandie", "15": "Auvergne-Rhône-Alpes", "16": "Nouvelle-Aquitaine", "17": "Nouvelle-Aquitaine", "18": "Centre-Val de Loire", "19": "Nouvelle-Aquitaine", "20": "Corse", "21": "Bourgogne-Franche-Comté", "22": "Bretagne", "23": "Nouvelle-Aquitaine", "24": "Nouvelle-Aquitaine", "25": "Bourgogne-Franche-Comté", "26": "Auvergne-Rhône-Alpes", "27": "Normandie", "28": "Centre-Val de Loire", "29": "Bretagne", "30": "Occitanie", "31": "Occitanie", "32": "Occitanie", "33": "Nouvelle-Aquitaine", "34": "Occitanie", "35": "Bretagne", "36": "Centre-Val de Loire", "37": "Centre-Val de Loire", "38": "Auvergne-Rhône-Alpes", "39": "Bourgogne-Franche-Comté", "40": "Nouvelle-Aquitaine", "41": "Centre-Val de Loire", "42": "Auvergne-Rhône-Alpes", "43": "Auvergne-Rhône-Alpes", "44": "Pays de la Loire", "45": "Centre-Val de Loire", "46": "Occitanie", "47": "Nouvelle-Aquitaine", "48": "Occitanie", "49": "Pays de la Loire", "50": "Normandie", "51": "Grand Est", "52": "Grand Est", "53": "Pays de la Loire", "54": "Grand Est", "55": "Grand Est", "56": "Bretagne", "57": "Grand Est", "58": "Bourgogne-Franche-Comté", "59": "Hauts-de-France", "60": "Hauts-de-France", "61": "Normandie", "62": "Hauts-de-France", "63": "Auvergne-Rhône-Alpes", "64": "Nouvelle-Aquitaine", "65": "Occitanie", "66": "Occitanie", "67": "Grand Est", "68": "Grand Est", "69": "Auvergne-Rhône-Alpes", "70": "Bourgogne-Franche-Comté", "71": "Bourgogne-Franche-Comté", "72": "Pays de la Loire", "73": "Auvergne-Rhône-Alpes", "74": "Auvergne-Rhône-Alpes", "75": "Île-de-France", "76": "Normandie", "77": "Île-de-France", "78": "Île-de-France", "79": "Nouvelle-Aquitaine", "80": "Hauts-de-France", "81": "Occitanie", "82": "Occitanie", "83": "Provence-Alpes-Côte d’Azur", "84": "Provence-Alpes-Côte d’Azur", "85": "Pays de la Loire", "86": "Nouvelle-Aquitaine", "87": "Nouvelle-Aquitaine", "88": "Grand Est", "89": "Bourgogne-Franche-Comté", "90": "Bourgogne-Franche-Comté", "91": "Île-de-France", "92": "Île-de-France", "93": "Île-de-France", "94": "Île-de-France", "95": "Île-de-France"
}


def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def text(value) -> str:
    return str(value or "").strip()


def as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [text(x) for x in value if text(x)]
    if isinstance(value, tuple):
        return [text(x) for x in value if text(x)]
    if isinstance(value, str):
        return [x.strip() for x in re.split(r"[,\n]", value) if x.strip()]
    return [text(value)] if text(value) else []


def unique(values) -> list[str]:
    result=[]
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def region_for(postal: str) -> str:
    p = text(postal)
    if p.startswith("97") or p.startswith("98"):
        return "Outre-mer"
    return REGIONS.get(p[:2], "France")


def safe_score(row: dict) -> float | None:
    if text(row.get("status")).lower() not in {"ok", "success", "loaded"}:
        return None
    provided = row.get("score")
    if isinstance(provided, (int, float)):
        return float(provided)
    ids = {key: as_list(row.get(key)) for key in ("gtm_ids", "ga4_ids", "google_ads_ids", "meta_pixel_ids", "bing_uet_ids")}
    consent = bool(row.get("consent_detected"))
    value = (3 if ids["gtm_ids"] else 0) + (2 if ids["ga4_ids"] else 0) + (2 if ids["google_ads_ids"] else 0) + (2 if consent else 0) + (1 if ids["meta_pixel_ids"] else 0)
    return float(value)


def score_label(score: float | None) -> str:
    if score is None:
        return "Non vérifiable"
    if score < 1:
        return "Suivi non démontré"
    if score < 2.5:
        return "Très insuffisant"
    if score < 4:
        return "Parcours peu mesuré"
    if score < 5:
        return "Étapes visibles · achat non validé"
    return "Plafonné · achat non testé"


def score_class(score: float | None) -> str:
    return "score-na" if score is None else f"score-{int(score)}"


def slugify(value: str) -> str:
    value=unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-") or "camping"


def normalized_result(row: dict) -> dict:
    out=dict(row)
    out["name"] = text(out.get("name")) or "Camping sans nom"
    out["city"] = text(out.get("city"))
    out["postal_code"] = text(out.get("postal_code"))
    out["source_url"] = text(out.get("source_url"))
    out["browse_url"] = text(out.get("browse_url")) or out["source_url"]
    out["slug"] = text(out.get("slug")) or f"{int(out.get('row', 0)):03d}-{slugify(out['name'])}"
    out["status"] = text(out.get("status")).lower() or "error"
    for key in ("gtm_ids", "ga4_ids", "google_ads_ids", "meta_pixel_ids", "bing_uet_ids", "data_layers", "event_names", "booking_links", "issues", "priority_actions", "limitations"):
        out[key]=unique(as_list(out.get(key)))
    out["consent_detected"] = bool(out.get("consent_detected"))
    out["consent_evidence"] = text(out.get("consent_evidence"))
    out["score"] = safe_score(out)
    return out


def read_payload(path: Path) -> list[dict]:
    """Accept both a JSON array and JSON-lines output from an audit batch."""
    raw=path.read_text(encoding="utf-8")
    if raw.lstrip().startswith("["):
        payload=json.loads(raw)
        if not isinstance(payload, list):
            raise ValueError(f"Expected a list in {path}")
        return payload
    rows=[]
    for line in raw.splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_results() -> list[dict]:
    """Read the consolidated audit produced by analyze_captures.py."""
    expected=json.loads(INPUT.read_text(encoding="utf-8"))
    if not FINAL.exists():
        raise SystemExit(f"Missing {FINAL}; run scripts/analyze_captures.py first")
    rows=[normalized_result(row) for row in json.loads(FINAL.read_text(encoding="utf-8"))]
    expected_keys=[(int(row["row"]), row["source_url"]) for row in expected]
    actual_keys=[(int(row.get("row", -1)), row.get("source_url", "")) for row in rows]
    if len(rows) != len(expected):
        raise SystemExit(f"Audit count mismatch: expected {len(expected)}, got {len(rows)}")
    if len(set(actual_keys)) != len(actual_keys):
        raise SystemExit("Duplicate audit rows detected")
    if set(actual_keys) != set(expected_keys):
        missing=sorted(set(expected_keys)-set(actual_keys))[:5]
        extra=sorted(set(actual_keys)-set(expected_keys))[:5]
        raise SystemExit(f"Audit keys mismatch; missing={missing}, extra={extra}")
    return sorted(rows, key=lambda row: int(row["row"]))


def nav(detail: bool=False) -> str:
    return "../../" if detail else ""


def header(title: str, description: str, detail: bool=False) -> str:
    prefix=nav(detail)
    return f'''<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <link rel="stylesheet" href="{prefix}assets/css/style.css">
</head>
<body>
  <a class="skip-link" href="#main-content">Aller au contenu</a>
  <header class="site-header">
    <a class="logo" href="{prefix}index.html" aria-label="Retour à Audit Camping">🏕️ <strong>Audit</strong> Camping</a>
    <span class="tagline">par Escale Ads</span>
  </header>
'''


def footer(detail: bool=False) -> str:
    prefix=nav(detail)
    return f'''  <footer class="site-footer">
    <p><strong>Audit Camping</strong> — une lecture claire du tracking des campings 5 étoiles.</p>
    <p class="powered">Méthode d’observation publique · {TODAY} · <a href="{prefix}index.html">Voir tous les campings</a></p>
  </footer>
  <script src="{prefix}assets/js/app.js" defer></script>
</body>
</html>
'''


def tool_cell(icon, label, present, ids, note="") -> str:
    state="Présent" if present else "Non détecté"
    cls="status-ok" if present else "status-missing"
    detail=f'<small>{esc(", ".join(ids[:4]))}</small>' if ids else (f'<small>{esc(note)}</small>' if note else '')
    return f'''<article class="audit-item"><div class="tool-icon">{icon}</div><div class="name">{esc(label)}</div><div class="status {cls}">{state}</div>{detail}</article>'''


def priority_rows(row: dict) -> list[str]:
    provided=as_list(row.get("priority_actions"))
    if provided:
        return provided[:5]
    actions=[]
    if row["score"] is None:
        actions.append("Rendre le site et le parcours de réservation vérifiables, puis relancer un contrôle complet.")
        return actions
    if not row["consent_detected"]:
        actions.append("Mettre en place une CMP conforme et bloquer les tags marketing avant le consentement.")
    if not row["gtm_ids"]:
        actions.append("Centraliser le plan de taggage dans Google Tag Manager pour fiabiliser les évolutions et les tests.")
    if not row["ga4_ids"]:
        actions.append("Installer GA4 et définir les événements utiles : vue d’offre, clic réservation, début de checkout et réservation confirmée.")
    if not row["google_ads_ids"]:
        actions.append("Relier les conversions Google Ads aux actions qui génèrent réellement une demande ou une réservation.")
    if not row["meta_pixel_ids"]:
        actions.append("Ajouter le suivi Meta uniquement si des campagnes Facebook/Instagram sont actives, avec consentement et déduplication adaptés.")
    if row["booking_links"]:
        actions.append("Tester la continuité du tracking sur le moteur de réservation externe et la remontée de la réservation finale.")
    if not actions:
        actions.append("Contrôler régulièrement les événements de réservation, leurs valeurs et la déduplication entre les outils.")
    return unique(actions)[:5]


def detail_page(row: dict) -> str:
    score=row["score"]
    score_text="—" if score is None else (str(int(score)) if score.is_integer() else str(score).replace(".", ","))
    status_text="Audit non vérifiable" if score is None else score_label(score)
    location=" · ".join(x for x in (row["city"], row["postal_code"], region_for(row["postal_code"])) if x)
    tools=[
        ("▦", "Google Tag Manager", row["gtm_ids"], row["gtm_ids"], "Aucun conteneur observé"),
        ("◉", "Google Analytics 4", row["ga4_ids"], row["ga4_ids"], "Aucune propriété observée"),
        ("↗", "Google Ads", row["google_ads_ids"], row["google_ads_ids"], "Aucune balise observée"),
        ("◌", "Meta Pixel", row["meta_pixel_ids"], row["meta_pixel_ids"], "Aucun pixel observé"),
        ("✓", "Consentement RGPD", row["consent_detected"], [], "Aucun signal CMP fiable observé"),
    ]
    tool_html="".join(tool_cell(*item) for item in tools)
    ids=[]
    for key,label in (("gtm_ids","GTM"),("ga4_ids","GA4"),("google_ads_ids","Google Ads"),("meta_pixel_ids","Meta Pixel"),("bing_uet_ids","Bing UET")):
        for ident in row[key]: ids.append(f"<li><strong>{esc(label)}</strong><code>{esc(ident)}</code></li>")
    id_html="<ul class=\"id-list\">"+"".join(ids)+"</ul>" if ids else '<p class="muted">Aucun identifiant public exploitable n’a été relevé.</p>'
    issues=row["issues"] or (["Aucun problème bloquant déduit des signaux publics observés."] if score is not None else ["La page n’a pas pu être contrôlée de manière exploitable."])
    issue_html="".join(f"<li>{esc(item)}</li>" for item in issues[:8])
    actions=priority_rows(row)
    action_html=""
    for i, item in enumerate(actions):
        priority = "Priorité 1" if i == 0 else f"Priorité {i + 1}"
        level = "high" if i == 0 else "med"
        action_html += f'<li><span class="priority prio-{level}">{priority}</span> {esc(item)}</li>'
    funnel_events=as_list(row.get("booking_funnel_events"))
    events=" · ".join((funnel_events or row["event_names"])[:10]) if (funnel_events or row["event_names"]) else "Aucun événement dataLayer public relevé"
    evidence=as_list(row.get("evidence"))
    evidence_html=("".join(f"<li>{esc(item)}</li>" for item in evidence[:8])
                   if evidence else "<li>Aucun signal exploitable n'a été observé sur cette page.</li>")
    tools_seen=as_list(row.get("other_tools"))
    if tools_seen:
        evidence_html+="".join(f"<li>Autre outil repéré : {esc(t)}</li>" for t in tools_seen[:6])
    booking="".join(f"<li><a href=\"{esc(url)}\" rel=\"nofollow noopener\">{esc(url)}</a></li>" for url in row["booking_links"][:5]) or '<li>Aucun lien de réservation identifiable dans la page observée.</li>'
    historical_limits=[item for item in row["limitations"] if "2026-09-14" not in item and "une seule visite par site" not in item.lower() and "sans réservation ni paiement réel" not in item.lower()]
    limitations=unique(["Parcours simulé jusqu'aux disponibilités ou à la liste d'hébergements ; aucune réservation, validation ou paiement réel.", "Sans transaction réelle ou environnement de recette, le déclenchement final d'un purchase reste non vérifié."] + historical_limits)
    limit_html="".join(f"<li>{esc(item)}</li>" for item in limitations[:6])
    breakdown=row.get("breakdown", {})
    journey_labels={"ok":"Parcours public accessible ; achat final non testé.", "blocked":"Tunnel bloqué ou inaccessible ; suivi au-delà non vérifiable.", "booking_closed":"Réservations en ligne fermées au moment du test.", "partial_manual":"Recherche et liste d'hébergements atteintes ; arrêt avant choix d'une offre."}
    journey_summary=text(row.get("journey_verdict")) or journey_labels.get(row.get("journey_status"), "Parcours non vérifiable.")
    interaction="Observée" if row.get("booking_interaction_tracked") else "Non observée"
    engine_hit="Observé" if row.get("booking_engine_measurement_observed") else "Non observé"
    funnel_text=" · ".join(funnel_events) if funnel_events else "Aucun événement e-commerce spécifique observé"
    purchase_text="Confirmé" if row.get("purchase_confirmed") else "Non confirmé — aucune réservation réelle effectuée"
    legacy_score=row.get("tag_presence_score")
    legacy_text="Non vérifiable" if legacy_score is None else f"{str(legacy_score).replace('.', ',')}/10"
    false_count=int(row.get("invalid_purchase_hit_count", 0) or 0)
    false_notice=(f'<p class="journey-alert"><strong>Signal critique :</strong> {false_count} hit(s) Google Ads étiqueté(s) purchase à valeur nulle ou sans transaction avant toute commande.</p>' if row.get("invalid_google_ads_purchase") else "")
    breakdown_text=(f"Outils {str(breakdown.get('stack_setup_2pts', 0)).replace('.', ',')}/2 · interaction {str(breakdown.get('booking_interaction_1pt', 0)).replace('.', ',')}/1 · mesure moteur {str(breakdown.get('booking_engine_measurement_1pt', 0)).replace('.', ',')}/1 · événement e-commerce {str(breakdown.get('booking_funnel_event_1pt', 0)).replace('.', ',')}/1 · achat confirmé {str(breakdown.get('confirmed_purchase_5pts', 0)).replace('.', ',')}/5")
    return header(f"{row['name']} — Audit de taggage", f"Audit public du tracking de {row['name']} à {row['city']}, réalisé le {TODAY}.", True)+f'''  <main id="main-content" class="camping-detail">
    <p class="breadcrumb"><a href="../../index.html">Tous les campings</a> <span>/</span> {esc(row["name"])}</p>
    <div class="detail-heading">
      <div><p class="eyebrow">Camping 5 étoiles · Rapport public</p><h1>{esc(row["name"])}</h1><p class="location-big">📍 {esc(location)}</p></div>
      <a class="source-link" href="{esc(row['source_url'])}" rel="nofollow noopener" target="_blank">Visiter le site ↗</a>
    </div>
    <section class="score-big {score_class(score)}" aria-label="Score de suivi des réservations">
      <div class="number">{score_text}<span>/10</span></div>
      <div class="meta"><p class="eyebrow">Note de suivi de réservation</p><h2>{esc(status_text)}</h2><p>Cette note valorise les événements du parcours ; les outils installés seuls ne suffisent pas. Aucun achat réel n'a été effectué, donc la note est plafonnée à 5/10.</p><div class="score-track"><span style="width:{0 if score is None else min(100,int(score*10))}%"></span></div></div>
    </section>
    <div class="notice"><strong>Ancien score de présence des outils :</strong> {esc(legacy_text)}. Il n'est pas comparable directement à la note de réservation affichée ci-dessus. Un score bas signifie que le suivi n'a pas été démontré dans ce parcours public ; ce n'est pas une preuve absolue de l'absence d'une configuration interne.</div>
    <section class="panel journey-panel"><p class="eyebrow">Repassage navigateur · {TODAY}</p><h2>Suivi du parcours de réservation</h2><p class="data-summary">{esc(journey_summary)}</p><div class="journey-metrics"><div><strong>Interaction de réservation mesurée</strong><span>{esc(interaction)}</span></div><div><strong>Mesure observée sur le moteur</strong><span>{esc(engine_hit)}</span></div><div><strong>Événements e-commerce</strong><span>{esc(funnel_text)}</span></div><div><strong>Achat final</strong><span>{esc(purchase_text)}</span></div></div>{false_notice}<p class="small">Décomposition : {esc(breakdown_text)}. Un événement `purchase` n'est valide que si une transaction confirmée, un identifiant, une valeur positive, une devise et des envois GA4/Google Ads uniques sont démontrés.</p></section>
    <section><div class="section-heading"><p class="eyebrow">Diagnostic technique</p><h2>Outils détectés sur le site</h2></div><div class="audit-grid">{tool_html}</div></section>
    <section class="panel evidence-panel"><p class="eyebrow">Preuves observées</p><h2>Ce qui a été réellement constaté</h2><ul class="issue-list">{evidence_html}</ul></section>
    <div class="detail-columns">
      <section class="panel"><p class="eyebrow">Problèmes à traiter</p><h2>Les points d’attention</h2><ul class="issue-list">{issue_html}</ul></section>
      <section class="panel"><p class="eyebrow">Plan d’action</p><h2>Les prochaines étapes</h2><ol class="action-list">{action_html}</ol></section>
    </div>
    <div class="detail-columns">
      <section class="panel"><p class="eyebrow">Identifiants publics</p><h2>Outils repérés</h2>{id_html}</section>
      <section class="panel"><p class="eyebrow">Réservation & dataLayer</p><h2>Parcours à fiabiliser</h2><p class="data-summary"><strong>Événements :</strong> {esc(events)}</p><ul class="link-list">{booking}</ul></section>
    </div>
    <section class="method-note"><p class="eyebrow">Périmètre et limites</p><h2>À savoir avant de décider</h2><ul>{limit_html}</ul><p class="small">URL testée : <code>{esc(row['browse_url'])}</code> · Contrôle du {TODAY}.</p></section>
    <section class="cta-block"><p class="eyebrow">Besoin d’un tracking qui travaille vraiment pour vos réservations ?</p><h2>Escale Ads peut le remettre au propre.</h2><p>Plan de taggage, Consent Mode, conversions Google Ads et tests du tunnel de réservation.</p><div class="price">499 €</div><p class="price-sub">Audit complet et accompagnement de mise en conformité</p><a class="cta-button" href="mailto:contact@escale-ads.com?subject=Audit%20taggage%20—%20{esc(row['name'])}">Demander un accompagnement</a></section>
  </main>
'''+footer(True)


def card(row: dict) -> str:
    score=row["score"]
    display="—" if score is None else (str(int(score)) if score.is_integer() else str(score).replace(".", ","))
    status="Non vérifiable" if score is None else ("Suivi non démontré" if score < 2 else "Partiel" if score < 4 else "À valider")
    badge="badge-na" if score is None else "badge-low" if score < 2 else "badge-mid"
    search=slugify(f"{row['name']} {row['city']} {region_for(row['postal_code'])}")
    return f'''<a class="camping-card" href="campings/{esc(row['slug'])}/" data-name="{esc(search)}" data-region="{esc(region_for(row['postal_code']))}" data-score="{esc('na' if score is None else str(int(score)))}">
  <div class="card-top"><span class="card-index">#{int(row['row']):03d}</span><span class="stars" aria-label="5 étoiles">★★★★★</span></div>
  <div class="card-body"><h3>{esc(row['name'])}</h3><div class="location">📍 {esc(row['city'])} · {esc(row['postal_code'])} · {esc(region_for(row['postal_code']))}</div><p class="card-tool-line">{esc(' · '.join(x for x in [f'GTM {len(row["gtm_ids"])}' if row["gtm_ids"] else 'Sans GTM', f'GA4 {len(row["ga4_ids"])}' if row["ga4_ids"] else 'Sans GA4', 'CMP détectée' if row["consent_detected"] else 'CMP non détectée'] if x))}</p></div>
  <div class="card-footer"><div class="mini-score"><span class="score-number">{display}</span><span class="score-denom">/10</span><span class="score-label">{esc(status)}</span></div><span class="status-badge {badge}">Voir le rapport&nbsp;↗</span></div>
</a>'''


def homepage(rows: list[dict]) -> str:
    verified=[r for r in rows if r["score"] is not None]
    scores=[r["score"] for r in verified]
    avg=(sum(scores)/len(scores)) if scores else 0
    non_verifiable=len(rows)-len(verified)
    false_purchase=sum(bool(r.get("invalid_google_ads_purchase")) for r in rows)
    booking_entries=sum(bool(r.get("booking_entry_reached")) for r in rows)
    regions=sorted({region_for(r["postal_code"]) for r in rows})
    options="".join(f'<option value="{esc(r)}">{esc(r)}</option>' for r in regions)
    cards="\n".join(card(r) for r in rows)
    return header("Audit de taggage des campings 5 étoiles | Escale Ads", "Découvrez l’état public du tracking des campings 5 étoiles en France : GTM, GA4, Google Ads, consentement et Meta Pixel.")+f'''  <main id="main-content">
    <section class="hero"><div class="hero-inner"><p class="eyebrow light">Observatoire du tracking touristique</p><h1>Votre camping est-il vraiment en mesure de <span>mesurer ses réservations&nbsp;?</span></h1><p class="hero-lead">Nous avons contrôlé les signaux publics du taggage et simulé les parcours de réservation des campings 5 étoiles en France. La note privilégie désormais les preuves d'étapes et d'achat, pas la seule présence d'identifiants.</p><div class="hero-actions"><a class="hero-cta" href="#campings">Explorer les audits <span>↓</span></a><a class="hero-secondary" href="#offre">Voir l’accompagnement à 499 €</a></div><p class="hero-footnote">283 parcours simulés · aucune réservation réelle · aucun paiement</p></div></section>
    <section class="stats-wrap"><div class="stats-bar"><div class="stat-item"><strong>{len(rows)}</strong><span>campings contrôlés</span></div><div class="stat-item"><strong>{len(verified)}</strong><span>scores calculés · {non_verifiable} non vérifiables</span></div><div class="stat-item"><strong>{f'{avg:.1f}'.replace('.', ',')}</strong><span>moyenne du suivi de réservation /10</span></div><div class="stat-item"><strong>{false_purchase}</strong><span>campings avec faux purchase Ads à 0 €</span></div></div></section>
    <section class="section intro"><div class="section-heading"><p class="eyebrow">Pourquoi cet audit</p><h2>Le bon outil n’est pas suffisant.</h2></div><div class="how-grid"><article class="how-card"><span class="step">01</span><h3>Voir les signaux</h3><p>GTM, GA4, Google Ads, Meta, Bing et les mécanismes de consentement réellement visibles depuis le site.</p></article><article class="how-card"><span class="step">02</span><h3>Comprendre le risque</h3><p>Un identifiant présent ne garantit pas qu’une réservation ou qu’un consentement soit correctement mesuré.</p></article><article class="how-card"><span class="step">03</span><h3>Agir dans l’ordre</h3><p>Chaque rapport met en avant les corrections qui protègent les données et les décisions d’acquisition.</p></article></div></section>
    <section id="campings" class="section listing"><div class="section-heading"><p class="eyebrow">Les rapports</p><h2>Campings audités</h2><p>Recherchez un établissement ou filtrez par région et niveau de preuve.</p></div><div class="filter-bar"><label class="sr-only" for="filter-camping">Rechercher un camping</label><input type="search" id="filter-camping" placeholder="Rechercher un camping, une ville…"><label class="sr-only" for="filter-region">Filtrer par région</label><select id="filter-region"><option value="all">Toutes les régions</option>{options}</select><label class="sr-only" for="filter-score">Filtrer par score</label><select id="filter-score"><option value="all">Tous les scores</option><option value="low">Suivi non démontré · 0–1</option><option value="mid">Parcours partiel · 2–3</option><option value="high">Étapes visibles · 4–5 (achat non validé)</option><option value="na">Non vérifiable</option></select><span id="results-count" role="status">{len(rows)} campings</span></div><div class="camping-grid">{cards}</div><p id="empty-state" class="empty-state" hidden>Aucun camping ne correspond à votre recherche.</p></section>
    <section id="offre" class="section offer-section"><div class="cta-block"><p class="eyebrow light">Passer de l’observation à la mesure fiable</p><h2>On remet votre tracking au propre.</h2><p>Plan de taggage, Consent Mode, conversions Google Ads, suivi de réservation et recette des données — avec un périmètre clair.</p><div class="price">499 €</div><p class="price-sub">pour l’audit complet et l’accompagnement de mise en œuvre</p><a class="cta-button" href="mailto:contact@escale-ads.com?subject=Audit%20taggage%20camping%205%20étoiles">Parler à Escale Ads&nbsp;↗</a></div></section>
    <section class="section methodology"><p class="eyebrow">Méthode révisée · {TODAY}</p><h2>La preuve de réservation pèse le plus.</h2><p>La note /10 attribue au plus 2 points aux outils et au consentement, 3 aux interactions et événements réellement observés dans le tunnel, et 5 à un achat confirmé une seule fois avec transaction_id, valeur positive, devise, GA4 et Google Ads. Un faux purchase Ads à 0 € avant commande retire 3 points. Les achats réels n'ayant pas été effectués, tous les scores sont plafonnés à 5/10 ; les parcours bloqués ou fermés sont signalés comme non vérifiables, pas comme preuve absolue d'absence de tracking. L'ancienne moyenne de présence des outils était de 7,34/10 ; la moyenne actuelle du suivi de réservation est de {f'{avg:.2f}'.replace('.', ',')}/10 sur {len(verified)} fiches notées. {booking_entries} entrées vers un parcours de réservation ont été atteintes ; aucun événement e-commerce n'a été observé.</p></section>
  </main>
'''+footer(False)


def main() -> None:
    rows=load_results()
    PAGES.mkdir(exist_ok=True)
    for row in rows:
        folder=PAGES / row["slug"]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "index.html").write_text(detail_page(row), encoding="utf-8")
    (ROOT / "index.html").write_text(homepage(rows), encoding="utf-8")
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "audits.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated {len(rows)} detail pages and homepage")
    print(f"Verified pages: {sum(r['score'] is not None for r in rows)}")
    print(f"Not verifiable: {sum(r['score'] is None for r in rows)}")


if __name__ == "__main__":
    main()
