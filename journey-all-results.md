# Audit exhaustif des parcours de réservation

Date : 2026-09-14

## Couverture

- **283/283 lignes CSV** parcourues.
- 7 lignes de référence : moteurs SecureHoliday, Yelloh, Capfun, Homair, MS Vacances, Webcamp/Thelis et Riviera Villages.
- 276 autres lignes parcourues séquentiellement dans le navigateur.
- **282 parcours complets**, **1 parcours partiel** (Les Truffières de Dordogne : timeout de collecte sur une page lourde après accès au tunnel).
- Les onglets créés pour chaque tentative ont été fermés ; le contrôle final ne laisse aucun onglet camping ouvert.

## Sécurité du test

- Parcours simulé uniquement : aucun nom, e-mail, téléphone, adresse ou carte saisi.
- Aucun bouton de confirmation, paiement ou réservation réelle utilisé.
- `purchase_confirmed: false` pour les 283 lignes.

## Tracking observé

- 18 lignes exposent des ressources ressemblant à des conversions.
- 14 lignes déclenchent un faux achat Google Ads à valeur zéro : lignes 43, 51, 71, 103, 160, 198, 208, 224, 226, 231, 241, 246, 266, 278.
- Motif principal : 13 pages Homair partagent AW-1037822916 et déclenchent purchase à value=0 ; la ligne 51 Camping de La Clape présente le même motif avec un autre identifiant.
- Ces signaux ne sont pas comptés comme des commandes valides : aucune preuve complète `purchase` + `transaction_id` + `value` + `currency` + GA4 + Google Ads sans doublon n’a été observée.

## Conclusion

La couverture navigateur des 283 campings est réalisée sans transaction réelle. Le tunnel public est souvent atteignable jusqu’à la recherche, aux disponibilités ou au détail d’offre, mais la validité des commandes reste non démontrée. Les faux achats à 0 € doivent être corrigés avant toute optimisation média.

Données détaillées : `journey-all-results.json`. Parcours représentatifs et preuves réseau : `journey-audit.json` / `journey-audit.md`.
