# Vérification des parcours de réservation — 14 septembre 2026

## Conclusion

La vérification réelle des parcours publics a été menée jusqu'à la recherche, aux disponibilités et au détail d'offre, sans renseigner de données personnelles, sans confirmation, sans paiement et sans réservation.

**Conclusion : les commandes ne sont pas encore prouvées comme correctement remontées.** Aucun parcours contrôlé n'a fourni simultanément :

- un succès de réservation réel ;
- un événement `purchase` déclenché exactement une fois ;
- un `transaction_id` non vide ;
- une `value` et une `currency` cohérentes ;
- une remontée vérifiable dans GA4 et Google Ads.

### Anomalie critique détectée

Une analyse globale des captures montre **14 pages qui envoient un endpoint Google Ads `purchase` avec `value=0` avant toute réservation** :

- 13 pages Homair, avec `AW-1037822916` ;
- 1 page Camping de La Clape, avec un autre identifiant.

Sur Homair, la preuve a été revue en parcours réel sur la page Domaine de Soleil Plage :

```text
en=conversion
bttype=purchase
value=0
currency_code=EUR
```

La requête part alors que le visiteur n'a pas choisi d'hébergement et que le consentement publicitaire est refusé (`pscdl=denied`). Il s'agit d'un **faux achat ou d'une conversion mal paramétrée**, pas d'une commande.

## Parcours contrôlés

| Moteur | Parcours observé | Tracking observé | Verdict |
|---|---|---|---|
| SecureHoliday | Accueil → Réserver → Hébergements → Tarifs | DataLayer moteur vide, aucun hit conversion | Réservation en ligne fermée ; liaison non démontrée |
| Yelloh | Accueil → Réserver → offres → Rechercher | `gtm.click`, `gtm.formSubmit`, GA4 `page_view` | Recherche mesurée, pas de `purchase` |
| Capfun | Page camping → Prix et Réservation → ancre | `gtm.linkClick`, page_view / Consent Mode | Clic mesuré, moteur non atteint |
| Homair | Page camping → Tarifs et disponibilités | GA4 `view_item` + faux `purchase` Ads à 0 € | **Critique : faux purchase** |
| MS Vacances | Page camping → Réserver un séjour | `gtm.click`, `gtm.linkClick` | Tunnel non atteint |
| Webcamp / Thelis | Réserver → Rechercher → résultats → détail offre | 3 `page_view` GA4, aucun événement métier | Résultats accessibles, e-commerce non exposé |
| Riviera Villages | Réserver → recherche | GA4 `view_no_results` | Absence de disponibilité correctement signalée |

## Détails utiles

### SecureHoliday — Acapulco

Le CTA public fonctionne et le moteur `reservation.secureholiday.net` s'ouvre. L'étape tarifs affiche **« La réservation en ligne est actuellement fermée »**. Le moteur ne contient qu'un `dataLayer` sans événement métier et aucun appel GA4/Ads de conversion n'a été relevé.

### Yelloh — Au Lac de Biscarrosse

Le moteur affiche des hébergements et des prix. Le bouton de recherche génère `gtm.click` et `gtm.formSubmit`, mais cela ne constitue qu'une tentative de recherche. Aucun `begin_checkout`, `add_to_cart` ou `purchase` n'est observable. Plusieurs configurations GA4/containers sont présentes et doivent être contrôlées pour éviter les doublons.

### Homair — Domaine de Soleil Plage

La page envoie `view_item`, mais envoie également un hit Google Ads de type `purchase` à valeur nulle dès le chargement de la page. Le clic sur « Tarifs et disponibilités » ne produit pas de succès de réservation dans le test. **À corriger avant d'utiliser Google Ads pour optimiser sur les réservations.**

### Webcamp / Thelis — Le Clos des Capitelles

Le bouton de recherche mène réellement à une page de résultats avec des offres et des appels de prix. Le clic sur le détail d'offre ne produit aucun événement métier dans le dataLayer. Trois `page_view` GA4 sont envoyés sur le moteur (`G-EF622EB6WZ`, `G-PZJK1RVF6C`, `G-DYPBFGBXVK`), ce qui pose aussi une question de propriété et de déduplication.

### Riviera Villages — La Toison d'Or

Le moteur accepte la recherche, mais indique que la période testée n'est pas disponible. L'événement GA4 `view_no_results` est bien envoyé. Aucun événement de réservation ou d'achat n'a été observé.

## Ce qui n'a pas été fait volontairement

Une réservation réelle implique des coordonnées, un engagement contractuel et parfois un paiement. Elle n'a donc pas été simulée. Un événement `purchase` injecté artificiellement ne prouverait que la chaîne GTM, pas le fonctionnement du moteur.

Pour certifier la commande de bout en bout, il faut un environnement de test ou une réservation annulable autorisée par le camping / fournisseur, avec comparaison entre :

1. la commande confirmée du moteur ;
2. l'événement `purchase` GA4 ;
3. la conversion Google Ads ;
4. le montant, la devise et le `transaction_id` ;
5. l'absence de doublon.

## Fichier de preuves

Les observations structurées sont dans [`journey-audit.json`](journey-audit.json). Le rapport porte sur 7 familles de moteurs représentatives et sur le scan global des 283 captures ; il ne transforme pas les 283 simples visites initiales en 283 validations de commande.
