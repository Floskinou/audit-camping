#!/usr/bin/env python3
"""Recompute booking-tracking scores from the 2026-09-23 safe browser replay.

The browser evidence is intentionally reduced before publication: URL query
strings/fragments, transaction identifiers, request values, raw page text, and
form values are not copied to the public report.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from statistics import mean, median
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from booking_scoring import score_journey

ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-09-23"
INPUT = ROOT / "audit-input.json"
AUDIT = ROOT / "audit-final.json"
RAW = ROOT / "journey-batches" / "rerun-20260923"
REPORT_JSON = ROOT / "journey-rerun-20260923.json"
REPORT_MD = ROOT / "journey-rerun-20260923.md"
CHUNKS = ["rows-001-028.json"] + [f"rows-{a:03d}-{b:03d}.json" for a, b in (
    (29, 48), (49, 68), (69, 88), (89, 108), (109, 128), (129, 148),
    (149, 168), (169, 188), (189, 208), (209, 228), (229, 248),
    (249, 268), (269, 283),
)]
ECOMMERCE_EVENTS = {
    "view_item", "select_item", "add_to_cart", "begin_checkout", "purchase",
    "booking_start", "reservation_start", "availability_search",
    "search_availability", "booking_search", "reservation_search",
}


def public_url(raw: str | None) -> str:
    """Drop all query parameters and fragments (including linker/session data)."""
    if not raw:
        return ""
    try:
        u = urlsplit(str(raw))
        if not u.scheme or not u.netloc:
            return ""
        return f"{u.scheme}://{u.netloc}{u.path}"[:260]
    except Exception:
        return ""


def safe_booking_url(raw: str | None) -> str:
    """Drop hard-coded search dates while keeping the campsite identifier."""
    if not raw:
        return ""
    try:
        u = urlsplit(str(raw))
        if not u.scheme or not u.netloc:
            return ""
        date_keys = {"begin", "end", "book-date", "booking-date", "arrival", "departure", "checkin", "checkout", "check_in", "check_out", "start-date", "end-date"}
        query = urlencode([(key, value) for key, value in parse_qsl(u.query, keep_blank_values=True) if key.lower() not in date_keys], doseq=True)
        return urlunsplit((u.scheme, u.netloc, u.path, query, ""))[:500]
    except Exception:
        return ""


def safe_event(raw) -> str:
    return re.sub(r"[^A-Za-z0-9_:/.-]", "", str(raw or ""))[:90]


def read_journeys() -> tuple[list[dict], dict[int, str]]:
    expected = json.loads(INPUT.read_text(encoding="utf-8"))
    cities = {int(x["row"]): str(x.get("city", "")) for x in expected}
    # The sanitized consolidated report is the canonical source in a public clone.
    # Raw browser batches stay ignored because they may contain volatile URL queries.
    if REPORT_JSON.exists():
        payload = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
        rows = payload.get("results", [])
    else:
        rows = []
        for name in CHUNKS:
            path = RAW / name
            if not path.exists():
                raise SystemExit(f"Missing sanitized report or browser batch: {path}")
            rows.extend(json.loads(path.read_text(encoding="utf-8")))
        manual_path = RAW / "row-282-manual.json"
        manual = json.loads(manual_path.read_text(encoding="utf-8"))
        rows = [manual if int(row["row"]) == 282 else row for row in rows]
    expected_rows = {int(x["row"]) for x in expected}
    actual_rows = [int(x["row"]) for x in rows]
    if len(rows) != len(expected) or len(set(actual_rows)) != len(actual_rows) or set(actual_rows) != expected_rows:
        raise SystemExit(f"Journey coverage mismatch: {len(rows)} rows, {len(set(actual_rows))} unique, expected {len(expected)}")
    for row in rows:
        row["city"] = row.get("city") or cities.get(int(row["row"]), "")
    return sorted(rows, key=lambda x: int(x["row"])), cities


def row_events(journey: dict) -> list[str]:
    found = []
    for step in journey.get("steps", []):
        found.extend(step.get("events", []))
        for layer in step.get("layers", []):
            found.extend(layer.get("events", []))
            found.extend(x.get("event", "") for x in layer.get("commerce", []))
        found.extend(x.get("event", "") for x in step.get("commerce_events", []))
        for hit in step.get("hits", step.get("measurement_hits", [])):
            if hit.get("event"):
                found.append(hit["event"])
    result = []
    for event in found:
        value = safe_event(event)
        if value and value not in result:
            result.append(value)
    return result


def click_tracked(journey: dict) -> bool:
    stages = {"after_booking_cta", "search_result", "availability_search", "target_accommodations"}
    for step in journey.get("steps", []):
        if step.get("stage") not in stages:
            continue
        for layer in step.get("layers", []):
            events = {safe_event(e).lower() for e in layer.get("events", [])}
            if events & {"gtm.click", "gtm.linkclick", "gtm.formsubmit", "booking_click", "reservation_click"}:
                return True
    return False


def engine_measurement(journey: dict) -> bool:
    stages = {"booking_entry", "search_result", "availability_search", "target_accommodations"}
    for step in journey.get("steps", []):
        if step.get("stage") not in stages:
            continue
        for hit in step.get("hits", step.get("measurement_hits", [])):
            host = str(hit.get("host", "")).lower()
            path = str(hit.get("path", "")).lower()
            # Consent Mode ccm/collect page_view is not credited as an analytics hit.
            if ("google-analytics" in host or "analytics.google" in host) and "/collect" in path:
                return True
    return False


def funnel_events(journey: dict) -> list[str]:
    found = set()
    for step in journey.get("steps", []):
        for event in step.get("events", []):
            name = safe_event(event).lower()
            if name in ECOMMERCE_EVENTS:
                found.add(name)
        for layer in step.get("layers", []):
            for event in layer.get("events", []):
                name = safe_event(event).lower()
                if name in ECOMMERCE_EVENTS:
                    found.add(name)
            for item in layer.get("commerce", []):
                name = safe_event(item.get("event", "")).lower()
                if name in ECOMMERCE_EVENTS:
                    found.add(name)
        for item in step.get("commerce_events", []):
            name = safe_event(item.get("event", "")).lower()
            if name in ECOMMERCE_EVENTS:
                found.add(name)
        for hit in step.get("hits", step.get("measurement_hits", [])):
            name = safe_event(hit.get("event", "")).lower()
            if name in ECOMMERCE_EVENTS:
                found.add(name)
    return sorted(found)


def false_ads_purchase(journey: dict) -> tuple[bool, int]:
    invalid = []
    for step in journey.get("steps", []):
        for hit in step.get("hits", step.get("measurement_hits", [])):
            event = str(hit.get("event", "")).lower()
            bttype = str(hit.get("bttype", "")).lower()
            if bttype == "purchase" or event == "purchase":
                if not hit.get("value_nonzero") or not hit.get("transaction_id_present"):
                    invalid.append(hit)
    return bool(invalid), len(invalid)


def summarize_journey(journey: dict, base: dict) -> dict:
    events = row_events(journey)
    scored = score_journey(journey, base)
    status = str(journey.get("status", "error"))
    if status == "partial_manual":
        verdict = "Parcours partiel : recherche et hébergements atteints ; achat non testé."
    elif status == "booking_closed":
        verdict = "Réservation fermée lors du contrôle ; achat non testé."
    elif status == "blocked":
        verdict = "Accès au site ou au moteur bloqué ; suivi non vérifiable."
    elif status == "error":
        verdict = "Erreur technique ; suivi non vérifiable."
    elif scored["invalid_google_ads_purchase"]:
        verdict = "Signal critique : purchase Ads déclenché sans achat confirmé."
    elif scored["purchase_validation_status"] == "test_failed":
        verdict = "Test transactionnel incomplet ou non conforme."
    elif scored["purchase_confirmed"]:
        verdict = "Achat de recette confirmé et transmis avec les champs requis."
    elif scored["booking_funnel_events"]:
        verdict = "Événement(s) d’étape observé(s) ; achat réel non testé."
    elif scored["booking_interaction_tracked"] or scored["booking_engine_measurement_observed"]:
        verdict = "Interaction ou mesure sur le moteur observée ; achat non testé."
    else:
        verdict = "Aucun événement de réservation probant observé pendant ce parcours."
    scored.update({
        "journey_status": status,
        "journey_verdict": verdict,
        "journey_events": events,
        "booking_entry_reached": any(x.get("stage") == "booking_entry" for x in journey.get("steps", [])),
        "availability_step_reached": any(x.get("stage") in {"search_result", "availability_search", "target_accommodations"} for x in journey.get("steps", [])),
        "reservation_made": False,
        "personal_data_entered": False,
    })
    return scored


def public_record(journey: dict, scored: dict) -> dict:
    result = {
        "row": int(journey["row"]),
        "name": str(journey.get("name", "")),
        "city": str(journey.get("city", "")),
        "status": str(journey.get("status", "error")),
        "source_url": public_url(journey.get("source_url")),
        "cta": None,
        "search_action": None,
        "steps": [],
        "score": scored["score"],
        "score_model": scored["score_model"],
        "score_status": scored["score_status"],
        "score_coverage_pct": scored["score_coverage_pct"],
        "score_assessed_points": scored["score_assessed_points"],
        "score_obtained_points": scored["score_obtained_points"],
        "score_breakdown": scored["score_breakdown"],
        "journey_verdict": scored["journey_verdict"],
        "booking_funnel_events": scored["booking_funnel_events"],
        "booking_interaction_tracked": scored["booking_interaction_tracked"],
        "booking_engine_measurement_observed": scored["booking_engine_measurement_observed"],
        "purchase_validation_status": scored["purchase_validation_status"],
        "purchase_confirmed": scored["purchase_confirmed"],
        "invalid_google_ads_purchase": scored["invalid_google_ads_purchase"],
        "invalid_purchase_hit_count": scored["invalid_purchase_hit_count"],
        "reservation_made": False,
        "personal_data_entered": False,
        "closed_tabs": int(journey.get("closed_tabs", 0)),
    }
    cta = journey.get("cta")
    if cta:
        result["cta"] = {"text": str(cta.get("text", ""))[:100], "href": public_url(cta.get("href")), "tag": str(cta.get("tag", ""))[:12]}
    action = journey.get("search_action")
    if action:
        result["search_action"] = {"text": str(action.get("text", ""))[:100], "date_fields_found": int(action.get("date_fields_found", 0)), "dates_filled": int(action.get("dates_filled", 0))}
    if journey.get("linker_parameter_seen"):
        result["linker_parameter_seen"] = True
    for step in journey.get("steps", []):
        out = {
            "stage": str(step.get("stage", "")),
            "url": public_url(step.get("url")),
            "title": str(step.get("title", ""))[:180],
            "layers": [],
            "hits": [],
            "blockers": list(step.get("blockers", [])),
        }
        for layer in step.get("layers", []):
            out["layers"].append({
                "name": str(layer.get("name", ""))[:60],
                "events": [safe_event(e) for e in layer.get("events", []) if safe_event(e)][:35],
                "commerce": [{
                    "event": safe_event(e.get("event", "")),
                    "transaction_id_present": bool(e.get("transaction_id_present")),
                    "value_present": bool(e.get("value_present")),
                    "value_nonzero": bool(e.get("value_nonzero")),
                    "currency_present": bool(e.get("currency_present")),
                } for e in layer.get("commerce", [])[:8]],
            })
        if step.get("events") and not out["layers"]:
            out["layers"].append({"name": "dataLayer", "events": [safe_event(e) for e in step["events"] if safe_event(e)][:35], "commerce": []})
        for hit in step.get("hits", step.get("measurement_hits", [])):
            out["hits"].append({k: hit.get(k) for k in ("host", "path", "event", "bttype", "value_present", "value_nonzero", "currency_present", "transaction_id_present") if k in hit})
        if step.get("note"):
            out["note"] = str(step["note"])[:420]
        result["steps"].append(out)
    if journey.get("error"):
        result["error"] = str(journey["error"])[:160]
    return result


def main() -> None:
    journeys, _ = read_journeys()
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    by_audit = {int(x["row"]): x for x in audit}
    by_journey = {int(x["row"]): x for x in journeys}
    if set(by_audit) != set(by_journey):
        raise SystemExit("Audit/journey row IDs differ")

    public_rows = []
    new_scores = []
    previous_scores = []
    statuses = Counter()
    false_rows = []
    for journey in journeys:
        key = int(journey["row"])
        row = by_audit[key]
        cleaned_links = [safe_booking_url(link) for link in row.get("booking_links", [])]
        row["booking_links"] = list(dict.fromkeys(link for link in cleaned_links if link))
        prior_score = row.get("score")
        if row.get("score_model") == "reservation_tracking_v2" and isinstance(prior_score, (int, float)):
            row.setdefault("reservation_tracking_v2_score", prior_score)
        legacy_score = row.get("tag_presence_score", prior_score)
        if isinstance(legacy_score, (int, float)):
            row["tag_presence_score"] = legacy_score
            previous_scores.append(float(legacy_score))
        scored = summarize_journey(journey, row)
        row.pop("breakdown", None)
        row.update(scored)
        row["score"] = scored["score"]
        row["score_model"] = scored["score_model"]
        row["score_observed_on"] = DATE
        if row["score"] is not None:
            new_scores.append(float(row["score"]))
        statuses[journey.get("status", "error")] += 1
        if scored["invalid_google_ads_purchase"]:
            false_rows.append({"row": key, "name": row.get("name", ""), "hits": scored["invalid_purchase_hit_count"]})

        actions = [action for action in list(row.get("priority_actions") or []) if not any(marker in action.lower() for marker in ("faux événement google ads purchase à 0 €", "réservation réelle remonte une seule fois"))]
        if scored["invalid_google_ads_purchase"]:
            actions.insert(0, "Corriger immédiatement le signal purchase prématuré/incomplet ; ne l’émettre qu’après un succès de réservation confirmé.")
        if not scored["booking_funnel_events"]:
            actions.append("Instrumenter le moteur sur les étapes disponibilité/offre/checkout et transmettre les événements au domaine d’analyse attendu.")
        actions.append("Valider une transaction de recette avec exactement un purchase portant transaction_id, value non nul et currency, transmis à GA4 et Google Ads.")
        row["priority_actions"] = list(dict.fromkeys(actions))[:5]
        issues = list(row.get("issues") or [])
        if scored["invalid_google_ads_purchase"]:
            issues.insert(0, "Un signal Google Ads purchase a été émis sans preuve d’une transaction confirmée ou avec des champs incomplets.")
        if not scored["booking_funnel_events"]:
            issues.append("Aucun événement e-commerce d’étape (disponibilité, offre, panier ou checkout) n’a été observé pendant le parcours simulé.")
        if scored["purchase_validation_status"] == "not_tested":
            issues.append("Aucune transaction de recette autorisée n’a été testée ; le suivi de l’achat final reste non vérifié.")
        elif scored["purchase_validation_status"] == "test_failed":
            issues.append("Le test transactionnel de recette n’a pas satisfait tous les critères de validation.")
        row["issues"] = list(dict.fromkeys(issues))[:10]
        evidence = list(row.get("evidence") or [])
        evidence.append("Parcours de réservation public repassé le 2026-09-23 sans réservation ni saisie de données personnelles.")
        evidence.append(scored["journey_verdict"])
        row["evidence"] = list(dict.fromkeys(evidence))[:10]
        row["limitations"] = list(dict.fromkeys(list(row.get("limitations") or []) + [
            "Aucun achat réel, paiement, soumission finale ou donnée personnelle n’a été saisi.",
            "Le score de réservation mesure les preuves publiques observées ; l’absence de preuve n’établit pas à elle seule l’absence de configuration interne.",
        ]))[:8]
        public_rows.append(public_record(journey, scored))

    valid = [float(x["score"]) for x in audit if isinstance(x.get("score"), (int, float))]
    click_count = sum(x["booking_interaction_tracked"] for x in audit)
    engine_hit_count = sum(x["booking_engine_measurement_observed"] for x in audit)
    funnel_count = sum(bool(x["booking_funnel_events"]) for x in audit)
    booking_entries = sum(any(s.get("stage") == "booking_entry" for s in j.get("steps", [])) for j in journeys)
    availability_steps = sum(any(s.get("stage") in {"search_result", "availability_search", "target_accommodations"} for s in j.get("steps", [])) for j in journeys)
    purchase_valid = sum(bool(x.get("purchase_confirmed")) for x in audit)
    purchase_statuses = Counter(x.get("purchase_validation_status", "not_tested") for x in audit)
    coverage_values = [int(x.get("score_coverage_pct", 0) or 0) for x in audit]
    report = {
        "audit_date": DATE,
        "scope": "Repassage en navigateur de chaque camping ; simulation limitée à l’entrée réservation et à la recherche/disponibilités lorsqu’elle était accessible.",
        "safety": {"reservation_made": False, "personal_data_entered": False, "payment_or_confirmation": False, "real_purchase_confirmed": False, "consent_granted_by_automation": False},
        "coverage": {"source_rows": 283, "unique_rows": len(public_rows), "status_counts": dict(sorted(statuses.items())), "booking_entry_reached": booking_entries, "availability_or_accommodation_step_reached": availability_steps, "score_coverage_mean_pct": round(mean(coverage_values), 1) if coverage_values else 0},
        "tracking": {"booking_click_or_search_interaction_measured": click_count, "booking_engine_ga4_measurement_hit_observed": engine_hit_count, "sites_with_ecommerce_funnel_events": funnel_count, "purchase_confirmed": purchase_valid, "purchase_validation_status_counts": dict(sorted(purchase_statuses.items())), "false_google_ads_purchase_sites": len(false_rows), "false_google_ads_purchase_hits": sum(x["hits"] for x in false_rows), "false_purchase_sites": false_rows},
        "scoring": {
            "model": "reservation_tracking_v3",
            "name": "suivi observable pré-transaction",
            "formula": "10 × points obtenus / points évaluables ; les critères non atteints sont exclus du dénominateur. Afficher la couverture séparément ; aucun score sous 5/10 points évaluables.",
            "components": {
                "measurement_setup": "2 pts : hit GA4 réel sur le site (1), outils identifiés (0,5 maximum) et CMP détectée (0,5 ; comportement CMP non testé)",
                "booking_interaction": "2 pts : événement d’interaction vu dans la dataLayer (1) et hit GA4 nommé sur l’étape CTA (1)",
                "booking_engine": "2 pts : hit GA4 non cookieless sur le moteur (1) et linker ou événement réservation nommé observé (1)",
                "availability_event": "1 pt si l’étape disponibilité/recherche est atteinte et l’événement correspondant est mesuré",
                "offer_event": "1 pt si la liste d’offres est atteinte et view_item/select_item (ou équivalent) est mesuré",
                "event_name_quality": "1 pt lorsque des événements réservation sont observés et leurs noms respectent le format GA4",
                "single_delivery_observed": "1 pt lorsque les hits GA4 de réservation observés ne sont pas dupliqués dans une même étape",
            },
            "purchase_validation": "Statut séparé : not_tested, validated, test_failed ou defect_observed. Un achat n’est validé qu’avec contexte de recette autorisé, succès confirmé, un seul achat, hit GA4 capturé, transaction_id, valeur positive, devise, GA4 + Ads et absence de doublon.",
            "critical_false_purchase": "Alerte critique séparée, sans pénalité forfaitaire arbitraire ; ne valide jamais un achat.",
            "minimum_assessed_points": 5,
            "average_previous_tag_presence_score": round(mean(previous_scores), 2) if previous_scores else None,
            "average_v2_score": round(mean([float(x["reservation_tracking_v2_score"]) for x in audit if isinstance(x.get("reservation_tracking_v2_score"), (int, float))]), 2) if any(isinstance(x.get("reservation_tracking_v2_score"), (int, float)) for x in audit) else None,
            "average_pretransaction_score": round(mean(valid), 2) if valid else None,
            "median_pretransaction_score": round(median(valid), 2) if valid else None,
            "scored_rows": len(valid),
            "insufficient_coverage_rows": sum(x.get("score_status") == "insufficient_coverage" for x in audit),
        },
        "results": public_rows,
    }
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    format_fr = lambda value: f"{value:.2f}".replace(".", ",")
    md = [
        "# Repassage des parcours de réservation — campings 5 étoiles",
        "", f"Date du contrôle : **{DATE}**", "",
        "## Couverture", "",
        f"- **{len(public_rows)}/283 campings** repassés dans le navigateur, un par un.",
        f"- Statuts : {', '.join(f'{k} : {v}' for k, v in sorted(statuses.items()))}.",
        f"- **{booking_entries}** entrées de moteur de réservation atteintes ; **{availability_steps}** étapes de recherche, disponibilités ou hébergements atteintes.",
        "- Les onglets camping/moteur créés pendant l’audit ont été fermés après chaque tentative.",
        "", "## Sécurité et limite de la simulation", "",
        "- Aucun achat, paiement ou réservation réelle ; aucune donnée personnelle saisie ; aucun bouton de confirmation finale activé.",
        "- Le contrôle s’arrête au résultat de recherche ou à la liste d’hébergements. Sans transaction de test autorisée, il ne peut prouver l’exécution réelle du purchase final.",
        "- Les choix CMP sont restés à leur état par défaut : aucun consentement n’a été accordé automatiquement.",
        "- Les sites qui bloquent l’accès, ferment les réservations ou échouent au chargement sont signalés comme non vérifiables, pas comme preuve certaine d’une absence de configuration interne.",
        "", "## Signaux observés", "",
        f"- Interaction réservation/recherche mesurée : **{click_count}** sites.",
        f"- Hit GA4 observé sur une étape de réservation : **{engine_hit_count}** sites (les seuls pings `ccm/collect` ne sont pas comptés comme hit analytics validant le tunnel).",
        f"- Événement e-commerce spécifique (offre, panier, checkout) : **{funnel_count}** sites.",
        f"- Purchase final valide confirmé : **{purchase_valid}**. Aucun vrai achat n’a été réalisé.",
        f"- Faux hits Google Ads `purchase` à valeur nulle/incomplète avant toute commande : **{len(false_rows)} sites**, **{sum(x['hits'] for x in false_rows)} hits**. Aucun n’est compté comme vente.",
        "", "### Campings avec faux purchase Google Ads observé", "",
        ", ".join(f"{x['row']} — {x['name']} ({x['hits']} hit{'s' if x['hits'] != 1 else ''})" for x in false_rows) or "Aucun.",
        "", "## Barème v3", "",
        "Le score /10 porte sur le **suivi observable avant transaction** ; la validation du purchase est un statut distinct.",
        "- Base de mesure : **2 pts** (hit GA4 réel, présence limitée des outils et CMP détectée ; le comportement CMP reste non testé).",
        "- Interaction réservation : **2 pts** (signal d’interaction dans la dataLayer et hit GA4 nommé sur l’étape CTA).",
        "- Moteur de réservation : **2 pts** (hit GA4 hors ping cookieless et signal de continuité/linker ou événement de réservation).",
        "- Disponibilités et offres : **2 pts** (1 point par étape atteinte et événement correspondant observé).",
        "- Qualité des événements : **2 pts** (noms conformes aux règles GA4 et absence de doublon parmi les hits de réservation observés dans une même étape).",
        "- Formule : 10 × points obtenus / points évaluables ; les étapes non atteintes sont exclues du dénominateur. Couverture affichée séparément ; aucun score si moins de 5 points sont évaluables.",
        "- Achat : `not_tested`, `validated`, `test_failed` ou `defect_observed`. Il ne contribue pas au score pré-transaction ; sa validation exige une recette autorisée, succès confirmé, hit GA4 capturé, un seul purchase, transaction_id, valeur positive, devise, envoi Google Ads et absence de doublon.",
        "- Un faux `purchase` prématuré/incomplet est une alerte critique distincte, sans soustraction forfaitaire arbitraire.",
        f"- Scores calculés : **{len(valid)}** ; couverture insuffisante : **{sum(x.get('score_status') == 'insufficient_coverage' for x in audit)}** ; moyenne pré-transaction : **{format_fr(mean(valid))}/10**." if valid else "- Aucun score n’atteint le seuil minimal de couverture.",
        f"- Moyenne v2 : **{format_fr(mean([float(x['reservation_tracking_v2_score']) for x in audit if isinstance(x.get('reservation_tracking_v2_score'), (int, float))]))}/10** ; elle n’est pas directement comparable au barème v3." if any(isinstance(x.get("reservation_tracking_v2_score"), (int, float)) for x in audit) else "- Aucun historique de score v2 conservé.",
        "", "## Recommandation", "",
        "Corriger tout signal purchase prématuré, instrumenter les étapes disponibilité/offre/checkout, puis valider le purchase en sandbox ou recette explicitement autorisée. Aucun achat réel n’a été réalisé pendant ce repassage.",
        "", "Le détail par camping est dans `journey-rerun-20260923.json` ; les scores recalculés sont publiés dans `data/audits.json`.", "",
    ]
    REPORT_MD.write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"journeys": len(public_rows), "score_rows": len(valid), "status_counts": dict(statuses), "booking_entries": booking_entries, "availability_steps": availability_steps, "click_measured": click_count, "engine_hits": engine_hit_count, "ecommerce_sites": funnel_count, "valid_purchase": purchase_valid, "false_purchase_sites": len(false_rows), "old_avg": round(mean(previous_scores), 2), "new_avg": round(mean(valid), 2), "files": [str(REPORT_JSON), str(REPORT_MD), str(AUDIT)]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
