# Audit Camping — suivi des réservations

Site statique public : **https://floskinou.github.io/audit-camping/**
Dépôt : `Floskinou/audit-camping` — GitHub Pages, branche `main`.

Le site rassemble 283 fiches de campings 5 étoiles. Les rapports distinguent la présence des outils de mesure et les preuves réellement observées dans un parcours de réservation. L’offre Escale Ads affichée reste **499 €**.

## Fichiers principaux

| Chemin | Rôle |
|---|---|
| `index.html` | Accueil, statistiques et filtres des 283 fiches |
| `campings/<slug>/index.html` | Rapport public par camping |
| `audit-input.json` | 283 lignes de la source d’audit |
| `audit-final.json` | Résultats par camping et nouveaux scores de réservation |
| `data/audits.json` | Données utilisées par le site statique |
| `journey-rerun-20260923.json` / `.md` | Repassage navigateur et signaux du parcours, URLs expurgées de leurs paramètres |
| `journey-all-results.json` / `.md` | Rapport de parcours historique du 2026-09-14, remplacé par le repassage du 2026-09-23 |
| `scripts/analyze_captures.py` | Analyse initiale des captures de taggage |
| `scripts/recompute_booking_scores.py` | Recalcul des résultats de parcours et production du rapport public |
| `scripts/booking_scoring.py` | Barème v3 : score pré-transaction, couverture et validation d’achat séparée |
| `tests/test_booking_scoring.py` | Tests unitaires des seuils, de la couverture et des preuves d’achat |
| `scripts/generate_site.py` | Génération de l’accueil et des 283 pages camping |
| `sitemap.xml`, `robots.txt` | Découverte du site sur GitHub Pages |

## Repassage navigateur du 2026-09-23

- **283/283** campings couverts, un par un ; les onglets d’audit ont été fermés après chaque tentative.
- Statuts : **266** pages accessibles, **8** réservations fermées, **8** accès bloqués et **1** parcours partiel repris manuellement (Les Truffières de Dordogne).
- **120** entrées dans un moteur de réservation et **85** étapes de recherche/disponibilités/hébergements atteintes.
- **113** sites : interaction de réservation ou de recherche mesurée ; **64** : hit GA4 observé sur une étape moteur.
- **0** événement e-commerce spécifique observé (offre, panier ou checkout), **0** achat valide confirmé.
- **17** campings ont émis **23** faux hits Google Ads `purchase` à 0 € ou sans transaction, avant toute commande.
- Aucun vrai achat ou paiement n’a été effectué ; aucune donnée personnelle n’a été saisie. Les choix CMP sont restés à leur état par défaut.

Les accès bloqués et réservations fermées ne prouvent pas qu’aucun tag interne n’existe. Le score reflète les preuves observables pendant le parcours sûr, pas une inspection des comptes Analytics ou du moteur de réservation.

## Barème v3

Le score /10 mesure le **suivi observable avant transaction**. La validation d’un achat est affichée à part : `not_tested`, `validated`, `test_failed` ou `defect_observed`.

- **2 points — base de mesure** : hit GA4 réel sur le site, présence limitée d’identifiants d’outils et CMP détectée. Les identifiants seuls ne suffisent pas ; le comportement CMP n’a pas été testé dans les deux états.
- **2 points — interaction** : signal d’interaction observé dans la dataLayer et hit GA4 nommé sur le CTA.
- **2 points — moteur** : hit GA4 non cookieless et signal de continuité/linker ou événement de réservation nommé.
- **2 points — étapes** : un point pour un événement de disponibilité et un point pour un événement d’offre, uniquement si l’étape correspondante a été atteinte.
- **2 points — qualité des événements** : conformité des noms GA4 et absence de doublon parmi les hits de réservation observés dans une même étape.

Le score est normalisé sur les seuls critères effectivement évaluables. Les étapes non atteintes ne sont pas assimilées à un échec ; la couverture est affichée séparément. Aucun score numérique n’est publié si moins de **5 points sur 10** ont pu être évalués. Un signal `purchase` prématuré/incomplet est une alerte critique distincte, sans pénalité forfaitaire qui brouillerait le score pré-transaction.

Un achat n’est marqué **validé** qu’après un succès dans un environnement de recette autorisé, avec un unique `purchase`, un hit GA4 capturé, `transaction_id`, valeur positive, devise, livraison GA4 et Google Ads, et absence de doublon. Une simulation qui s’arrête avant ce succès laisse le statut `not_tested` ; elle ne valide ni ne réfute à elle seule la configuration interne.

Les scores v2 (champ `reservation_tracking_v2_score`) et v3 ne sont pas directement comparables : ils ne mesurent pas la même chose. Les résultats v3 et la couverture calculée sont consignés dans `audit-final.json` et dans le rapport de parcours.

## Régénérer le site

```bash
python scripts/recompute_booking_scores.py
python scripts/generate_site.py
```

Le recalcul utilise le rapport de parcours expurgé versionné dans le dépôt ; les lots navigateur bruts restent ignorés afin de ne pas publier de paramètres de session/attribution. Pour refaire l’audit navigateur lui-même, il faut relancer un navigateur de test et produire un nouveau rapport avant le recalcul.

## Déploiement et vérification

GitHub Pages sert le site depuis la racine de `main`. Après publication, vérifier l’accueil, une fiche camping, les fichiers CSS/JS et le sitemap avec un paramètre anti-cache ; exiger HTTP 200 et un marqueur de version unique avant de déclarer la mise en ligne.

## Publication sur escale-ads.com/tracking-camping

Le site est aussi publié en miroir sous `https://escale-ads.com/tracking-camping/` via `scripts/export_to_escale.py`, qui recopie l’accueil, les 283 fiches et les assets dans un clone de `Floskinou/Escale-Ads2026`, réécrit les liens internes en cibles fichier, injecte canonical + og:url sous la base publique, génère le sitemap de section (284 URL) et complète `robots.txt` + `sitemap.xml` racine — de façon idempotente et sans toucher aux autres fichiers de la cible.

```bash
python scripts/export_to_escale.py . <clone-Escale-Ads2026>
```

Tests : `tests/test_export_to_escale.py` ; smoke runtime du miroir : `tests/visual_smoke_subpath.cjs` (serveur local racine du clone cible sur le port 8767). La source de déploiement Netlify est la branche `main` de `Floskinou/Escale-Ads2026` ; après publication, exiger HTTP 200 + canonical exact sur la section, et contrôler le root sitemap ainsi que les deux lignes `Sitemap:` du `robots.txt`.
