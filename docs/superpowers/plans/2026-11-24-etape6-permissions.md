# Étape 6 — Grille des permissions par rôle : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Une page `/admin/permissions` avec trois onglets : **Discord** (permissions natives de chaque rôle, par familles lisibles en français), **Hermes** (quels rôles peuvent utiliser quelles commandes du bot), **Site** (renvoi vers la grille des accès de l'étape 2), sous anti-escalade stricte.

**Architecture:** Catalogue pur des permissions Discord (familles, libellés) partagé bot/site ; table `command_permissions` (liste blanche de rôles par commande) appliquée par le bot avant chaque commande (contrôle côté bot : l'API Discord des permissions de commandes exige un jeton OAuth utilisateur que le bot n'a pas) ; API interne du bot pour lire/écrire les permissions de rôle ; web-api pour droits, anti-escalade et journal ; page du site.

**Tech Stack:** PostgreSQL 15, discord.py, FastAPI, Next.js 16 / vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-11-23-pilotage-discord-design.md` §4.1, §4.7.

## Global Constraints

- Droit du site : `permissions.manage` pour les onglets Discord et Hermes. Onglet Site = la grille existante `/admin/acces` (même droit).
- Familles Discord (libellés français, toutes les permissions de `discord.Permissions.VALID_FLAGS` classées, aucune oubliée) : **Général** (voir les salons, gérer les salons, gérer les rôles, gérer les expressions, voir les logs, voir les analyses, gérer les webhooks, gérer le serveur, créer des invitations, changer/gérer les pseudos…), **Membres** (expulser, bannir, exclure temporairement…), **Messages** (envoyer, fils, liens, fichiers, réactions, émojis externes, mentionner @everyone, gérer les messages, épingler, historique, commandes d'application, sondages…), **Vocal** (se connecter, parler, vidéo, activités, soundboard, priorité, rendre muet, mettre en sourdine, déplacer, détection de voix…), **Événements** (créer/gérer des événements), **Avancé** (administrateur, seul, confirmé). Un test garantit que chaque drapeau de discord.py est dans exactement une famille.
- Anti-escalade Discord (sauf propriétaire) : rôle modifiable seulement s'il est strictement sous le rôle le plus haut de l'acteur et sous le bot, non `managed`, non `@everyone` (ce dernier : propriétaire seulement) ; l'acteur ne peut activer ou désactiver qu'une permission qu'il possède lui-même (permissions effectives du serveur ; « administrateur » = toutes) ; activer « Administrateur » exige une confirmation explicite (`confirm_administrator: true`) et n'est possible que pour le propriétaire.
- Commandes Hermes : `command_permissions(command_name TEXT, role_id BIGINT, PRIMARY KEY(command_name, role_id))`. Règle d'accès (propriétaire et `admin_role` : toujours autorisés) :
  - commande réservée aux admins (`@administration_only`) : autorisée si le membre a `admin_role` **ou** un rôle de sa liste ;
  - autre commande : liste vide = tout le monde (comportement actuel) ; liste non vide = seulement ces rôles.
  - Les commandes protégées nativement (`app_commands.checks.has_permissions`) et l'activation/désactivation existante (`command_enabled`) restent inchangées ; le refus affiche un message éphémère français.
  - Anti-escalade : l'acteur ne peut ajouter/retirer qu'un rôle strictement sous lui ; ouvrir une commande admin à un rôle est réservé aux admins (`is_admin`).
- Toute modification journalisée (`audit_events`, kind `permission`, `details` avant/après lisibles). Erreurs Discord traduites. Ne jamais afficher `.env` ni `docker compose config`. Commits en français terminés par la ligne Co-Authored-By de la consigne. Migration : `db/migrations/025_command_permissions.sql`.

## Review Focus

1. Un modérateur coche « Bannir » pour un rôle alors qu'il n'a pas lui-même « Bannir » → 403 (Task 3).
2. Retrait d'une permission que l'acteur n'a pas (ex. « Administrateur » d'un rôle sous lui) → 403 (Task 3).
3. Liste blanche d'une commande non admin vidée → commande de nouveau ouverte à tous (Task 2).
4. Rôle supprimé encore présent dans `command_permissions` → ignoré, pas d'erreur (Task 2).
5. Bot redémarré → liste blanche relue avant la première commande (Task 2).

---

### Task 1: Catalogue et règles pures

**Files:** Create `bot/utils/permission_catalog.py`, `bot/utils/command_access.py`, `db/migrations/025_command_permissions.sql` (+ `db/init.sql`), `web/src/lib/discord-permissions.ts` (copie du catalogue : clé discord.py, famille, libellé) ; Test `bot/tests/test_permission_catalog.py`, `bot/tests/test_command_access.py`, `web/src/lib/__tests__/discord-permissions.test.ts` (même liste que le catalogue Python, lu par expression régulière).

**Interfaces:** `FAMILIES: list[tuple[str, list[tuple[str, str]]]]` (famille → [(drapeau, libellé)]) ; `def flags_to_value(flags: Iterable[str]) -> int` ; `def value_to_flags(value: int) -> set[str]` ; `def can_use(*, is_owner: bool, is_admin_role: bool, admin_only: bool, member_role_ids: set[int], allowed_role_ids: set[int]) -> bool` ; `def escalation_error(actor_perms: int, is_owner: bool, before: int, after: int) -> str | None`.

- [ ] Tests (chaque drapeau dans exactement une famille ; conversions ; `can_use` pour les 4 cas du Global Constraints ; `escalation_error` pour activer/retirer sans posséder, administrateur), implémentation, suites vertes, commit `feat(permissions): catalogue des permissions Discord et règles d'accès aux commandes`.

### Task 2: Bot (contrôle des commandes + API interne)

**Files:** Modify `bot/utils/command_manager.py` et/ou `bot/utils/decorators.py` (contrôle `can_use` dans le chemin commun de toutes les commandes : `command_enabled` et `administration_only`), cache des listes blanches rechargé au démarrage et sur `POST /command-permissions/reload` ; Modify `bot/api.py` : `GET /discord/roles/permissions?actor_id=` (rôles : id, nom, position, managed, permissions ; acteur : permissions effectives, rang, propriétaire ; bot : rang), `PATCH /discord/roles/{id}/permissions` {permissions: int, confirm_administrator?: bool, actor_id, actor_name} (anti-escalade complète, raison d'audit « via le site par … »), `GET /commands/catalog` (nom, description, `admin_only`, protégé nativement) ; Test `bot/tests/test_command_permissions.py`, `bot/tests/test_api_role_permissions.py`.

- [ ] Tests (Review Focus 3, 4, 5 ; refus éphémère ; anti-escalade de PATCH), implémentation, `cd bot && python -m pytest -q` + `python -c "import main"`, commit `feat(permissions): accès aux commandes par rôle et API des permissions de rôle`.

### Task 3: web-api

**Files:** Create `web-api/routes/permissions_admin.py` (router `/admin/permissions`) ; Test `web-api/tests/test_permissions_admin.py`.

**Interfaces:** `GET /admin/permissions/discord` (catalogue + rôles + acteur, `editable` par rôle et par drapeau) ; `PUT /admin/permissions/discord/{role_id}` {permissions: [drapeaux], confirm_administrator?} ; `GET /admin/permissions/commands` (catalogue des commandes + rôles autorisés) ; `PUT /admin/permissions/commands/{name}` {role_ids: [str]} (anti-escalade ; commande admin réservée `is_admin` ; rechargement du bot) — droit `permissions.manage` ; journal `permission`.

- [ ] Tests (Review Focus 1, 2 ; propriétaire exempté ; journal), implémentation, `cd web-api && python -m pytest -q`, commit `feat(permissions): gestion des permissions de rôle et des commandes dans web-api`.

### Task 4: Page Permissions

**Files:** Create `web/src/app/[locale]/admin/permissions/page.tsx`, composants `discord-permissions-grid.tsx`, `command-permissions.tsx` ; Modify `admin-sections.ts` (section « Permissions », `permissions.manage`) ; Test `web/src/app/[locale]/admin/__tests__/permissions.test.tsx`.

```
Permissions        [Discord] [Hermes] [Site → Accès]
Discord : rôle [Modérateur ▾]
  Membres   ☑ Expulser  ☐ Bannir (vous ne l'avez pas)  ☑ Exclure temporairement
  Messages  ☑ Gérer les messages …
  Avancé    ☐ Administrateur (propriétaire seulement, confirmation)
  [Enregistrer]  → récapitulatif avant/après, confirmation
Hermes : /warn (admin)  rôles autorisés : [Modérateur ✕] [+ ajouter]
         /blague         tout le monde   [restreindre…]
```

- [ ] Tests (droits, cases désactivées pour ce que l'acteur n'a pas, administrateur réservé, récapitulatif avant/après, liste blanche d'une commande, erreurs affichées), implémentation, `cd web && npm test && npm run lint && npm run build`, commit `feat(permissions): page Permissions (Discord, Hermes, Site)`.

## Déploiement (contrôleur, après relecture finale)

Sauvegarde, push, pull, migration 025, `docker compose up -d --build web-api bot web` ; vérifier : toutes les commandes fonctionnent comme avant (listes blanches vides) ; la grille Discord s'affiche ; aucune permission modifiée au déploiement.
