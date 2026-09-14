# Audit Camping — observatoire du taggage des campings 5 étoiles

Site statique qui publie, pour chaque camping 5 étoiles du fichier source, un rapport public
sur l'état de son plan de taggage : GTM, GA4, Google Ads, Meta Pixel, Bing UET, consentement
RGPD et signaux de réservation. Chaque page se termine par un plan d'action priorisé et une
offre d'accompagnement **Escale Ads à 499 €**.

## Contenu du dépôt

| Chemin | Rôle |
|---|---|
| `index.html` | Page d'accueil : statistiques, filtres (recherche, région, score), 283 cartes |
| `campings/<slug>/index.html` | Un rapport par camping (283 pages) |
| `audit-input.json` | Les 283 lignes du CSV source, URLs d'origine préservées à l'identique |
| `audit-final.json` | Résultat consolidé : une fiche par camping, seule source des pages |
| `scripts/analyze_captures.py` | Transforme les captures navigateur en fiches d'audit |
| `scripts/generate_site.py` | Génère l'accueil et les 283 pages |
| `data/audits.json` | Copie lisible du résultat consolidé |
| `journey-audit.json` / `journey-audit.md` | Parcours publics réels représentatifs jusqu'aux disponibilités, preuves réseau et anomalies de conversion |
| `journey-all-results.json` / `journey-all-results.md` | Parcours navigateur exhaustif des 283 lignes CSV, sans réservation réelle |
| `sitemap.xml`, `robots.txt` | Découverte du site |

## Méthode

Une visite réelle par site, sans compte, sans réservation et sans paiement :

1. chargement de la page d'accueil publique dans un navigateur réel, avec un temps de
   stabilisation puis un défilement complet, car de nombreux tags se chargent en différé ;
2. relevé du DOM rendu, des ressources réellement chargées, du `dataLayer`, des variables de
   consentement présentes à l'exécution et des **cookies écrits** ;
3. récupération de la configuration publique de chaque conteneur GTM détecté
   (`googletagmanager.com/gtm.js?id=…`) pour identifier les propriétés GA4 et les balises
   Google Ads qu'il pilote ;
4. contrôle de cohérence : un identifiant de conteneur n'est retenu que si sa configuration
   publique a pu être récupérée.
5. parcours réel non transactionnel de plusieurs familles de moteurs (CTA, recherche,
   disponibilités, détail d'offre), avec contrôle des événements et requêtes sortantes.
   Ce contrôle ne remplace pas une réservation de test autorisée.

**Preuve par cookie.** Un identifiant présent dans le code ne prouve pas qu'un outil tourne.
Inversement, un cookie écrit (`_ga`, `_gcl_au`, `_fbp`, `_uetvid`, `axeptio_*`, `didomi_*`…)
prouve que l'outil s'est réellement exécuté. Les deux formes de preuve sont comptées et
explicitement listées sur chaque page, dans la section « Preuves observées ».

**Score sur 10** — GTM 3 points, GA 2, Google Ads 2, consentement/CMP 2, Meta Pixel 1.
Un point n'est accordé que pour un signal réellement observé, identifiant ou cookie.

## Limites assumées

- Une seule visite par site, à une date donnée : un déploiement postérieur invalide le constat.
- Aucune réservation n'a été effectuée : la remontée effective d'une conversion jusqu'à la
  plateforme n'est pas vérifiée.
- Un identifiant présent ne prouve pas qu'un tag se déclenche correctement.
- Les identifiants GA4/Ads déduits de la configuration du conteneur GTM traduisent une
  intention de mesure, pas un déclenchement observé ; les pages le précisent.
- 13 adresses n'ont pas pu être chargées (domaine injoignable ou URL erronée) : elles sont
  publiées comme **non vérifiables**, jamais comme « sans taggage ».

## Régénérer

```bash
python scripts/analyze_captures.py   # nécessite redo/raw-capture-*.json et redo/gtm/
python scripts/generate_site.py      # écrit index.html et campings/
```

`generate_site.py` refuse de produire le site si le nombre de fiches ne correspond pas
exactement aux lignes du CSV source.

## Déploiement

Site statique : GitHub Pages, Netlify ou tout hébergeur de fichiers. Le fichier `.nojekyll`
est présent pour GitHub Pages.

---

Réalisé par [Escale Ads](mailto:contact@escale-ads.com) — accompagnement taggage, Consent Mode
et conversions à 499 €.
