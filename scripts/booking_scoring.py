"""Evidence-based scoring for publicly observable pre-transaction tracking."""
from __future__ import annotations

import re
from collections import Counter

MODEL = "reservation_tracking_v3"
GA4_HOST_MARKERS = ("google-analytics", "analytics.google")
BOOKING_STAGES = {
    "booking_entry", "search_result", "availability_search", "target_accommodations"
}
AVAILABILITY_STAGES = {"search_result", "availability_search"}
AVAILABILITY_EVENTS = {
    "availability_search", "search_availability", "booking_search", "reservation_search"
}
OFFER_EVENTS = {"view_item", "select_item", "offer_view", "select_offer", "accommodation_view"}
ECOMMERCE_EVENTS = AVAILABILITY_EVENTS | OFFER_EVENTS | {
    "add_to_cart", "begin_checkout", "purchase", "booking_start", "reservation_start"
}
INTERACTION_LAYER_EVENTS = {
    "gtm.click", "gtm.linkclick", "gtm.formsubmit", "booking_click", "reservation_click"
}
GA4_EVENT_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,39}$")


def _steps(journey: dict) -> list[dict]:
    return list(journey.get("steps", []))


def _events_in_step(step: dict) -> list[str]:
    events = list(step.get("events", []))
    for layer in step.get("layers", []):
        events.extend(layer.get("events", []))
        events.extend(item.get("event", "") for item in layer.get("commerce", []))
    events.extend(item.get("event", "") for item in step.get("commerce_events", []))
    events.extend(hit.get("event", "") for hit in step.get("hits", step.get("measurement_hits", [])))
    return [str(event).strip() for event in events if str(event or "").strip()]


def _is_ga4_hit(hit: dict) -> bool:
    host = str(hit.get("host", "")).lower()
    path = str(hit.get("path", "")).lower()
    return any(marker in host for marker in GA4_HOST_MARKERS) and "/collect" in path and "/ccm/collect" not in path


def _is_purchase_hit(hit: dict) -> bool:
    return str(hit.get("event", "")).lower() == "purchase" or str(hit.get("bttype", "")).lower() == "purchase"


def _is_booking_event(name: str) -> bool:
    value = str(name).lower()
    if value.startswith("gtm.") or value in {"page_view", "scroll", "click", "form_start", "form_submit"}:
        return False
    return value in ECOMMERCE_EVENTS or bool(re.search(
        r"booking|reservation|reserva|availability|disponibil|checkout|cart|item|offer|accommodation|recherche|search|clic|click|bouton|purchase",
        value,
    ))


def _is_pretransaction_event(name: str) -> bool:
    return _is_booking_event(name) and str(name).lower() != "purchase"


def _all_hits(journey: dict) -> list[tuple[dict, dict]]:
    return [
        (step, hit)
        for step in _steps(journey)
        for hit in step.get("hits", step.get("measurement_hits", []))
    ]


def _ga4_hits(journey: dict) -> list[tuple[dict, dict]]:
    return [(step, hit) for step, hit in _all_hits(journey) if _is_ga4_hit(hit)]


def _purchase_validation(journey: dict, invalid_purchase: bool) -> tuple[str, bool]:
    test = journey.get("transaction_test") or {}
    attempted = bool(test.get("performed") or test.get("tested"))
    if not attempted:
        return ("defect_observed" if invalid_purchase else "not_tested", False)

    purchase_hits = [(step, hit) for step, hit in _all_hits(journey) if _is_purchase_hit(hit)]
    ga4_purchase_hits = [
        hit for _, hit in purchase_hits
        if _is_ga4_hit(hit) and str(hit.get("event", "")).lower() == "purchase"
    ]
    captured_ga4_purchase = bool(ga4_purchase_hits) and all(
        hit.get("transaction_id_present") and hit.get("value_nonzero") and hit.get("currency_present")
        for hit in ga4_purchase_hits
    )
    required = {
        "authorized_test_context": str(test.get("evidence_type", "")).lower() in {"sandbox", "authorized_test_transaction"},
        "confirmed_success": bool(test.get("success_confirmed")),
        "exactly_one_purchase": test.get("purchase_event_count") == 1,
        "captured_ga4_purchase": captured_ga4_purchase,
        "transaction_id": bool(test.get("transaction_id_present")),
        "nonzero_value": bool(test.get("value_nonzero")),
        "currency": bool(test.get("currency_present")),
        "ga4_delivery": bool(test.get("ga4_delivered")),
        "google_ads_delivery": bool(test.get("google_ads_delivered")),
        "no_duplicates": bool(test.get("duplicate_free")),
        "no_premature_purchase": not bool(test.get("premature_purchase")),
    }
    if all(required.values()) and not invalid_purchase:
        return "validated", True
    return "test_failed", False


def score_journey(journey: dict, base: dict) -> dict:
    """Return a 0–10 pre-transaction score and separate transaction evidence state.

    Only criteria actually exercised by the public journey count toward the score
    denominator. The number is normalized over assessed criteria and is withheld
    when fewer than five of ten points could be assessed; coverage is always
    reported separately. A missing transaction test never subtracts points.
    """
    steps = _steps(journey)
    by_stage: dict[str, list[dict]] = {}
    for step in steps:
        by_stage.setdefault(str(step.get("stage", "")), []).append(step)

    relevant_events = sorted({
        event
        for step in steps
        for event in _events_in_step(step)
        if _is_pretransaction_event(event)
    })
    purchase_hits = [(step, hit) for step, hit in _all_hits(journey) if _is_purchase_hit(hit)]
    transaction_test = journey.get("transaction_test") or {}
    transaction_was_confirmed = bool(transaction_test.get("success_confirmed"))
    invalid_purchase_hits = [
        hit for _, hit in purchase_hits
        if not transaction_was_confirmed
        or not hit.get("transaction_id_present")
        or not hit.get("value_nonzero")
        or not hit.get("currency_present")
        or bool(hit.get("premature"))
    ]
    invalid_purchase = bool(invalid_purchase_hits)

    components: dict[str, dict] = {}

    def component(name: str, points: float, maximum: float, assessed: bool) -> None:
        components[name] = {
            "points": round(points, 2) if assessed else None,
            "max_points": maximum,
            "assessed": bool(assessed),
        }

    site_accessible = str(base.get("status", "")).lower() in {"ok", "success", "loaded"} or "home" in by_stage
    source_stages = {"home", "after_booking_cta"}
    source_ga4 = any(step.get("stage") in source_stages for step, _ in _ga4_hits(journey))
    identifier_present = any(base.get(key) for key in ("gtm_ids", "ga4_ids", "google_ads_ids"))
    component(
        "measurement_setup",
        (1.0 if source_ga4 else 0.0) + (0.5 if identifier_present else 0.0) + (0.5 if base.get("consent_detected") else 0.0),
        2.0,
        site_accessible,
    )

    cta_steps = by_stage.get("after_booking_cta", [])
    click_seen = any(
        str(event).lower() in INTERACTION_LAYER_EVENTS
        for step in cta_steps
        for layer in step.get("layers", [])
        for event in layer.get("events", [])
    )
    custom_click_hit = any(
        _is_ga4_hit(hit) and _is_pretransaction_event(str(hit.get("event", "")))
        for step in cta_steps
        for hit in step.get("hits", step.get("measurement_hits", []))
    )
    component("booking_interaction", float(click_seen) + float(custom_click_hit), 2.0, bool(cta_steps))

    engine_steps = [step for step in steps if step.get("stage") in BOOKING_STAGES]
    engine_ga4 = any(_is_ga4_hit(hit) for step in engine_steps for hit in step.get("hits", step.get("measurement_hits", [])))
    engine_booking_event = any(
        _is_ga4_hit(hit) and _is_pretransaction_event(str(hit.get("event", "")))
        for step in engine_steps
        for hit in step.get("hits", step.get("measurement_hits", []))
    )
    engine_continuity = bool(journey.get("linker_parameter_seen")) or engine_booking_event
    component("booking_engine", float(engine_ga4) + float(engine_continuity), 2.0, bool(engine_steps))

    availability_reached = any(stage in by_stage for stage in AVAILABILITY_STAGES)
    availability_seen = any(
        str(event).lower() in AVAILABILITY_EVENTS
        for stage in AVAILABILITY_STAGES
        for step in by_stage.get(stage, [])
        for event in _events_in_step(step)
    )
    component("availability_event", float(availability_seen), 1.0, availability_reached)

    offer_reached = "target_accommodations" in by_stage
    offer_seen = any(
        str(event).lower() in OFFER_EVENTS
        for step in by_stage.get("target_accommodations", [])
        for event in _events_in_step(step)
    )
    component("offer_event", float(offer_seen), 1.0, offer_reached)

    component("event_name_quality", float(all(GA4_EVENT_NAME.fullmatch(event) for event in relevant_events)), 1.0, bool(relevant_events))

    booking_hits = [
        (step, hit) for step, hit in _ga4_hits(journey)
        if _is_pretransaction_event(str(hit.get("event", "")))
    ]
    hit_counts = Counter((str(step.get("stage", "")), str(hit.get("host", "")).lower(), str(hit.get("event", "")).lower()) for step, hit in booking_hits)
    duplicate_free = all(count == 1 for count in hit_counts.values())
    component("single_delivery_observed", float(duplicate_free), 1.0, bool(booking_hits))

    assessed_max = sum(item["max_points"] for item in components.values() if item["assessed"])
    earned = sum(item["points"] or 0.0 for item in components.values() if item["assessed"])
    score = round(earned / assessed_max * 10, 1) if assessed_max >= 5 else None
    coverage = int(round(assessed_max / 10 * 100))
    score_status = "scored" if score is not None else ("insufficient_coverage" if assessed_max else "unverifiable")
    purchase_status, purchase_confirmed = _purchase_validation(journey, invalid_purchase)

    funnel_events = sorted({
        event.lower()
        for step in steps
        for event in _events_in_step(step)
        if event.lower() in ECOMMERCE_EVENTS
    })
    return {
        "score": score,
        "score_model": MODEL,
        "score_status": score_status,
        "score_coverage_pct": coverage,
        "score_assessed_points": round(assessed_max, 2),
        "score_obtained_points": round(earned, 2),
        "score_breakdown": components,
        "purchase_validation_status": purchase_status,
        "purchase_confirmed": purchase_confirmed,
        "invalid_google_ads_purchase": invalid_purchase,
        "invalid_purchase_hit_count": len(invalid_purchase_hits),
        "booking_interaction_tracked": click_seen,
        "booking_engine_measurement_observed": engine_ga4,
        "booking_funnel_events": funnel_events,
    }
