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

- Interaction réservation/recherche mesurée : **113** sites.
- Hit GA4 observé sur une étape de réservation : **64** sites (les seuls pings `ccm/collect` ne sont pas comptés comme hit analytics validant le tunnel).
- Événement e-commerce spécifique (offre, panier, checkout) : **0** sites.
- Purchase final valide confirmé : **0**. Aucun vrai achat n’a été réalisé.
- Faux hits Google Ads `purchase` à valeur nulle/incomplète avant toute commande : **17 sites**, **23 hits**. Aucun n’est compté comme vente.

### Campings avec faux purchase Google Ads observé

20 — CAMPING BOIS SOLEIL (1 hit), 22 — CAMPING CAMP DU DOMAINE (1 hit), 44 — CAMPING DE L'ARCHE (1 hit), 49 — CAMPING DE LA BAUME (1 hit), 51 — CAMPING DE LA CLAPE (4 hits), 60 — CAMPING DOMAINE DE LA BRÈCHE (1 hit), 103 — CAMPING LA CROIX DU VIEUX PONT (1 hit), 139 — CAMPING LE CHÂTEAU (1 hit), 144 — CAMPING LE CORMORAN (2 hits), 159 — CAMPING LE DOMAINE DU CLARYS (2 hits), 186 — CAMPING LE TY NADAN (2 hits), 202 — CAMPING LES GENÊTS (1 hit), 226 — CAMPING LOU PIGNADA (1 hit), 238 — CAMPING OASIS VILLAGE (1 hit), 246 — CAMPING SAINT AVIT LOISIRS (1 hit), 266 — CAMPING VERDON PARC (1 hit), 275 — CAMPING YELLOH! VILLAGE SAINT PABU PLAGE (1 hit)

## Nouveau système de notation

Le score public mesure maintenant le **suivi de réservation observé**, au lieu de récompenser surtout la présence d’identifiants :
- Outils de base détectés (GTM, GA4, Google Ads, consentement) : **2 points maximum**.
- Interaction de réservation mesurée : **1 point**.
- Hit analytics non limité au ping cookieless de consentement sur le moteur : **1 point**.
- Événement d’étape e-commerce réellement observé (disponibilité/offre/panier/checkout) : **1 point**.
- Achat confirmé : **5 points**, uniquement avec succès réel, `transaction_id`, `value` non nul, `currency`, GA4 + Google Ads et absence de doublon.
- Faux `purchase` à 0 € ou sans identifiant de transaction avant une commande : **−3 points**.
- Moyenne de l’ancien score de présence : **7,34/10** ; nouvelle moyenne de réservation : **1,98/10** sur **271** pages scorées,
- En l’absence de transaction réelle confirmée, le nouveau score est plafonné à **5/10**. Les résultats de parcours bloqués ou fermés restent signalés comme non vérifiables.

## Recommandation

Avant d’optimiser les campagnes sur les réservations, corriger tout `purchase` prématuré à 0 €, instrumenter les étapes du moteur externe, puis valider une transaction de recette (ou sandbox) avec un `purchase` unique et une valeur, devise et transaction réellement renseignées.

Le détail par camping est dans `journey-rerun-20260923.json` ; les scores recalculés sont également publiés dans `data/audits.json`.
