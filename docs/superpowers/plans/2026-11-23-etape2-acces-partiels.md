# Étape 2 — Accès partiels à l'admin : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer le « tout ou rien » de l'admin par des droits précis attribués à des rôles Discord, gérés depuis une page `/admin/acces`, avec anti-escalade, et masquer le contenu des messages du journal à qui n'a pas le droit dédié.

**Architecture:** Table `site_permissions` (rôle Discord → droit). Le site calcule l'ensemble des droits d'un membre à la connexion et à chaque réévaluation (10 min) et le stocke dans `"user"."sitePermissions"` ; web-api le lit avec la session et chaque route exige un droit précis (`require_permission`). La page `/admin/acces` écrit la table via web-api, qui applique l'anti-escalade à l'aide de la position des rôles fournie par le bot.

**Tech Stack:** PostgreSQL 15, FastAPI + asyncpg (web-api), discord.py (API interne du bot), Next.js 16 / BetterAuth / vitest (web), pytest.

**Spec:** `docs/superpowers/specs/2026-11-23-pilotage-discord-design.md` (§4.1 anti-escalade, §4.3 accès partiels) ; décision R13 de l'étape 1 (contenu des messages).

## Global Constraints

- Catalogue fermé de droits (clé → libellé français), identique côté web-api et site :
  `admin.view` « Voir l'administration », `moderation.view` « Voir la modération et le journal », `moderation.act` « Sanctionner (avertir, exclure, bannir) », `moderation.content` « Lire le contenu des messages du journal », `tickets.manage` « Gérer les tickets », `articles.write` « Écrire des articles », `articles.publish` « Publier et gérer les étiquettes », `gallery.manage` « Gérer la galerie », `content.edit` « Modifier les contenus (pages, grades, état-major) », `quests.manage` « Gérer les quêtes », `games.manage` « Gérer les jeux », `roles.manage` « Gérer les rôles », `members.roles` « Donner ou retirer des rôles », `channels.manage` « Gérer les salons », `permissions.manage` « Gérer les accès », `settings.manage` « Modifier les réglages et les commandes », `analytics.view` « Voir l'analytique ».
- Le propriétaire du serveur Discord et les détenteurs de `admin_role` ont **tous** les droits (calculés, jamais stockés dans `site_permissions`) : personne ne peut s'enfermer dehors.
- Anti-escalade (§4.1) : sauf le propriétaire, un acteur ne modifie les droits que d'un rôle **strictement sous** son rôle le plus haut (position Discord), et n'accorde ni ne retire un droit qu'il ne possède pas lui-même. Les détenteurs de `admin_role` y sont soumis.
- Comportement actuel préservé à la migration : `admin_role` → tout ; `redacteur_role` → `articles.write` et `articles.publish`.
- Un droit retiré prend effet à la prochaine réévaluation de la session (≤ 10 min, comportement existant de `role-refresh`).
- Sans `moderation.content`, le journal (`/admin/audit`, CSV) ne renvoie pas le texte des messages (`details.content`, `details.before`/`details.after`/`avant`/`après`, `details.messages`) et la recherche `q` ne porte pas sur `details`.
- Toute modification d'accès est journalisée (`audit_events`, kind `site_access`, action `update`, `details` = droits avant/après).
- Ne jamais afficher `.env` ni `docker compose config`. Commits en français terminés par la ligne Co-Authored-By indiquée dans la consigne.

## Review Focus

1. Membre dont le rôle Discord est supprimé ou dont la ligne `site_permissions` vise un rôle disparu → ses droits disparaissent, aucune erreur (Task 2).
2. Discord injoignable pendant la réévaluation → droits précédents conservés (comportement existant) ; jamais d'élévation (Task 2).
3. Acteur qui tente de modifier un rôle à la même position que le sien, ou de s'accorder un droit via son propre rôle → 403 (Task 4).
4. Appel direct à une route admin avec une session sans le droit → 403, même si la page n'est pas affichée (Task 3).
5. Utilisateur sans `moderation.content` qui cherche un mot présent uniquement dans un message supprimé → aucun résultat (Task 3).

---

### Task 1: Table, colonne de session et catalogue

**Files:**
- Create: `db/migrations/021_site_permissions.sql` ; même contenu ajouté à `db/init.sql`
- Create: `web-api/permissions.py`, `web/src/lib/permissions.ts`
- Test: `web-api/tests/test_permissions_catalog.py`

**Interfaces:**
- Produces: table `site_permissions(discord_role_id BIGINT NOT NULL, permission VARCHAR(50) NOT NULL, granted_by BIGINT, granted_at TIMESTAMPTZ DEFAULT NOW(), PRIMARY KEY (discord_role_id, permission))` ; colonne `"user"."sitePermissions" TEXT[] NOT NULL DEFAULT '{}'` ; amorçage : pour la valeur de `bot_settings.redacteur_role` (si numérique) → `articles.write`, `articles.publish` (idempotent, `ON CONFLICT DO NOTHING`).
- Produces: `PERMISSIONS: dict[str, str]` (clé → libellé, ordre du Global Constraints) dans `web-api/permissions.py` ; `export const PERMISSIONS: Record<SitePermission, string>` et `type SitePermission` dans `web/src/lib/permissions.ts`.

- [ ] **Step 1: Failing test** — `test_catalog_matches_web` : lit `web/src/lib/permissions.ts`, extrait les clés (regex), compare à `PERMISSIONS` (mêmes clés, même ordre) ; `test_catalog_has_17_entries`.
- [ ] **Step 2: Run** `cd web-api && python -m pytest -q tests/test_permissions_catalog.py` → FAIL.
- [ ] **Step 3: Implement** migration (idempotente) + les deux catalogues.
- [ ] **Step 4: Run** → PASS ; `cd web && npx tsc --noEmit` sans erreur.
- [ ] **Step 5: Commit** `feat(acces): table site_permissions et catalogue des droits`.

---

### Task 2: Calcul des droits à la connexion et à la réévaluation (site)

**Files:**
- Modify: `web/src/lib/auth.ts` (`resolveDiscordRoles` et ses deux appels, l. ~85-205), `web/src/lib/role-refresh.ts` (type `StaffRoles`, stockage)
- Test: `web/src/lib/__tests__/site-permissions.test.ts`

**Interfaces:**
- Consumes: `site_permissions`, `"user"."sitePermissions"`, `PERMISSIONS` (Task 1).
- Produces: `computePermissions(input: { isOwner: boolean; isAdminRole: boolean; roleIds: string[]; grants: Array<{ roleId: string; permission: string }> }): SitePermission[]` (fonction pure, triée, sans doublon ; propriétaire ou `admin_role` → toutes ; droits inconnus du catalogue ignorés) ; `resolveDiscordRoles` renvoie `{ isAdmin, isRedacteur, permissions }` où `isAdmin = isOwner || isAdminRole`, `isRedacteur = permissions.includes("articles.write")` ; `store` écrit `"isAdmin"`, `"isRedacteur"`, `"sitePermissions"`.
- Produces: propriétaire détecté via `GET https://discord.com/api/v10/guilds/{GUILD_ID}` (`owner_id`), mis en cache 10 min en mémoire, avec le même délai (`AbortSignal.timeout(5000)`) que l'appel `/roles` existant ; en cas d'échec → `isOwner = false`.

- [ ] **Step 1: Failing tests**

```ts
it("propriétaire ou rôle admin : tous les droits", () => {
  expect(computePermissions({ isOwner: true, isAdminRole: false, roleIds: [], grants: [] })).toHaveLength(17)
  expect(computePermissions({ isOwner: false, isAdminRole: true, roleIds: [], grants: [] })).toHaveLength(17)
})
it("union des droits des rôles du membre, sans doublon ni droit inconnu", () => {
  const grants = [{ roleId: "1", permission: "moderation.view" }, { roleId: "2", permission: "moderation.view" },
                  { roleId: "2", permission: "tickets.manage" }, { roleId: "3", permission: "articles.write" },
                  { roleId: "1", permission: "inconnu" }]
  expect(computePermissions({ isOwner: false, isAdminRole: false, roleIds: ["1", "2"], grants }))
    .toEqual(["moderation.view", "tickets.manage"])
})
it("rôle disparu ou aucun rôle : aucun droit", () => {
  expect(computePermissions({ isOwner: false, isAdminRole: false, roleIds: [], grants: [{ roleId: "9", permission: "admin.view" }] })).toEqual([])
})
it("rédacteur dérivé de articles.write", async () => { /* resolveDiscordRoles avec fetch et pool simulés */ })
it("Discord injoignable pendant la réévaluation : droits stockés inchangés", async () => { /* … */ })
```

- [ ] **Step 2: Run** `cd web && npx vitest run src/lib/__tests__/site-permissions.test.ts` → FAIL.
- [ ] **Step 3: Implement** ; la lecture `SELECT discord_role_id::text, permission FROM site_permissions WHERE discord_role_id = ANY($1::bigint[])` utilise le pool existant de `auth.ts`.
- [ ] **Step 4: Run** `cd web && npm test && npm run lint && npm run build` → vert.
- [ ] **Step 5: Commit** `feat(acces): droits du membre calculés depuis ses rôles Discord`.

---

### Task 3: Droits exigés par web-api, route par route

**Files:**
- Modify: `web-api/middleware/auth_middleware.py` (requête de session, `require_permission`, `has_permission`), `web-api/routes/auth.py` (`/auth/me` renvoie `permissions`), et toutes les routes qui appellent `require_admin`/`require_redacteur` (`admin.py`, `audit.py`, `content.py`, `grades.py`, `settings.py`, `staff.py`, `tickets.py`, `articles.py`, `tags.py`, `media.py` — vérifier la liste par `grep -rn "require_admin\|require_redacteur" web-api/routes`)
- Test: `web-api/tests/test_permissions_routes.py`

**Interfaces:**
- Consumes: `"user"."sitePermissions"`, `PERMISSIONS`.
- Produces: `user["permissions"]: frozenset[str]` ; `def has_permission(user: dict, perm: str) -> bool` (vrai si `is_admin` ou `perm` dans l'ensemble ; `perm` hors catalogue → `ValueError` à l'appel, pour attraper les fautes de frappe en test) ; `def require_permission(user: dict, perm: str) -> dict` (403 « Droit requis : <libellé> ») ; `require_admin`/`require_redacteur` conservés comme alias (`admin.view` / `articles.write`) le temps de la migration puis non utilisés dans `routes/`.
- Correspondance route → droit (à appliquer telle quelle) :
  - `admin.py` : `/admin/stats` → `admin.view` ; `/admin/commands*`, `/admin/settings*` (dont `create-channel`) → `settings.manage` ; `/admin/discord/channels`, `/admin/discord/roles` (lecture) → `admin.view` ; `/admin/kick|ban|timeout`, `POST/DELETE /admin/warns*` → `moderation.act` ; `GET /admin/warns*`, `/admin/users/search` → `moderation.view` ; `/admin/quest*`, `/admin/quests/*` → `quests.manage` ; `/admin/analytics` → `analytics.view` ; `/admin/gallery*` → `gallery.manage`.
  - `audit.py` : toutes → `moderation.view` ; masquage R13 sans `moderation.content` (liste ci-dessus, et `q` hors `details`).
  - `content.py` : jeux → `games.manage` ; pages → `content.edit`. `grades.py`, `staff.py` (écriture) → `content.edit`. `tickets.py` : routes réservées à l'admin → `tickets.manage` (les routes du membre propriétaire restent inchangées).
  - `articles.py` : créer, modifier, supprimer → `articles.write` (règle d'auteur existante conservée) ; mettre `published = true` (création ou mise à jour) → `articles.publish` en plus. `tags.py` (écriture) → `articles.publish`. `media.py` upload → `articles.write`.

- [ ] **Step 1: Failing tests** — table de cas paramétrée : pour chaque (méthode, route, droit) de la correspondance, une session **avec** le seul droit → pas 403 ; **sans** → 403 (corps « Droit requis »). Plus : `is_admin` → tout passe ; `/auth/me` renvoie `permissions` triées ; audit sans `moderation.content` → `details.content` absent, `q="motsecret"` ne cherche pas dans `details` (SQL capturé) ; avec → présent.
- [ ] **Step 2: Run** `cd web-api && python -m pytest -q tests/test_permissions_routes.py` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `cd web-api && python -m pytest -q` → vert (tests existants ajustés si leur fixture de session passe par `is_admin`).
- [ ] **Step 5: Commit** `feat(acces): chaque route admin exige un droit précis`.

---

### Task 4: Gestion des accès dans web-api, anti-escalade

**Files:**
- Modify: `bot/api.py` — `/discord/roles` ajoute `position` et `managed` ; nouvelle route `GET /discord/members/{user_id}/rank` → `{"top_position": int, "is_owner": bool, "role_ids": [str]}` (404 si membre absent)
- Create: `web-api/routes/access.py` (router `prefix="/admin"`, enregistré dans `web-api/main.py`)
- Test: `web-api/tests/test_access.py`, `bot/tests/test_api_rank.py`

**Interfaces:**
- Consumes: `site_permissions`, `PERMISSIONS`, `require_permission` (Task 3), `_bot()` de web-api, `_log`/`audit_events`.
- Produces:
  - `GET /admin/access` (`permissions.manage`) → `{"catalog": [{"key","label"}], "roles": [{"id","name","color","position","managed","permissions": [str], "editable": bool}], "actor": {"top_position": int, "is_owner": bool, "permissions": [str]}}` ; `editable` = propriétaire, ou position < `top_position` de l'acteur.
  - `PUT /admin/access/{role_id}` (`permissions.manage`) body `{"permissions": [str]}` → remplace l'ensemble des droits du rôle ; refus 403 si rôle non éditable, si un droit ajouté **ou retiré** n'est pas dans les droits de l'acteur (propriétaire exempté) ; 422 si droit hors catalogue ; 404 si rôle inconnu ; écrit `audit_events` (`site_access`/`update`, `details.before`/`details.after`, cible = rôle).
  - `def check_escalation(actor: dict, role_position: int, before: set[str], after: set[str]) -> str | None` (message d'erreur ou `None`), fonction pure.

- [ ] **Step 1: Failing tests**

```python
def test_cannot_edit_role_at_or_above_own():
    actor = {"top_position": 10, "is_owner": False, "permissions": {"permissions.manage", "moderation.view"}}
    assert check_escalation(actor, 10, set(), {"moderation.view"}) is not None
    assert check_escalation(actor, 9, set(), {"moderation.view"}) is None

def test_cannot_grant_or_remove_what_actor_lacks():
    actor = {"top_position": 10, "is_owner": False, "permissions": {"permissions.manage"}}
    assert check_escalation(actor, 5, set(), {"settings.manage"}) is not None
    assert check_escalation(actor, 5, {"settings.manage"}, set()) is not None

def test_owner_is_exempt():
    assert check_escalation({"top_position": 0, "is_owner": True, "permissions": set()}, 99, set(), {"settings.manage"}) is None
```

  plus tests de route : 403 / 422 / 404, remplacement effectif (SQL capturé), ligne `site_access` écrite ; bot : `rank` renvoie la position du plus haut rôle et `is_owner`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** `cd web-api && python -m pytest -q` et `cd bot && python -m pytest -q` → vert.
- [ ] **Step 5: Commit** `feat(acces): gestion des droits par rôle avec anti-escalade`.

---

### Task 5: Site — admin filtrée par droit et page `/admin/acces`

**Files:**
- Modify: `web/src/lib/admin-gate.ts` (`adminGate(permission: SitePermission)`), chaque page de `web/src/app/[locale]/admin/**/page.tsx` (droit de la correspondance de Task 3 ; vue d'ensemble → `admin.view`), `web/src/lib/admin-sections.ts` (droit par section), `web/src/components/admin/admin-nav.tsx` (n'affiche que les sections autorisées), `web/src/components/layout/nav-links.ts` + `navbar.tsx` (« Admin » si au moins un droit d'admin, « Écrire un article » si `articles.write`), type `SessionUser` (+ `permissions`)
- Create: `web/src/app/[locale]/admin/acces/page.tsx`, `web/src/components/admin/access-grid.tsx`
- Test: `web/src/app/[locale]/admin/__tests__/acces.test.tsx`, `web/src/lib/__tests__/admin-gate.test.ts`

**Interfaces:**
- Consumes: `/auth/me` (`permissions`), `GET/PUT /admin/access` (Task 4), `PERMISSIONS` (Task 1).
- Produces: section « Accès » (`/admin/acces`, droit `permissions.manage`) ajoutée à `ADMIN_SECTIONS`.

Interface de `/admin/acces` :
```
Accès                                               (vous : Modérateur, position 12)
Rôle ▾ (un rôle par ligne, ordre Discord)          Droits (cases groupées : Modération · Contenu · Serveur · Administration)
🟣 Modérateur        [✓ Voir la modération] [✓ Sanctionner] [☐ Lire le contenu des messages] …   [Enregistrer]
🔵 Rédacteur         [✓ Écrire des articles] [✓ Publier] …
🟡 GroFlex (admin)   « Tous les droits (rôle administrateur) » — non modifiable
⚪ Rôle au-dessus     grisé : « Au-dessus de votre rôle »
```
Cases grisées pour les droits que l'acteur n'a pas ; enregistrement par rôle avec message de succès/erreur (texte de l'erreur 403 de l'API) ; rappel « effet sous 10 minutes ».

- [ ] **Step 1: Failing tests** — `adminGate("moderation.view")` : session avec le droit → ok, sans → page « accès refusé », visiteur → connexion ; la navigation admin ne liste que les sections autorisées ; « Admin » absent du menu pour un membre sans droit ; grille : rôle non éditable grisé, droit non possédé désactivé, PUT envoyé avec la liste cochée, erreur 403 affichée.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** `cd web && npm test && npm run lint && npm run build` → vert.
- [ ] **Step 5: Commit** `feat(acces): admin filtrée par droit et page Accès`.

---

## Déploiement (contrôleur, après relecture finale)

1. Sauvegarde (`~/bin/hermes-backup.sh`), `git push`, sur le serveur `git pull`, migration `021_site_permissions.sql`, puis aussitôt `docker compose up -d --build bot web-api web`.
2. Vérifier : le propriétaire et GroFlex voient toute l'admin ; `/admin/acces` liste les rôles ; donner `moderation.view` à un rôle test → un membre de ce rôle voit Modération (après reconnexion ou ≤ 10 min) mais pas Réglages ; le journal ne montre pas le contenu des messages sans `moderation.content`.
