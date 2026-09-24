import unittest

from scripts.booking_scoring import score_journey
from scripts.generate_site import card, safe_score, score_label


class BookingScoringTests(unittest.TestCase):
    def test_missing_transaction_stays_unverified_without_zeroing_pretransaction_score(self):
        journey = self.complete_pretransaction_journey()
        base = self.base_record()

        result = score_journey(journey, base)

        self.assertEqual(result["score_model"], "reservation_tracking_v3")
        self.assertEqual(result["score"], 10.0)
        self.assertEqual(result["purchase_validation_status"], "not_tested")
        self.assertFalse(result["purchase_confirmed"])
        self.assertEqual(result["score_coverage_pct"], 100)

    def test_unreachable_camping_has_no_numeric_score(self):
        result = score_journey({"status": "blocked", "steps": []}, {"status": "unreachable"})

        self.assertIsNone(result["score"])
        self.assertEqual(result["score_status"], "unverifiable")
        self.assertEqual(result["score_coverage_pct"], 0)
        retested_home = score_journey({"status": "ok", "steps": [{"stage": "home", "hits": [{"host": "region1.google-analytics.com", "path": "/g/collect", "event": "page_view"}]}]}, {"status": "unreachable"})
        self.assertTrue(retested_home["score_breakdown"]["measurement_setup"]["assessed"])

    def test_unreached_engine_is_excluded_and_low_coverage_is_not_a_zero(self):
        journey = {
            "status": "booking_closed",
            "steps": [
                {"stage": "home", "hits": [{"host": "region1.google-analytics.com", "path": "/g/collect", "event": "page_view"}]},
                {"stage": "after_booking_cta", "layers": [{"events": ["gtm.click"]}]},
            ],
        }
        result = score_journey(journey, self.base_record())

        self.assertIsNone(result["score"])
        self.assertEqual(result["score_status"], "insufficient_coverage")
        self.assertEqual(result["score_coverage_pct"], 40)
        self.assertFalse(result["score_breakdown"]["booking_engine"]["assessed"])
        self.assertEqual(result["purchase_validation_status"], "not_tested")

    def test_premature_purchase_is_a_critical_status_not_a_flat_score_penalty(self):
        ordinary = self.complete_pretransaction_journey()
        with_false_purchase = self.complete_pretransaction_journey()
        with_false_purchase["steps"][1]["hits"].append({
            "host": "pagead2.googlesyndication.com", "path": "/pagead/conversion/", "event": "conversion",
            "bttype": "purchase", "value_nonzero": False, "transaction_id_present": False,
            "currency_present": False,
        })

        normal_result = score_journey(ordinary, self.base_record())
        faulty_result = score_journey(with_false_purchase, self.base_record())

        self.assertEqual(faulty_result["purchase_validation_status"], "defect_observed")
        self.assertTrue(faulty_result["invalid_google_ads_purchase"])
        self.assertFalse(faulty_result["purchase_confirmed"])
        self.assertEqual(faulty_result["score"], normal_result["score"])
        self.assertNotIn("invalid_purchase_penalty", faulty_result)

    def test_unconfirmed_purchase_hit_cannot_inflate_pretransaction_score(self):
        journey = {"status": "booking_closed", "steps": [
            {"stage": "home", "hits": [{"host": "region1.google-analytics.com", "path": "/g/collect", "event": "page_view"}]},
            {"stage": "after_booking_cta", "layers": [{"events": ["gtm.click"]}]},
        ]}
        with_purchase = {"status": "booking_closed", "steps": [*journey["steps"], {
            "stage": "purchase_confirmation", "hits": [{"host": "region1.google-analytics.com", "path": "/g/collect", "event": "purchase", "transaction_id_present": True, "value_nonzero": True, "currency_present": True}]
        }]}

        ordinary = score_journey(journey, self.base_record())
        premature = score_journey(with_purchase, self.base_record())

        self.assertEqual(premature["score"], ordinary["score"])
        self.assertEqual(premature["score_coverage_pct"], ordinary["score_coverage_pct"])
        self.assertEqual(premature["purchase_validation_status"], "defect_observed")

    def test_purchase_is_validated_only_with_authorized_success_and_complete_unique_delivery(self):
        journey = self.complete_pretransaction_journey()
        journey["transaction_test"] = {
            "performed": True, "evidence_type": "sandbox", "success_confirmed": True,
            "purchase_event_count": 1, "transaction_id_present": True, "value_nonzero": True,
            "currency_present": True, "ga4_delivered": True, "google_ads_delivered": True,
            "duplicate_free": True,
        }
        journey["steps"].append({"stage": "purchase_confirmation", "hits": [{
            "host": "region1.google-analytics.com", "path": "/g/collect", "event": "purchase",
            "transaction_id_present": True, "value_nonzero": True, "currency_present": True,
        }]})

        result = score_journey(journey, self.base_record())

        self.assertEqual(result["purchase_validation_status"], "validated")
        self.assertTrue(result["purchase_confirmed"])

    def test_transaction_metadata_without_a_captured_purchase_hit_is_not_validation(self):
        journey = self.complete_pretransaction_journey()
        journey["transaction_test"] = {
            "performed": True, "evidence_type": "sandbox", "success_confirmed": True,
            "purchase_event_count": 1, "transaction_id_present": True, "value_nonzero": True,
            "currency_present": True, "ga4_delivered": True, "google_ads_delivered": True,
            "duplicate_free": True,
        }

        result = score_journey(journey, self.base_record())

        self.assertEqual(result["purchase_validation_status"], "test_failed")
        self.assertFalse(result["purchase_confirmed"])

    def test_incomplete_sandbox_purchase_does_not_validate(self):
        journey = self.complete_pretransaction_journey()
        journey["transaction_test"] = {
            "performed": True, "evidence_type": "sandbox", "success_confirmed": True,
            "purchase_event_count": 2, "transaction_id_present": True, "value_nonzero": True,
            "currency_present": False, "ga4_delivered": True, "google_ads_delivered": False,
            "duplicate_free": False,
        }

        result = score_journey(journey, self.base_record())

        self.assertEqual(result["purchase_validation_status"], "test_failed")
        self.assertFalse(result["purchase_confirmed"])

    def test_camping_card_surfaces_critical_purchase_alert_even_with_high_score(self):
        row = {
            "score": 8.0, "score_model": "reservation_tracking_v3", "score_status": "scored", "status": "ok",
            "invalid_google_ads_purchase": True, "row": 1, "slug": "example", "name": "Camping Exemple",
            "city": "Paris", "postal_code": "75000", "gtm_ids": [], "ga4_ids": [], "consent_detected": False,
        }
        rendered = card(row)
        self.assertIn("Alerte purchase critique", rendered)
        self.assertIn("badge-low", rendered)

    def test_site_labels_low_coverage_separately_from_unverified_tracking(self):
        low_coverage = {"score": None, "score_model": "reservation_tracking_v3", "score_status": "insufficient_coverage", "status": "ok"}
        unreachable = {"score": None, "score_model": "reservation_tracking_v3", "score_status": "unverifiable", "status": "unreachable"}

        self.assertIsNone(safe_score(low_coverage))
        self.assertEqual(score_label(None, low_coverage), "Couverture insuffisante")
        self.assertEqual(score_label(None, unreachable), "Non vérifiable")
        self.assertEqual(score_label(8.0, {"score_status": "scored"}), "Suivi bien observable · achat à valider")
        observed_before_block = {"score": 6.0, "score_model": "reservation_tracking_v3", "score_status": "scored", "status": "blocked"}
        self.assertEqual(safe_score(observed_before_block), 6.0)

    @staticmethod
    def base_record():
        return {"status": "ok", "gtm_ids": ["GTM-ABCDE1"], "ga4_ids": ["G-ABCDE12345"], "google_ads_ids": ["AW-123456789"], "consent_detected": True}

    @staticmethod
    def complete_pretransaction_journey():
        return {
            "status": "ok",
            "linker_parameter_seen": True,
            "steps": [
                {"stage": "home", "hits": [{"host": "region1.google-analytics.com", "path": "/g/collect", "event": "page_view"}]},
                {"stage": "after_booking_cta", "layers": [{"events": ["gtm.click", "booking_click"]}], "hits": [{"host": "region1.google-analytics.com", "path": "/g/collect", "event": "booking_click"}]},
                {"stage": "booking_entry", "hits": [{"host": "region1.google-analytics.com", "path": "/g/collect", "event": "page_view"}, {"host": "region1.google-analytics.com", "path": "/g/collect", "event": "availability_search"}]},
                {"stage": "availability_search", "events": ["availability_search"], "hits": [{"host": "region1.google-analytics.com", "path": "/g/collect", "event": "availability_search"}]},
                {"stage": "target_accommodations", "events": ["view_item"], "commerce_events": [{"event": "view_item", "items_present": True}], "hits": [{"host": "region1.google-analytics.com", "path": "/g/collect", "event": "view_item"}]},
            ],
        }


if __name__ == "__main__":
    unittest.main()
