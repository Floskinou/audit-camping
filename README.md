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
| `scripts/recompute_booking_scores.py` | Recalcul du score à partir du rapport de parcours expurgé |
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

## Barème révisé (sur 10)

Le score mesure désormais le **suivi des réservations** et non la seule présence de balises :

- **2 points maximum** pour GTM, GA4, Google Ads et le consentement détectés (0,5 chacun) ;
- **1 point** pour une interaction de réservation/recherche effectivement mesurée ;
- **1 point** pour un hit analytics non limité au ping cookieless de consentement sur le moteur ;
- **1 point** pour un événement d’étape e-commerce observé (disponibilité/offre/panier/checkout) ;
- **5 points** seulement pour un achat confirmé avec `transaction_id`, valeur positive, `currency`, envoi GA4 et Google Ads une seule fois et sans doublon ;
- **−3 points** en cas de faux `purchase` Google Ads à valeur nulle ou sans transaction avant toute commande.

Faute de réservation réelle ou de transaction de recette autorisée, les scores sont plafonnés à **5/10**. La moyenne de présence des outils de l’ancien barème était de **7,34/10** ; la moyenne du suivi de réservation est de **1,98/10** sur 271 fiches notées. Les 12 autres restent non vérifiables.

## Régénérer le site

```bash
python scripts/recompute_booking_scores.py
python scripts/generate_site.py
```

Le recalcul utilise le rapport de parcours expurgé versionné dans le dépôt ; les lots navigateur bruts restent ignorés afin de ne pas publier de paramètres de session/attribution. Pour refaire l’audit navigateur lui-même, il faut relancer un navigateur de test et produire un nouveau rapport avant le recalcul.

## Déploiement et vérification

GitHub Pages sert le site depuis la racine de `main`. Après publication, vérifier l’accueil, une fiche camping, les fichiers CSS/JS et le sitemap avec un paramètre anti-cache ; exiger HTTP 200 et un marqueur de version unique avant de déclarer la mise à jour en ligne.
