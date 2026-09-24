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
BOOKING_URL = "https://calendly.com/escaleads/30min?utm_source=audit-camping&utm_medium=site&utm_campaign=plan-de-taggage"

REGIONS = {
    "01": "Auvergne-Rhône-Alpes", "02": "Hauts-de-France", "03": "Auvergne-Rhône-Alpes", "04": "Provence-Alpes-Côte d’Azur", "05": "Provence-Alpes-Côte d’Azur", "06": "Provence-Alpes-Côte d’Azur", "07": "Auvergne-Rhône-Alpes", "08": "Grand Est", "09": "Occitanie", "10": "Grand Est", "11": "Occitanie", "12": "Occitanie", "13": "Provence-Alpes-Côte d’Azur", "14": "Normandie", "15": "Auvergne-Rhône-Alpes", "16": "Nouvelle-Aquitaine", "17": "Nouvelle-Aquitaine", "18": "Centre-Val de Loire", "19": "Nouvelle-Aquitaine", "20": "Corse", "21": "Bourgogne-Franche-Comté", "22": "Bretagne", "23": "Nouvelle-Aquitaine", "24": "Nouvelle-Aquitaine", "25": "Bourgogne-Franche-Comté", "26": "Auvergne-Rhône-Alpes", "27": "Normandie", "28": "Centre-Val de Loire", "29": "Bretagne", "30": "Occitanie", "31": "Occitanie", "32": "Occitanie", "33": "Nouvelle-Aquitaine", "34": "Occitanie", "35": "Bretagne", "36": "Centre-Val de Loire", "37": "Centre-Val de Loire", "38": "Auvergne-Rhône-Alpes", "39": "Bourgogne-Franche-Comté", "40": "Nouvelle-Aquitaine", "41": "Centre-Val de Loire", "42": "Auvergne-Rhône-Alpes", "43": "Auvergne-Rhône-Alpes", "44": "Pays de la Loire", "45": "Centre-Val de Loire", "46": "Occitanie", "47": "Nouvelle-Aquitaine", "48": "Occitanie", "49": "Pays de la Loire", "50": "Normandie", "51": "Grand Est", "52": "Grand Est", "53": "Pays de la Loire", "54": "Grand Est", "55": "Grand Est", "56": "Bretagne", "57": "Grand Est", "58": "Bourgogne-Franche-Comté", "59": "Hauts-de-France", "60": "Hauts-de-France", "61": "Normandie", "62": "Hauts-de-France", "63": "Auvergne-Rhône-Alpes", "64": "Nouvelle-Aquitaine", "65": "Occitanie", "66": "Occitanie", "67": "Grand Est", "68": "Grand Est", "69": "Auvergne-Rhône-Alpes", "70": "Bourgogne-Franche-Comté", "71": "Bourgogne-Franche-Comté", "72": "Pays de la Loire", "73": "Auvergne-Rhône-Alpes", "74": "Auvergne-Rhône-Alpes", "75": "Île-de-France", "76": "Normandie", "77": "Île-de-France", "78": "Île-de-France", "79": "Nouvelle-Aquitaine", "80": "Hauts-de-France", "81": "Occitanie", "82": "Occitanie", "83": "Provence-Alpes-Côte d’Azur", "84": "Provence-Alpes-Côte d’Azur", "85": "Pays de la Loire", "86": "Nouvelle-Aquitaine", "87": "Nouvelle-Aquitaine", "88": "Grand Est", "89": "Bourgogne-Franche-Comté", "90": "Bourgogne-Franche-Comté", "91": "Île-de-France", "92": "Île-de-France", "93": "Île-de-France", "94": "Île-de-France", "95": "Île-de-France"
}


def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def text(value) -> str:
    return str(value or "").strip()


def external_href(value) -> str:
    raw = text(value)
    return "https://" + raw if raw.lower().startswith("www.") else raw


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
    provided = row.get("score")
    if row.get("score_model") == "reservation_tracking_v3":
        return float(provided) if isinstance(provided, (int, float)) else None
    if text(row.get("status")).lower() not in {"ok", "success", "loaded"}:
        return None
    if isinstance(provided, (int, float)):
        return float(provided)
    ids = {key: as_list(row.get(key)) for key in ("gtm_ids", "ga4_ids", "google_ads_ids", "meta_pixel_ids", "bing_uet_ids")}
    consent = bool(row.get("consent_detected"))
    value = (3 if ids["gtm_ids"] else 0) + (2 if ids["ga4_ids"] else 0) + (2 if ids["google_ads_ids"] else 0) + (2 if consent else 0) + (1 if ids["meta_pixel_ids"] else 0)
    return float(value)


def score_label(score: float | None, row: dict | None = None) -> str:
    row = row or {}
    if score is None:
        if row.get("score_status") == "insufficient_coverage":
            return "Couverture insuffisante"
        return "Non vérifiable"
    if score < 2:
        return "Suivi non démontré"
    if score < 4:
        return "Suivi faible"
    if score < 6:
        return "Suivi partiel"
    if score < 8:
        return "Suivi observable"
    purchase_status = row.get("purchase_validation_status", "not_tested")
    if purchase_status == "validated":
        return "Suivi bien observable · achat validé"
    if purchase_status in {"defect_observed", "test_failed"}:
        return "Suivi observable · alerte achat"
    return "Suivi bien observable · achat à valider"


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
    anchors=f"{prefix}index.html" if detail else ""
    return f'''<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="theme-color" content="#082b52">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{prefix}assets/css/style.css">
  <link rel="stylesheet" href="{prefix}assets/css/redesign.css">
</head>
<body>
  <a class="skip-link" href="#main-content">Aller au contenu</a>
  <header class="site-header">
    <a class="logo" href="{prefix}index.html" aria-label="Accueil de l’observatoire Escale Ads"><img src="{prefix}assets/images/logo-escale-ads.png" alt="Escale Ads" width="112" height="43"><span class="brand-divider" aria-hidden="true"></span><span class="brand-label">Observatoire<br>Camping</span></a>
    <nav class="header-nav" aria-label="Navigation principale"><a href="{anchors}#classements">Classements</a><a href="{anchors}#campings">Les audits</a><a href="{anchors}#offre">Le plan de taggage</a></nav>
    <a class="header-cta" href="{esc(BOOKING_URL)}" target="_blank" rel="noopener noreferrer">Parler du taggage <span aria-hidden="true">↗</span></a>
  </header>
'''


def footer(detail: bool=False) -> str:
    prefix=nav(detail)
    anchors=f"{prefix}index.html" if detail else ""
    return f'''  <footer class="site-footer">
    <div class="footer-layout"><div><strong>Escale Ads <span>×</span> Audit Camping</strong><p>Des signaux observés, des limites explicites, un plan de taggage pour décider.</p></div><nav aria-label="Navigation de pied de page"><a href="{anchors}#classements">Classements</a><a href="{anchors}#campings">Les audits</a><a href="{anchors}#offre">Le plan de taggage</a><a href="mailto:florent@escale-ads.com?subject=Plan%20de%20taggage%20camping">Contact</a></nav></div>
    <p class="powered">Observation publique du {TODAY} · Aucun achat final testé · <a href="https://escale-ads.com/" target="_blank" rel="noopener noreferrer">escale-ads.com ↗</a></p>
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
    status_text=score_label(score, row)
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
    booking="".join(f"<li><a href=\"{esc(external_href(url))}\" rel=\"nofollow noopener\">{esc(url)}</a></li>" for url in row["booking_links"][:5]) or '<li>Aucun lien de réservation identifiable dans la page observée.</li>'
    historical_limits=[item for item in row["limitations"] if "2026-09-14" not in item and "une seule visite par site" not in item.lower() and "sans réservation ni paiement réel" not in item.lower()]
    limitations=unique(["Parcours simulé jusqu'aux disponibilités ou à la liste d'hébergements ; aucune réservation, validation ou paiement réel.", "Sans transaction réelle ou environnement de recette, le déclenchement final d'un purchase reste non vérifié."] + historical_limits)
    limit_html="".join(f"<li>{esc(item)}</li>" for item in limitations[:6])
    breakdown=row.get("score_breakdown", {})
    journey_labels={"ok":"Parcours public accessible ; achat final non testé.", "blocked":"Tunnel bloqué ou inaccessible ; suivi au-delà non vérifiable.", "booking_closed":"Réservations en ligne fermées au moment du test.", "partial_manual":"Recherche et liste d'hébergements atteintes ; arrêt avant choix d'une offre."}
    journey_summary=text(row.get("journey_verdict")) or journey_labels.get(row.get("journey_status"), "Parcours non vérifiable.")
    interaction="Observée" if row.get("booking_interaction_tracked") else "Non observée"
    engine_hit="Observé" if row.get("booking_engine_measurement_observed") else "Non observé"
    funnel_text=" · ".join(funnel_events) if funnel_events else "Aucun événement e-commerce spécifique observé"
    purchase_status_labels={"not_tested":"Non testé — aucune transaction de recette autorisée effectuée", "validated":"Validé en environnement de recette autorisé", "test_failed":"Test de recette incomplet ou non conforme", "defect_observed":"Défaut critique observé ; achat valide non démontré"}
    purchase_text=purchase_status_labels.get(row.get("purchase_validation_status", "not_tested"), "Non testé")
    coverage_pct=int(row.get("score_coverage_pct", 0) or 0)
    assessed_points=row.get("score_assessed_points", 0) or 0
    earned_points=row.get("score_obtained_points", 0) or 0
    coverage_text=f"Couverture des critères pré-transaction : {coverage_pct}% ({str(earned_points).replace('.', ',')}/{str(assessed_points).replace('.', ',')} points évalués)."
    component_labels={"measurement_setup":"Base de mesure", "booking_interaction":"Interaction réservation", "booking_engine":"Moteur de réservation", "availability_event":"Disponibilités", "offer_event":"Offre", "event_name_quality":"Noms d’événements", "single_delivery_observed":"Envoi sans doublon observé"}
    breakdown_parts=[]
    for key, component in breakdown.items():
        if not component.get("assessed"):
            value="non évalué"
        else:
            value=f"{str(component.get('points', 0)).replace('.', ',')}/{str(component.get('max_points', 0)).replace('.', ',')}"
        breakdown_parts.append(f"{component_labels.get(key, key)} : {value}")
    breakdown_text=" · ".join(breakdown_parts)
    legacy_score=row.get("tag_presence_score")
    legacy_text="Non vérifiable" if legacy_score is None else f"{str(legacy_score).replace('.', ',')}/10"
    false_count=int(row.get("invalid_purchase_hit_count", 0) or 0)
    false_notice=(f'<p class="journey-alert"><strong>Signal critique :</strong> {false_count} hit(s) Google Ads étiqueté(s) purchase émis sans preuve de succès transactionnel confirmé ou avec des champs incomplets.</p>' if row.get("invalid_google_ads_purchase") else "")
    return header(f"{row['name']} — Audit de taggage", f"Audit public du tracking de {row['name']} à {row['city']}, réalisé le {TODAY}.", True)+f'''  <main id="main-content" class="camping-detail">
    <p class="breadcrumb"><a href="../../index.html">Tous les campings</a> <span>/</span> {esc(row["name"])}</p>
    <div class="detail-heading">
      <div><p class="eyebrow">Camping 5 étoiles · Rapport public</p><h1>{esc(row["name"])}</h1><p class="location-big">📍 {esc(location)}</p></div>
      <a class="source-link" href="{esc(external_href(row['source_url']))}" rel="nofollow noopener" target="_blank">Visiter le site ↗</a>
    </div>
    <section class="score-big {score_class(score)}" aria-label="Score de suivi des réservations">
      <div class="number">{score_text}<span>/10</span></div>
      <div class="meta"><p class="eyebrow">Score de suivi observable pré-transaction</p><h2>{esc(status_text)}</h2><p>Les critères non atteints ou non observés ne sont pas assimilés automatiquement à des défaillances. Le score est calculé sur les critères évaluables ; la couverture est affichée séparément.</p><p class="small">{esc(coverage_text)} L’achat final est évalué dans un statut distinct.</p><div class="score-track"><span style="width:{0 if score is None else min(100,int(score*10))}%"></span></div></div>
    </section>
    <div class="notice"><strong>Ancien score de présence des outils :</strong> {esc(legacy_text)}. Il n'est pas comparable directement à la note de réservation affichée ci-dessus. Un score bas signifie que le suivi n'a pas été démontré dans ce parcours public ; ce n'est pas une preuve absolue de l'absence d'une configuration interne.</div>
    <section class="panel journey-panel"><p class="eyebrow">Repassage navigateur · {TODAY}</p><h2>Suivi du parcours de réservation</h2><p class="data-summary">{esc(journey_summary)}</p><div class="journey-metrics"><div><strong>Interaction de réservation mesurée</strong><span>{esc(interaction)}</span></div><div><strong>Mesure observée sur le moteur</strong><span>{esc(engine_hit)}</span></div><div><strong>Événements e-commerce</strong><span>{esc(funnel_text)}</span></div><div><strong>Statut de l’achat</strong><span>{esc(purchase_text)}</span></div></div>{false_notice}<p class="small">Décomposition du score : {esc(breakdown_text)}. Le statut « Validé » exige un hit GA4 capturé après un succès autorisé, un seul purchase, transaction_id, valeur positive, devise, envoi Google Ads et absence de doublon.</p></section>
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
    <section class="cta-block"><p class="eyebrow light">Du diagnostic public au plan d’action</p><h2>Le prochain pas pour votre suivi de réservation.</h2><p>Plan de taggage, Consent Mode, conversions Google Ads et recette du tunnel — sur un périmètre défini avec vous.</p><div class="price">499 €</div><p class="price-sub">Audit complet et accompagnement de mise en œuvre</p><a class="cta-button" href="{esc(BOOKING_URL)}" target="_blank" rel="noopener noreferrer">Parler de mon plan de taggage <span aria-hidden="true">↗</span></a></section>
  </main>
'''+footer(True)


def card(row: dict) -> str:
    score=row["score"]
    display="—" if score is None else (str(int(score)) if score.is_integer() else str(score).replace(".", ","))
    status=score_label(score,row)
    critical_purchase=bool(row.get("invalid_google_ads_purchase"))
    badge="badge-low" if critical_purchase else "badge-na" if score is None else "badge-low" if score < 4 else "badge-mid" if score < 8 else "badge-high"
    report_label="Alerte purchase critique ↗" if critical_purchase else "Voir le rapport ↗"
    search=slugify(f"{row['name']} {row['city']} {region_for(row['postal_code'])}")
    return f'''<a class="camping-card" href="campings/{esc(row['slug'])}/" data-name="{esc(search)}" data-region="{esc(region_for(row['postal_code']))}" data-score="{esc('na' if score is None else str(int(score)))}" data-critical="{'true' if critical_purchase else 'false'}">
  <div class="card-top"><span class="card-index">#{int(row['row']):03d}</span><span class="stars" aria-label="5 étoiles">★★★★★</span></div>
  <div class="card-body"><h3>{esc(row['name'])}</h3><div class="location">📍 {esc(row['city'])} · {esc(row['postal_code'])} · {esc(region_for(row['postal_code']))}</div><p class="card-tool-line">{esc(' · '.join(x for x in [f'GTM {len(row["gtm_ids"])}' if row["gtm_ids"] else 'Sans GTM', f'GA4 {len(row["ga4_ids"])}' if row["ga4_ids"] else 'Sans GA4', 'CMP détectée' if row["consent_detected"] else 'CMP non détectée'] if x))}</p></div>
  <div class="card-footer"><div class="mini-score"><span class="score-number">{display}</span><span class="score-denom">/10</span><span class="score-label">{esc(status)}</span></div><span class="status-badge {badge}">{esc(report_label)}</span></div>
</a>'''


def ranked_campings(rows: list[dict], limit: int = 10) -> tuple[list[dict], list[dict]]:
    eligible = [row for row in rows if row.get("score_model") == "reservation_tracking_v3"
                and row.get("score_status") == "scored"
                and isinstance(row.get("score"), (int, float))
                and int(row.get("score_coverage_pct", 0) or 0) >= 60]
    best = sorted((row for row in eligible if not row.get("invalid_google_ads_purchase")),
                  key=lambda row: (-row["score"], -int(row["score_coverage_pct"]), int(row["row"])))[:limit]
    best_ids = {int(row["row"]) for row in best}
    worst = sorted((row for row in eligible if int(row["row"]) not in best_ids),
                   key=lambda row: (row["score"], -bool(row.get("invalid_google_ads_purchase")),
                                    -int(row["score_coverage_pct"]), int(row["row"])))[:limit]
    return best, worst


def ranking_entry(row: dict, position: int, kind: str) -> str:
    score = float(row["score"])
    display = str(int(score)) if score.is_integer() else str(score).replace(".", ",")
    region = region_for(row["postal_code"])
    alert = '<span class="rank-alert">Alerte purchase</span>' if row.get("invalid_google_ads_purchase") else ""
    return (f'<li class="rank-entry" data-ranking="{kind}" data-row="{int(row["row"])}">'
            f'<a href="campings/{esc(row["slug"])}/">'
            f'<span class="rank-position">{position:02d}</span>'
            f'<span class="rank-identity"><strong>{esc(row["name"])}</strong><small>{esc(row["city"])} · {esc(region)}</small>{alert}</span>'
            f'<span class="rank-value"><strong>{esc(display)}<small>/10</small></strong><small>Couverture {int(row["score_coverage_pct"])} %</small></span>'
            '</a></li>')


def homepage(rows: list[dict]) -> str:
    verified=[r for r in rows if r["score"] is not None]
    scores=[r["score"] for r in verified]
    avg=(sum(scores)/len(scores)) if scores else 0
    not_scored=len(rows)-len(verified)
    insufficient_coverage=sum(r.get("score_status")=="insufficient_coverage" for r in rows)
    false_purchase=sum(bool(r.get("invalid_google_ads_purchase")) for r in rows)
    booking_entries=sum(bool(r.get("booking_entry_reached")) for r in rows)
    regions=sorted({region_for(r["postal_code"]) for r in rows})
    options="".join(f'<option value="{esc(r)}">{esc(r)}</option>' for r in regions)
    cards="\n".join(card(r) for r in rows)
    best, worst = ranked_campings(rows)
    best_html = "".join(ranking_entry(row, position, "best") for position, row in enumerate(best, 1))
    worst_html = "".join(ranking_entry(row, position, "worst") for position, row in enumerate(worst, 1))
    return header("Audit de taggage des campings 5 étoiles | Escale Ads", "Découvrez l’état public du tracking des campings 5 étoiles en France : GTM, GA4, Google Ads, consentement et Meta Pixel.")+f'''  <main id="main-content">
    <section class="hero"><div class="hero-inner"><div class="hero-copy"><p class="eyebrow light">Le plan de taggage des campings qui vendent en direct</p><h1>Votre moteur réserve. <span>Vos campagnes le savent-elles&nbsp;?</span></h1><p class="hero-lead">Un clic sur « Réserver » n’est pas une vente mesurée. Après l’analyse publique de 283 parcours, nous vous aidons à bâtir le plan de taggage qui relie site, moteur, GA4 et Google Ads — sans confondre intention et achat confirmé.</p><div class="hero-actions"><a class="hero-cta" href="{esc(BOOKING_URL)}" target="_blank" rel="noopener noreferrer">Parler de mon plan de taggage <span aria-hidden="true">↗</span></a><a class="hero-secondary" href="#campings">Trouver mon camping <span aria-hidden="true">↓</span></a></div><p class="hero-footnote">Échange de 30 minutes · Audit public sans réservation ni paiement réels</p></div><aside class="signal-panel" aria-label="Parcours type à instrumenter"><div class="signal-panel-top"><span class="signal-live" aria-hidden="true"></span> PARCOURS À RELIER <span>01—04</span></div><ol class="signal-steps"><li><span class="signal-index">01</span><span>Visite du site<small>La première intention</small></span><span class="signal-arrow" aria-hidden="true">↘</span></li><li><span class="signal-index">02</span><span>Clic « Réserver »<small>Le départ vers le moteur</small></span><span class="signal-arrow" aria-hidden="true">↘</span></li><li><span class="signal-index">03</span><span>Choix de séjour<small>Disponibilité et offre</small></span><span class="signal-arrow" aria-hidden="true">↘</span></li><li class="signal-final"><span class="signal-index">04</span><span>Réservation confirmée<small>À valider en recette autorisée</small></span><span class="signal-state">Non testée</span></li></ol><p class="signal-caption">Schéma du plan de taggage, pas le résultat d’un camping audité.</p></aside></div></section>
    <section class="stats-wrap" aria-label="Chiffres de l’audit"><div class="stats-bar"><div class="stat-item"><strong>{len(rows)}</strong><span>campings examinés</span></div><div class="stat-item"><strong>{len(verified)}</strong><span>scores avec couverture suffisante</span></div><div class="stat-item stat-alert"><strong>{false_purchase}</strong><a href="#campings" data-filter-alerts>signalements purchase à examiner <span aria-hidden="true">↗</span></a></div><div class="stat-item"><strong>0</strong><span>achat final testé ou validé</span></div></div></section>
    <section id="classements" class="section rankings" aria-labelledby="rankings-title"><div class="section-heading"><p class="eyebrow">Classements de mesure</p><h2 id="rankings-title">Top 10 &amp; Bas 10 du suivi observable</h2><p>Ce classement porte uniquement sur le tracking pré-transaction, jamais sur la qualité des campings. Les achats réels n’ont pas été testés.</p></div><div class="rankings-grid"><div class="ranking-panel ranking-best"><div class="ranking-heading"><span>01 / 02</span><h3>Les 10 suivis les mieux observés</h3><p>Notes les plus élevées, sans signal purchase critique.</p></div><ol class="ranking-list">{best_html}</ol></div><div class="ranking-panel ranking-worst"><div class="ranking-heading"><span>02 / 02</span><h3>Les 10 suivis les moins démontrés</h3><p>Notes les plus basses parmi les parcours suffisamment couverts.</p></div><ol class="ranking-list">{worst_html}</ol></div></div><p class="ranking-method">Éligibilité : score v3 calculé et couverture d’au moins 60 %. Top 10 : note décroissante, sans alerte purchase critique ; Bas 10 : note croissante, puis alerte critique, couverture et numéro de fiche en cas d’égalité. Aucune réservation finale n’a été testée. <a href="#methode">Comprendre la méthode ↗</a></p></section>
    <section class="section intro"><div class="insight-layout"><div class="insight-copy"><p class="eyebrow">Le vrai sujet</p><h2>Des tags présents. <em>Mais les ventes&nbsp;?</em></h2><p>Un identifiant GTM ou GA4 ne prouve pas que le passage vers le moteur, le choix du séjour et la confirmation remontent correctement. Nos rapports publics indiquent où regarder ; la validation d’une conversion exige une recette autorisée.</p><a class="text-link" href="#offre">Découvrir le plan de taggage <span aria-hidden="true">↗</span></a></div><div class="insight-list"><div><span>01 / DIAGNOSTIC</span><h3>Identifier la rupture</h3><p>Site, clic de réservation, moteur externe : on sépare les preuves des simples indices.</p></div><div><span>02 / PLAN</span><h3>Définir les bons événements</h3><p>Le plan de taggage précise ce qui doit être mesuré et transmis à GA4 et Google Ads.</p></div><div><span>03 / RECETTE</span><h3>Valider sans inventer de ventes</h3><p>La transaction finale reste non validée tant qu’un test autorisé ne l’a pas démontrée.</p></div></div></div></section>
    <details id="campings" class="section listing"><summary class="listing-summary"><span class="listing-summary-kicker">L’observatoire complet</span><strong>Retrouvez votre camping parmi les {len(rows)} audits</strong><span class="listing-summary-action">Ouvrir le catalogue <span aria-hidden="true">↗</span></span></summary><div class="section-heading"><p class="eyebrow">Les rapports</p><h2>Campings audités</h2><p>Recherchez un établissement ou filtrez par région et niveau de preuve.</p></div><div class="filter-bar"><label class="sr-only" for="filter-camping">Rechercher un camping</label><input type="search" id="filter-camping" placeholder="Rechercher un camping, une ville…"><label class="sr-only" for="filter-region">Filtrer par région</label><select id="filter-region"><option value="all">Toutes les régions</option>{options}</select><label class="sr-only" for="filter-score">Filtrer par score</label><select id="filter-score"><option value="all">Tous les scores</option><option value="low">Peu de preuves · 0–1</option><option value="mid">Suivi partiel · 2–3</option><option value="high">Suivi observable · 4–10</option><option value="na">Couverture insuffisante / non vérifiable</option><option value="critical">Alerte purchase critique</option></select><span id="results-count" role="status">{len(rows)} campings</span></div><div class="camping-grid">{cards}</div><p id="empty-state" class="empty-state" hidden>Aucun camping ne correspond à votre recherche.</p></details>
    <section id="offre" class="section offer-section"><div class="offer-frame"><div class="offer-copy"><p class="eyebrow light">L’offre Escale Ads</p><h2>Un plan de taggage qui va jusqu’au moteur de réservation.</h2><p>Le rapport public est un point de départ. L’audit complet et l’accompagnement donnent un périmètre de mise en œuvre pour fiabiliser vos décisions d’acquisition.</p><p class="offer-inline-price">Audit complet + accompagnement · 499 €</p><a class="offer-quicklink" href="{esc(BOOKING_URL)}" target="_blank" rel="noopener noreferrer">Échanger 30 min sur mon plan <span aria-hidden="true">↗</span></a><ul class="offer-deliverables"><li>Cartographier le parcours entre le site et le moteur</li><li>Définir les événements utiles pour GA4 et Google Ads</li><li>Prévoir Consent Mode, conversions et recette des données</li></ul><p class="offer-honesty">L’achat final ne peut être déclaré validé qu’après un test autorisé ; cet observatoire n’en a réalisé aucun.</p></div><aside class="offer-card" aria-label="Tarif et prise de rendez-vous"><span class="offer-card-top">Audit complet + accompagnement</span><strong class="price">499 €</strong><p class="price-sub">pour l’audit complet et l’accompagnement de mise en œuvre, selon le périmètre défini ensemble</p><a class="cta-button" href="{esc(BOOKING_URL)}" target="_blank" rel="noopener noreferrer">Échanger 30 min sur mon plan <span aria-hidden="true">↗</span></a><p class="offer-microcopy">Un échange pour cadrer votre besoin, sans accès à vos comptes à cette étape.</p><a class="offer-email" href="mailto:florent@escale-ads.com?subject=Plan%20de%20taggage%20camping">Ou écrire à Florent <span aria-hidden="true">↗</span></a></aside></div></section>
    <section id="methode" class="section methodology"><p class="eyebrow">Méthode v3 · {TODAY}</p><h2>La note mesure un parcours. Pas des ventes.</h2><p class="method-lead">Seul le suivi observable avant achat est noté. La couverture et le statut d’achat sont affichés à part ; une transaction non testée n’est jamais déclarée validée. Le classement exige une couverture d’au moins 60 %.</p><details class="method-disclosure"><summary>Lire le barème détaillé <span aria-hidden="true">↓</span></summary><p>Le score /10 mesure le suivi observable avant transaction : base de mesure (2 pts), interaction au CTA (2), mesure sur le moteur (2), événements disponibilité/offre (2) et qualité des événements observés (2). Il est normalisé sur les seuls critères évaluables ; les étapes non atteintes ne sont pas traitées comme des échecs. La couverture est affichée, et aucun score n’est publié si moins de 5 points peuvent être évalués. Le statut d’achat est distinct : non testé, validé en recette autorisée, test échoué ou défaut observé. Un purchase prématuré/incomplet déclenche une alerte critique sans pénalité forfaitaire arbitraire. Les identifiants et CMP détectés ne prouvent pas à eux seuls un tracking fonctionnel ; l’état CMP n’a pas été testé dans les deux modes. L’ancienne moyenne de présence des outils n’est pas comparable à cette nouvelle mesure. Moyenne pré-transaction : {f'{avg:.2f}'.replace('.', ',')}/10 sur {len(verified)} fiches scorées ; {not_scored} fiches ont une couverture insuffisante ou restent non vérifiables. {booking_entries} entrées vers un moteur ont été atteintes ; aucun achat réel n’a été effectué.</p></details></section>
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
