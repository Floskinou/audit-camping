# Repassage des parcours de réservation — campings 5 étoiles

Date du contrôle : **2026-09-23**

## Couverture

- **283/283 campings** repassés dans le navigateur, un par un.
- Statuts : blocked : 8, booking_closed : 8, ok : 266, partial_manual : 1.
- **120** entrées de moteur de réservation atteintes ; **85** étapes de recherche, disponibilités ou hébergements atteintes.
- Les onglets camping/moteur créés pendant l’audit ont été fermés après chaque tentative.

## Sécurité et limite de la simulation

- Aucun achat, paiement ou réservation réelle ; aucune donnée personnelle saisie ; aucun bouton de confirmation finale activé.
- Le contrôle s’arrête au résultat de recherche ou à la liste d’hébergements. Sans transaction de test autorisée, il ne peut prouver l’exécution réelle du purchase final.
- Les choix CMP sont restés à leur état par défaut : aucun consentement n’a été accordé automatiquement.
- Les sites qui bloquent l’accès, ferment les réservations ou échouent au chargement sont signalés comme non vérifiables, pas comme preuve certaine d’une absence de configuration interne.

## Signaux observés

- Interaction réservation/recherche mesurée : **85** sites.
- Hit GA4 observé sur une étape de réservation : **64** sites (les seuls pings `ccm/collect` ne sont pas comptés comme hit analytics validant le tunnel).
- Événement e-commerce spécifique (offre, panier, checkout) : **0** sites.
- Purchase final valide confirmé : **0**. Aucun vrai achat n’a été réalisé.
- Faux hits Google Ads `purchase` à valeur nulle/incomplète avant toute commande : **17 sites**, **23 hits**. Aucun n’est compté comme vente.

### Campings avec faux purchase Google Ads observé

20 — CAMPING BOIS SOLEIL (1 hit), 22 — CAMPING CAMP DU DOMAINE (1 hit), 44 — CAMPING DE L'ARCHE (1 hit), 49 — CAMPING DE LA BAUME (1 hit), 51 — CAMPING DE LA CLAPE (4 hits), 60 — CAMPING DOMAINE DE LA BRÈCHE (1 hit), 103 — CAMPING LA CROIX DU VIEUX PONT (1 hit), 139 — CAMPING LE CHÂTEAU (1 hit), 144 — CAMPING LE CORMORAN (2 hits), 159 — CAMPING LE DOMAINE DU CLARYS (2 hits), 186 — CAMPING LE TY NADAN (2 hits), 202 — CAMPING LES GENÊTS (1 hit), 226 — CAMPING LOU PIGNADA (1 hit), 238 — CAMPING OASIS VILLAGE (1 hit), 246 — CAMPING SAINT AVIT LOISIRS (1 hit), 266 — CAMPING VERDON PARC (1 hit), 275 — CAMPING YELLOH! VILLAGE SAINT PABU PLAGE (1 hit)

## Barème v3

Le score /10 porte sur le **suivi observable avant transaction** ; la validation du purchase est un statut distinct.
- Base de mesure : **2 pts** (hit GA4 réel, présence limitée des outils et CMP détectée ; le comportement CMP reste non testé).
- Interaction réservation : **2 pts** (signal d’interaction dans la dataLayer et hit GA4 nommé sur l’étape CTA).
- Moteur de réservation : **2 pts** (hit GA4 hors ping cookieless et signal de continuité/linker ou événement de réservation).
- Disponibilités et offres : **2 pts** (1 point par étape atteinte et événement correspondant observé).
- Qualité des événements : **2 pts** (noms conformes aux règles GA4 et absence de doublon parmi les hits de réservation observés dans une même étape).
- Formule : 10 × points obtenus / points évaluables ; les étapes non atteintes sont exclues du dénominateur. Couverture affichée séparément ; aucun score si moins de 5 points sont évaluables.
- Achat : `not_tested`, `validated`, `test_failed` ou `defect_observed`. Il ne contribue pas au score pré-transaction ; sa validation exige une recette autorisée, succès confirmé, hit GA4 capturé, un seul purchase, transaction_id, valeur positive, devise, envoi Google Ads et absence de doublon.
- Un faux `purchase` prématuré/incomplet est une alerte critique distincte, sans soustraction forfaitaire arbitraire.
- Scores calculés : **165** ; couverture insuffisante : **118** ; moyenne pré-transaction : **3,33/10**.
- Moyenne v2 : **1,98/10** ; elle n’est pas directement comparable au barème v3.

## Recommandation

Corriger tout signal purchase prématuré, instrumenter les étapes disponibilité/offre/checkout, puis valider le purchase en sandbox ou recette explicitement autorisée. Aucun achat réel n’a été réalisé pendant ce repassage.

Le détail par camping est dans `journey-rerun-20260923.json` ; les scores recalculés sont publiés dans `data/audits.json`.
