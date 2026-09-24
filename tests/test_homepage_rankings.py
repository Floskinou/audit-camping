import re
import unittest

from scripts.generate_site import detail_page, homepage, load_results, ranked_campings


class HomepageRankingTests(unittest.TestCase):
    def test_homepage_contains_ten_distinct_best_and_worst_scored_campings(self):
        rows = load_results()
        rendered = homepage(rows)
        best = re.findall(r'<li[^>]+data-ranking="best"[^>]+data-row="(\d+)"', rendered)
        worst = re.findall(r'<li[^>]+data-ranking="worst"[^>]+data-row="(\d+)"', rendered)

        self.assertEqual(len(best), 10)
        self.assertEqual(len(worst), 10)
        self.assertEqual(len(set(best + worst)), 20)
        by_row = {str(row["row"]): row for row in rows}
        self.assertTrue(all(by_row[number]["score"] is not None for number in best + worst))

    def test_hero_names_tagging_plan_and_links_to_verified_appointment(self):
        rendered = homepage(load_results())
        hero = rendered.split('<section class="hero">', 1)[1].split('</section>', 1)[0]

        self.assertIn("plan de taggage", hero.lower())
        self.assertIn('href="https://calendly.com/escaleads/30min', hero)

    def test_header_uses_brand_logo_and_appointment_link(self):
        rendered = homepage(load_results())
        site_header = rendered.split('<header class="site-header">', 1)[1].split('</header>', 1)[0]

        self.assertIn('src="assets/images/logo-escale-ads.png"', site_header)
        self.assertIn('href="https://calendly.com/escaleads/30min', site_header)
        self.assertTrue('href="assets/css/redesign.css"' in rendered, "feuille de style de refonte absente")

    def test_catalog_is_collapsible_and_methodology_anchor_exists(self):
        rendered = homepage(load_results())

        self.assertTrue('<details id="campings"' in rendered, "catalogue repliable absent")
        self.assertTrue('<section id="methode"' in rendered, "ancre méthode absente")

    def test_critical_purchase_alerts_can_be_filtered(self):
        rendered = homepage(load_results())
        alerts = sum(bool(row.get("invalid_google_ads_purchase")) for row in load_results())

        self.assertTrue('<option value="critical">' in rendered, "filtre alerte absent")
        self.assertEqual(rendered.count('data-critical="true"'), alerts)

    def test_mobile_offer_has_early_price_and_appointment_link(self):
        rendered = homepage(load_results())
        offer_copy = rendered.split('<div class="offer-copy">', 1)[1].split('</div>', 1)[0]

        self.assertTrue('499 €' in offer_copy, "prix absent du début de l’offre")
        self.assertTrue('href="https://calendly.com/escaleads/30min' in offer_copy,
                        "CTA absent avant la liste des livrables")

    def test_ranking_orders_scored_rows_and_excludes_critical_from_best(self):
        def row(number, score, coverage, critical=False, status="scored"):
            return {"row": number, "score_model": "reservation_tracking_v3",
                    "score_status": status, "score": score,
                    "score_coverage_pct": coverage, "invalid_google_ads_purchase": critical}

        rows = [row(1, 9, 70, True), row(2, 8, 80), row(3, 8, 70),
                row(4, 1, 60), row(5, 0, 70), row(6, 2, 40),
                row(7, None, 80, status="insufficient_coverage")]
        best, worst = ranked_campings(rows, limit=2)

        self.assertEqual([item["row"] for item in best], [2, 3])
        self.assertEqual([item["row"] for item in worst], [5, 4])

    def test_critical_alert_breaks_low_score_tie(self):
        def row(number, critical, score=0):
            return {"row": number, "score_model": "reservation_tracking_v3",
                    "score_status": "scored", "score": score, "score_coverage_pct": 70,
                    "invalid_google_ads_purchase": critical}
        _, worst = ranked_campings([row(1, False), row(2, True), row(3, False, 5)], limit=1)
        self.assertEqual(worst[0]["row"], 2)

    def test_bare_camping_domain_is_absolute_in_detail_source_link(self):
        row = next(row for row in load_results() if row["source_url"].startswith("www."))
        rendered = detail_page(row)
        self.assertIn(f'href="https://{row["source_url"]}"', rendered)
        self.assertNotIn(f'href="{row["source_url"]}"', rendered)

    def test_detail_offer_uses_the_same_appointment_path(self):
        rendered = detail_page(load_results()[0])
        detail_offer = rendered.split('<section class="cta-block">', 1)[1].split('</section>', 1)[0]

        self.assertTrue('href="https://calendly.com/escaleads/30min' in detail_offer,
                        "l’offre de la fiche n’utilise pas le rendez-vous vérifié")


if __name__ == "__main__":
    unittest.main()
