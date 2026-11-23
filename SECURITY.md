# Politique de sécurité

Hermes est le bot Discord et la plateforme web de la communauté SaucisseLand. Ce document explique comment signaler une vulnérabilité et comment nous la traitons.

## Versions prises en charge

| Version | Prise en charge |
|---|---|
| `main` (v2 : `bot/`, `web-api/`, `web/`) | ✅ |
| Code v1 à la racine (`main.py`, `cogs/`, `utils/`) | ❌ Legacy, non maintenu |

## Signaler une vulnérabilité

**Ne publiez pas de vulnérabilité dans une issue, une pull request ou un salon Discord public.**

Deux canaux privés :

1. **GitHub (recommandé)** : [Signaler une vulnérabilité](https://github.com/DrTableBasse/Hermes/security/advisories/new), dans l'onglet *Security* du dépôt.
2. **Discord** : un message privé à un administrateur du serveur SaucisseLand.

Merci d'indiquer :

- le composant concerné (bot, web-api, site web) et la route ou le fichier ;
- les étapes pour reproduire, avec une preuve de concept minimale si possible ;
- l'impact estimé (données exposées, actions possibles, prérequis) ;
- si vous le souhaitez, comment vous créditer.

## Ce à quoi vous attendre

| Étape | Délai indicatif |
|---|---|
| Accusé de réception | 72 heures |
| Première évaluation (validité, gravité) | 7 jours |
| Correctif d'une faille critique ou haute | 30 jours |
| Publication de l'avis de sécurité | Après le déploiement du correctif |

Hermes est maintenu bénévolement : ces délais sont des objectifs, pas des garanties. Nous vous tiendrons informé de l'avancement. Avec votre accord, nous vous créditerons dans l'avis publié.

## Périmètre

**Dans le périmètre :**

- le bot Discord (`bot/`) et son API interne ;
- l'API web (`web-api/`) ;
- le site web (`web/`), y compris l'authentification Discord ;
- la configuration de déploiement fournie (`compose.yml`, Dockerfiles, schéma `db/`).

**Hors périmètre :**

- les vulnérabilités de Discord, de GitHub ou des services tiers eux-mêmes ;
- les attaques par déni de service volumétrique ;
- l'ingénierie sociale envers les membres ou le staff ;
- les rapports issus uniquement de scanners automatiques, sans impact démontré ;
- l'absence d'en-têtes ou de bonnes pratiques sans scénario d'exploitation concret ;
- les instances auto-hébergées mal configurées par un tiers.

## Règles de test

Pour que votre recherche soit considérée de bonne foi :

- testez sur votre propre instance (`docker compose up`) plutôt que sur le serveur de production ;
- si vous devez tester en production, n'utilisez que vos propres comptes ;
- n'accédez pas aux données d'autres membres, ne les modifiez pas et ne les supprimez pas au-delà du strict nécessaire pour prouver la faille ;
- n'effectuez aucune action de modération (kick, ban, timeout) sur d'autres membres ;
- arrêtez-vous et signalez dès que vous obtenez un accès non prévu.

Nous ne prendrons aucune mesure contre une personne qui respecte ces règles et nous laisse le temps de corriger avant toute divulgation.

## Bonnes pratiques pour les contributeurs

- Ne commitez jamais de secrets (`.env`, jetons, mots de passe). Utilisez `env.example` comme modèle.
- Requêtes SQL paramétrées uniquement, jamais de valeurs interpolées dans une chaîne.
- Toute route d'administration passe par `require_admin` ou `require_redacteur` côté web-api.
- `web-api` et l'API interne du bot ne doivent jamais être publiés hors du réseau Docker.
- Si vous découvrez une faille en contribuant, signalez-la par les canaux ci-dessus, pas dans la PR.
