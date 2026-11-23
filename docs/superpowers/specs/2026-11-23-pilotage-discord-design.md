# Pilotage du serveur Discord depuis le site — conception

Date : 2026-11-23 · Statut : à valider par le propriétaire (relu par un builder ; questions tranchées) · Projet : Hermes v2 (SaucisseLand)

## 1. Intention

Le propriétaire veut **administrer le serveur Discord depuis l'admin du site** au lieu des paramètres
Discord : rôles, attribution de rôles, salons et permissions, jeux, droits sur Hermes et sur le site, et
une modération complète avec l'historique de tout ce qui se passe. Ajouter des permissions « rôle par
rôle » dans Discord est jugé trop long ; le site doit offrir des gestes simples (modèles, grilles, un
clic pour un jeu).

Succès : le propriétaire et son staff font depuis `/admin` ce qu'ils faisaient dans les paramètres
Discord, avec un journal qui dit qui a fait quoi, et des accès partiels pour confier une partie de
l'admin (modération, tickets…) sans tout donner.

### Objectifs
1. **Journal unique et page Modération complète** : commandes utilisées, sanctions (site, Hermes et
   modération native Discord), changements de rôles/salons faits depuis le site ; filtres et export.
2. **Accès partiels à l'admin**, gérés depuis le site : chaque page/action de l'admin exige un droit
   précis, attribué à des rôles Discord.
3. **Rôles** : créer/modifier des rôles Discord, en donner/retirer à des membres (unitaire et en lot),
   et **règles de rôles automatiques** (condition → rôle), remplaçant les rôles codés en dur (Batman,
   succès, niveaux, jeux).
4. **Jeux en un clic** : ajouter un jeu dans l'admin crée le rôle, le forum réservé et la commande
   `/<jeu>` ; désactiver archive sans supprimer.
5. **Salons avec modèles d'accès** : créer un salon/forum/catégorie et appliquer un modèle d'accès
   (Public, Rôle requis, Annonces, Staff) à un salon ou à une catégorie entière.
6. **Grille des permissions par rôle** : permissions Discord (par familles lisibles), commandes Hermes
   autorisées, droits sur le site.

### Non-objectifs
- Remplacer entièrement le client Discord (messages, vocal, threads, emojis, stickers, AutoMod,
  webhooks, onboarding, événements programmés Discord) : hors périmètre.
- Gérer plusieurs serveurs Discord : un seul (`GUILD_ID`).
- Fonctionnement quand le bot est arrêté : les modifications sont refusées avec un message clair.

### Anti-objectifs (échec même si « ça marche »)
- Un membre du staff qui, via le site, s'attribue ou attribue des droits **au-dessus** des siens
  (escalade de privilèges).
- Une action destructive (suppression de rôle/salon, retrait massif de rôles) sans confirmation
  explicite affichant ce qui sera touché.
- Le site qui détient ou manipule des secrets supplémentaires (le jeton du bot reste côté bot ;
  `web` n'appelle jamais Discord pour modifier le serveur).
- Des règles qui se contredisent en silence (deux règles qui donnent/retirent le même rôle en boucle).

## 2. Contraintes (existant)

- Pile : `bot` (discord.py + API interne FastAPI :8001, même boucle asyncio que le bot via
  `asyncio.gather` dans `bot/main.py`, jeton `BOT_API_TOKEN`), `web-api` (FastAPI interne, appelle le bot
  via `bot_client`), `web` (Next.js 16, proxy `/api/proxy/*`), PostgreSQL. Migrations SQL manuelles
  numérotées dans `db/migrations/` (dernière : 019).
- Async uniquement ; commandes slash **guild-scoped** ; tests : vitest (web), pytest (bot, web-api).
- Droits du site aujourd'hui : `isAdmin`/`isRedacteur` calculés à la connexion depuis les rôles Discord
  (`web/src/lib/auth.ts`, réglages `admin_role`/`redacteur_role`), réévalués toutes les 10 min
  (`role-refresh.ts`), lus par web-api dans les tables BetterAuth (`require_admin`, `require_redacteur`).
- Journal actuel : `admin_logs` (actions faites depuis le site seulement) ; commandes : compteur
  `user_command_stats` (sans date ni contexte) + embed dans un salon de logs (`COMMAND_LOG_CHANNEL_ID`).
- Rôles automatiques existants, dispersés :
  - Batman : réglage `role_batman` + `voice_hours_for_role` (100) dans `cogs/moderation/voice.py` ;
  - niveaux : `LEVEL_ROLE_KEYS` → réglages de rôles dans `cogs/gamification/xp.py` ;
  - succès : rôle créé **par nom** « <icône> <nom du succès> » dans `cogs/system/achievements_notifier.py` ;
  - jeux : `GAMES` codé en dur dans `cogs/fun/game_lfg.py` (6 jeux, une commande chacun, rôles/forums
    par nom) ; côté site, `site_games` (clé, nom, couleur, visuel, `discord_role_id`,
    `forum_channel_id`, position, actif, accroche).
- Limites Discord : le bot ne peut gérer que les rôles **sous son rôle le plus haut** et ne peut pas
  accorder des permissions qu'il n'a pas ; 250 rôles max ; 100 commandes slash par serveur ; la
  resynchronisation des commandes est limitée (~200 écritures/jour/serveur) ; les forums exigent un
  serveur « Communauté ».
- Sécurité (vague du 2026-11-23) : contrôle d'Origin sur les mutations du proxy, rate limiting par IP
  de socket, `web` sans `BOT_API_TOKEN`.

## 3. Approches

| | Principe | Pour | Contre |
|---|---|---|---|
| **A (retenue)** | Le site enregistre, web-api appelle l'API interne du bot, le bot agit dans Discord et répond. | Réutilise le chemin existant (kick/ban/toggle) ; un seul écrivain Discord (limites de débit et cache gérés par discord.py) ; retour immédiat. | Bot arrêté → modifications refusées. |
| B | web-api/web appelle l'API REST Discord avec le jeton du bot. | Marche bot arrêté. | Deux écrivains, limites de débit doublées, cache du bot désynchronisé, le jeton sort du bot. |
| C | File de travaux en base consommée par le bot. | Rien n'est perdu bot arrêté. | Pas de retour immédiat, page d'état, lourd pour un bot qui tourne en permanence. |

Choix du propriétaire : **A**, livraison en 6 étapes dans l'ordre des objectifs.

## 4. Conception

### 4.1 Principes transverses
- **Source de vérité** : Discord pour les objets Discord (rôles, salons, permissions natives,
  membres) — le site les lit en direct via le bot (pas de copie persistante, sauf cache court) ;
  la base pour ce qui est propre à Hermes (règles, droits du site, droits sur les commandes, jeux, journal).
- **Chaque mutation** passe par : web-api (contrôle du droit précis de l'appelant + contrôle anti-escalade)
  → API interne du bot → Discord ; puis écriture d'une ligne dans le journal (§4.2) avec l'acteur
  (membre du site) comme auteur et `X-Audit-Log-Reason` Discord « via le site par <pseudo> ».
- **Anti-escalade** (règle unique, appliquée côté web-api ET côté bot) : un acteur ne peut créer,
  modifier, attribuer ou retirer qu'un rôle **strictement en dessous** de son propre rôle le plus haut,
  et ne peut accorder (permission Discord, droit du site, droit de commande) que ce qu'il possède lui-même.
  Seul le propriétaire du serveur Discord n'a pas de limite. **Décision du propriétaire : les détenteurs
  de `admin_role` y sont soumis comme tout le monde** (la position Discord fait loi ; si le rôle admin est
  trop bas, on le remonte dans Discord). « Rôle le plus haut » = position Discord du rôle le plus haut du
  membre.
- **Rôles staff** (décision du concepteur) : nouveau réglage `staff_roles` (liste d'identifiants de rôles),
  réutilisé par les forums de jeux (§4.5) et les modèles Annonces/Staff (§4.6). Quand il change, l'admin
  propose de réécrire les surcharges des salons qui l'utilisent (aperçu + confirmation).
- **Confirmations** : toute action destructive ou de masse affiche avant exécution ce qui sera touché
  (nombre de membres, salons, rôles) et exige une confirmation.
- **Erreurs Discord** traduites en français dans l'admin (rôle au-dessus du bot, permission manquante,
  limite atteinte, bot hors ligne).

### 4.2 Étape 1 — Journal unique et page Modération
- Nouvelle table `audit_events` (remplace l'usage de `admin_logs`, qui est migrée dedans puis
  conservée en lecture) : `id`, `occurred_at`, `kind` (`command`, `sanction`, `role`, `channel`,
  `member_role`, `permission`, `setting`, `game`, `site_access`…), `action` (ex. `kick`, `timeout`,
  `role.create`, `/fortnite`), `source` (`site`, `hermes`, `discord`), `actor_id`, `actor_name`,
  `target_id`, `target_name`, `channel_id`, `channel_name`, `success` (bool), `details` (JSONB :
  arguments, raison, durée, avant/après), index sur (`occurred_at`), (`kind`,`occurred_at`),
  (`actor_id`), (`target_id`).
- Périmètre (précisé par le propriétaire) : **toute action sur le serveur** est journalisée — messages modifiés/supprimés (avec contenu), vocal (connexions, déplacements, micro/casque, partage d'écran), arrivées/départs, pseudos, rôles des membres, rôles, salons et permissions, fils, invitations, émojis, réglages du serveur — avec des filtres cohérents par type d'action. Les messages envoyés ne sont pas journalisés (volume).
- Alimentation :
  - commandes : `on_app_command_completion` et `on_app_command_error` (bot) → une ligne par commande,
    avec arguments (valeurs des options ; masquer le texte libre des commandes anonymes comme
    `/confess`), salon, succès ;
  - sanctions : actions Hermes et site (déjà connues) + **modération native** lue via l'évènement
    `on_audit_log_entry_create` (kick, ban, unban, timeout, suppression de message par un modérateur) —
    nécessite la permission « Voir les logs du serveur » pour le bot. Les entrées dont l'auteur est le
    bot lui-même (actions site/Hermes) ne créent pas de doublon : elles complètent la ligne existante
    (identifiant de l'entrée Discord) (décision du concepteur) ;
  - changements faits depuis le site (étapes 2 à 6).
- Rétention : purge quotidienne des lignes de plus de **365 jours** (tâche du bot).
- Page `/admin/moderation` : actions existantes (avertir, exclure, bannir, timeout) + journal paginé
  avec filtres (type, action/commande, auteur, cible, salon, source, succès, période) et recherche,
  export CSV du résultat filtré, lien vers la fiche membre. L'onglet « journal » existant (`admin-logs`)
  est remplacé.

### 4.3 Étape 2 — Accès partiels à l'admin
- Table `site_permissions` : (`discord_role_id`, `permission`) ; liste fermée de permissions du site :
  `admin.view`, `moderation.view`, `moderation.act`, `tickets.manage`, `articles.write`,
  `articles.publish`, `gallery.manage`, `content.edit`, `quests.manage`, `games.manage`,
  `roles.manage`, `members.roles`, `channels.manage`, `permissions.manage`, `settings.manage`,
  `analytics.view`. (Le builder peut affiner les noms ; la liste doit couvrir chaque page de l'admin.)
- Le propriétaire du serveur et le rôle `admin_role` actuel ont toutes les permissions (filet de
  sécurité : impossible de s'enfermer dehors). `redacteur_role` reçoit `articles.write` à la migration.
- Calcul : à la connexion et à chaque réévaluation (10 min), la session stocke l'**ensemble des
  permissions** du membre (union des permissions de ses rôles) au lieu de deux booléens ; web-api
  remplace `require_admin`/`require_redacteur` par `require(permission)`. Les booléens restent
  dérivés pour compatibilité pendant la transition.
- Page `/admin/acces` : grille rôles × permissions du site, cases à cocher, soumise à l'anti-escalade.
- L'admin n'affiche que les pages autorisées ; une page non autorisée répond « accès refusé ».

### 4.4 Étape 3 — Rôles
- Page `/admin/roles` : liste des rôles du serveur (ordre, couleur, nombre de membres, géré par une
  intégration ou non, au-dessus/en dessous du bot), création (nom, couleur, affiché séparément,
  mentionnable), modification, suppression (confirmée, avec le nombre de membres), réordonnancement
  limité aux rôles sous le bot.
- Attribution : depuis la fiche membre (ajouter/retirer) et **en lot** (sélection de membres par
  recherche ou filtre → ajouter/retirer un rôle ; confirmation avec le nombre).
- **Règles automatiques** (table `role_rules`) : `id`, `condition_type`, `condition_value`
  (ex. heures, niveau, id du succès, clé du jeu), `role_id`, `remove_when_lost` (bool),
  `exclusive_group` (optionnel : un seul rôle du groupe à la fois, ex. grades), `active`.
  Conditions : vocal total (heures), messages total, niveau, grade, succès débloqué, série en cours
  (jours), bumps, invitations. (Pas de condition « jeu choisi » : le choix du jeu *est* l'attribution
  du rôle, §4.5.)
- Succès : une règle de succès vise un rôle existant **ou** « créer le rôle au premier déblocage »
  (`role_id` nul + nom/couleur à créer, comportement actuel conservé) ; aucun rôle n'est pré-créé ;
  chaque succès a une règle ou non (décision du concepteur, limite de 250 rôles).
- Moteur dans le bot : évaluation **à l'évènement** (XP gagné, succès débloqué, fin de session
  vocale, choix de jeu…) pour le membre concerné, plus une **réconciliation** périodique (toutes les
  6 h) et à la demande (bouton « appliquer maintenant » avec aperçu du nombre de membres touchés).
  Détection des règles contradictoires (même rôle donné par une règle et retiré par une autre) à
  l'enregistrement : refus avec explication.
- Changement du rôle d'une règle : aperçu « N membres remplissent la condition » ; donner le nouveau
  rôle à ces membres ; proposer (case à cocher, confirmée) de retirer l'ancien.
- Migration : reprendre les comportements actuels en règles (Batman = vocal ≥ `voice_hours_for_role`
  → `role_batman` ; niveaux = `LEVEL_ROLE_KEYS` ; succès = un rôle par succès, en résolvant les rôles
  existants « <icône> <nom> » par nom **une fois** pour obtenir leurs identifiants ; jeux = étape 4).
  Le code codé en dur correspondant est retiré une fois la règle en place. Aucun membre ne perd ni ne
  gagne de rôle le jour de la bascule : les règles migrées démarrent en **mode aperçu** (évaluation à
  l'évènement active comme aujourd'hui, réconciliation désactivée) ; la réconciliation d'une règle n'est
  activée qu'après qu'un admin a vu l'aperçu (qui gagnerait/perdrait quoi) et validé (décision du concepteur).

### 4.5 Étape 4 — Jeux en un clic
- `site_games` devient la seule source des jeux (fin de `GAMES` dans `game_lfg.py`) ; colonnes ajoutées :
  `emoji`, `command_name` (dérivé de la clé, modifiable, unique, conforme aux règles Discord),
  `category_id` (catégorie du forum), `lfg_cooldown`.
- Ajout d'un jeu → le bot crée (ou rattache s'il existe déjà, par identifiant choisi dans l'admin) :
  le rôle du jeu, le **forum réservé** (visible et accessible seulement au rôle du jeu, au staff et au
  bot), et la commande `/<command_name>` (même comportement que les commandes LFG actuelles : ping du
  rôle, cooldown). Les commandes de jeux sont enregistrées **dynamiquement** par le bot (guild commands)
  et resynchronisées sans redémarrage, en regroupant les changements pour respecter les limites.
- Désactivation : retire la commande, archive le forum (verrouillé, masqué) et laisse le rôle
  (suppression possible séparément, confirmée). Réactivation : restaure.
- Les 6 jeux actuels sont migrés sans changement visible (mêmes commandes, rôles et forums rattachés
  par identifiant).
- **Rôles de jeux par réaction** (`bot/cogs/system/reaction_roles.py`, `GAME_ROLES` en dur) : le message
  de réactions des jeux est reconstruit depuis `site_games` (emoji de chaque jeu actif) ; ajouter ou
  désactiver un jeu met ce message à jour. Les réactions restent le moyen pour un membre de choisir
  ses jeux (décision du concepteur). Les rôles de notification de ce même cog ne changent pas.

### 4.6 Étape 5 — Salons et modèles d'accès
- Page `/admin/salons` : arborescence catégories → salons (texte, vocal, forum, annonces), création,
  renommage, déplacement, suppression (confirmée), et **modèle d'accès** applicable à un salon ou à
  toute une catégorie (option « synchroniser les salons de la catégorie ») :
  - Public : tout le monde lit et écrit ;
  - Rôle requis : invisible sauf pour le(s) rôle(s) choisi(s) ;
  - Annonces : tout le monde lit, seuls le(s) rôle(s) choisi(s) écrivent ;
  - Staff : invisible sauf pour le(s) rôle(s) staff choisi(s) ;
  - Personnalisé : ouvre la grille détaillée (§4.7) pour ce salon.
- Le modèle se traduit en surcharges de permissions Discord (`@everyone`, rôles choisis, bot) ;
  l'aperçu montre les surcharges qui seront écrites et celles qui seront supprimées.

### 4.7 Étape 6 — Grille des permissions par rôle
- Page `/admin/permissions` : un rôle par ligne, trois onglets :
  - **Discord** : permissions natives regroupées en familles lisibles (Général, Membres, Messages,
    Vocal, Événements, Avancé) avec libellés français ; « Administrateur » isolé et confirmé ;
  - **Hermes** : commandes autorisées pour le rôle — appliqué via les permissions de commandes
    d'application Discord quand c'est possible (le bot doit alors disposer d'un jeton OAuth avec
    `applications.commands.permissions.update`, sinon vérification côté bot avant exécution) ;
  - **Site** : les permissions du §4.3.
- Toutes les écritures soumises à l'anti-escalade et journalisées (avant/après).

## 5. Ce qui reste au builder
- Noms exacts des permissions du site, découpage des routes web-api et bot, schéma SQL détaillé et
  numéros de migration, pagination et tri, libellés français des permissions Discord.
- Choix technique pour les permissions de commandes Hermes (permissions natives Discord vs contrôle
  côté bot), à trancher selon ce qu'autorise l'API Discord avec le jeton du bot.
- Stratégie de cache court (lecture des rôles/salons du serveur dans l'admin).
- Découpage en tâches et en commits, une étape livrable et déployable à la fois.
