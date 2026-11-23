# Étape 3 — Rôles et règles automatiques : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Depuis l'admin, créer/modifier/supprimer des rôles Discord, en donner ou retirer à des membres (un par un ou en lot), et gérer des règles « condition → rôle » qui remplacent les rôles codés en dur (Batman, niveaux, succès), avec aperçu avant application.

**Architecture:** Table `role_rules` ; moteur pur dans le bot (`bot/utils/role_rules.py`) appelé aux évènements (XP, succès, fin de session vocale) et par une réconciliation périodique pour les règles validées ; l'API interne du bot exécute les actions Discord ; web-api applique droits et anti-escalade ; le site offre les pages `/admin/roles` et `/admin/regles`.

**Tech Stack:** PostgreSQL 15, discord.py, FastAPI (bot interne + web-api), Next.js 16 / vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-11-23-pilotage-discord-design.md` §4.1 (anti-escalade, confirmations, erreurs traduites) et §4.4 (rôles, attribution, règles, migration « aucun membre ne gagne ni ne perd de rôle »).

## Global Constraints

- Droits du site (étape 2) : gérer les rôles et les règles → `roles.manage` ; donner/retirer des rôles à des membres → `members.roles`.
- Anti-escalade (§4.1) : sauf le propriétaire, un acteur ne crée, modifie, supprime, attribue ou retire qu'un rôle **strictement sous** son rôle le plus haut ; le bot ne touche qu'aux rôles strictement sous son propre rôle le plus haut ; jamais `@everyone` ni un rôle `managed` (intégration). L'étape 3 ne modifie PAS les permissions Discord d'un rôle (étape 6).
- Confirmations : suppression d'un rôle (nombre de membres concernés affiché), attribution/retrait en lot (nombre affiché), application d'une règle (aperçu : qui gagne, qui perd).
- Conditions des règles (liste fermée) : `voice_hours` (heures de vocal total), `messages` (messages total), `level` (niveau XP), `grade` (slug de `grades`, vrai si niveau ≥ `level_min`), `achievement` (id de succès débloqué), `streak_days` (série vocale en cours), `bumps`, `invites`.
- Une règle : condition + valeur, rôle cible (`role_id`) **ou** « créer au premier déblocage » (succès seulement : `create_role_name`, `create_role_color`), `remove_when_lost` (défaut faux), `exclusive_group` (facultatif : un seul rôle du groupe à la fois, le plus élevé), `active`, `reconcile` (défaut **faux** = mode aperçu : seule l'évaluation à l'évènement agit, comme aujourd'hui).
- Conflits refusés à l'enregistrement (422, explication française) : deux règles actives visant le même rôle dont l'une a `remove_when_lost` ; une règle `achievement` sans succès existant ; un rôle cible non gérable par le bot.
- Bascule sans effet pour les membres : les comportements actuels deviennent des règles **sans réconciliation** (Batman : `voice_hours ≥ voice_hours_for_role` → `role_batman` ; niveaux : `role_level_N` s'ils sont réglés ; succès : un « créer au premier déblocage » par succès, nom `{icône} {nom}`, couleur selon le palier comme aujourd'hui) ; le code codé en dur correspondant est retiré.
- Toute action est journalisée dans `audit_events` (kinds `role`, `member_role`, `setting` pour les règles ; source `site` ; auteur = membre du site) ; l'entrée d'audit Discord correspondante (auteur = bot) complète la ligne existante (mécanisme de l'étape 1).
- Écritures Discord en lot : séquentielles côté bot (discord.py gère les limites), jamais plus de 500 membres par requête, réponse immédiate avec un identifiant de travail et un état consultable.
- Ne jamais afficher `.env` ni `docker compose config`. Commits en français terminés par la ligne Co-Authored-By indiquée dans la consigne. Migrations manuelles : `db/migrations/022_role_rules.sql`.

## Review Focus

1. Membre qui remplit deux règles d'un même `exclusive_group` → seul le rôle de la règle au seuil le plus élevé est gardé (Task 1).
2. Rôle cible supprimé dans Discord → la règle est signalée « rôle introuvable » dans l'admin, aucune erreur en boucle dans le bot (Task 2).
3. Attribution en lot interrompue (bot redémarré) → état « interrompu » avec le nombre traité, pas de reprise silencieuse (Task 3).
4. Création de rôle avec un nom vide, > 100 caractères ou une couleur invalide → 422 (Task 4).
5. Changement du rôle d'une règle avec « retirer l'ancien » → aperçu du nombre puis confirmation ; sans la case, l'ancien rôle reste (Task 4/5).

---

### Task 1: Table et moteur pur

**Files:**
- Create: `db/migrations/022_role_rules.sql` (+ `db/init.sql`), `bot/utils/role_rules.py`
- Test: `bot/tests/test_role_rules.py`

**Interfaces:**
- Produces: table `role_rules(id SERIAL PK, condition_type VARCHAR(20) NOT NULL, condition_value TEXT NOT NULL, role_id BIGINT, create_role_name VARCHAR(100), create_role_color INT, remove_when_lost BOOLEAN NOT NULL DEFAULT FALSE, exclusive_group VARCHAR(50), active BOOLEAN NOT NULL DEFAULT TRUE, reconcile BOOLEAN NOT NULL DEFAULT FALSE, created_by BIGINT, updated_at TIMESTAMPTZ DEFAULT NOW(), CHECK (role_id IS NOT NULL OR (condition_type = 'achievement' AND create_role_name IS NOT NULL)))` ; amorçage idempotent selon le Global Constraints (Batman depuis `bot_settings`, niveaux s'ils existent, une règle par succès ; couleur de palier = même table que `achievements_notifier._TIER_ROLE_COLORS`).
- Produces (`bot/utils/role_rules.py`, pur) : `CONDITIONS: frozenset[str]` ; `@dataclass Rule(id, condition_type, condition_value, role_id, remove_when_lost, exclusive_group, active, reconcile, create_role_name, create_role_color)` ; `@dataclass MemberStats(voice_hours: float, messages: int, level: int, streak_days: int, bumps: int, invites: int, achievements: frozenset[int])` ; `def matches(rule: Rule, stats: MemberStats, grades: dict[str, int]) -> bool` ; `def plan_changes(rules: list[Rule], stats: MemberStats, member_role_ids: set[int], grades: dict[str, int]) -> tuple[set[int], set[int]]` (à ajouter, à retirer ; retrait seulement si `remove_when_lost` ou perdant d'un `exclusive_group` ; règles inactives ignorées ; règles sans `role_id` ignorées ici) ; `def find_conflicts(rules: list[Rule]) -> list[str]`.

- [ ] **Step 1: Failing tests** — `matches` pour chaque condition (seuil atteint/non) ; `grade` via `grades={"sergent": 20}` ; `plan_changes` : ajout simple ; pas de retrait sans `remove_when_lost` ; retrait avec ; `exclusive_group` garde le seuil le plus haut et retire l'autre ; inactive ignorée ; `find_conflicts` détecte deux règles même rôle dont une `remove_when_lost`.
- [ ] **Step 2: Run** `cd bot && python -m pytest -q tests/test_role_rules.py` → FAIL.
- [ ] **Step 3: Implement.** **Step 4: Run** `cd bot && python -m pytest -q` → PASS.
- [ ] **Step 5: Commit** `feat(roles): table des règles de rôles et moteur d'évaluation`.

---

### Task 2: Moteur branché dans le bot (évènements, réconciliation, aperçu)

**Files:**
- Create: `bot/cogs/system/role_engine.py`
- Modify: `bot/cogs/gamification/xp.py` (retirer `_grant_level_role`/`LEVEL_ROLE_KEYS` → appel du moteur), `bot/cogs/moderation/voice.py` (retirer Batman → appel du moteur en fin de session), `bot/cogs/system/achievements_notifier.py` (rôle de succès → moteur, création au premier déblocage conservée, `backfill_roles` retiré au profit de la réconciliation des règles validées)
- Test: `bot/tests/test_role_engine.py`

**Interfaces:**
- Consumes: `role_rules` (Task 1), `record` (journal, étape 1).
- Produces (cog `RoleEngine`) : `async def evaluate_member(member: discord.Member) -> tuple[list[int], list[int]]` (applique et renvoie ajoutés/retirés ; « créer au premier déblocage » : crée le rôle, enregistre `role_id` dans la règle) ; `async def reload()` ; `async def preview(rule_id: int) -> dict` → `{"gain": [user_id…], "lose": [user_id…], "missing_role": bool}` sur tous les membres ; `async def apply(rule_id: int) -> dict` (réconcilie une règle, même forme + compte) ; tâche `@tasks.loop(hours=6)` réconciliant les règles `reconcile = true` ; statistiques lues en **une** requête par lot de membres (vocal, messages, XP, série, bumps, invitations, succès).
- Les rôles introuvables ou non gérables : un avertissement par règle et par valeur (pas en boucle), règle marquée `missing_role` dans l'aperçu.

- [ ] **Step 1: Failing tests** (faux guild/membres/rôles et `db_manager` simulé) : fin de session vocale ≥ 100 h → Batman ajouté une fois ; montée au niveau d'une règle → rôle ajouté ; succès débloqué avec règle « créer » → rôle créé puis `role_id` enregistré, attribué ; `preview` liste gagnants/perdants sans rien modifier ; règle au rôle supprimé → `missing_role`, un seul avertissement ; les anciens chemins codés en dur n'existent plus (`LEVEL_ROLE_KEYS` absent, plus d'appel `settings.get_role(..., 'role_batman')`).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** `cd bot && python -m pytest -q` et `cd bot && python -c "import main"` → OK.
- [ ] **Step 5: Commit** `feat(roles): règles appliquées par le bot, rôles codés en dur retirés`.

---

### Task 3: API interne du bot (rôles, membres, lots, règles)

**Files:**
- Modify: `bot/api.py`
- Test: `bot/tests/test_api_roles.py`

**Interfaces:**
- Consumes: `RoleEngine` (Task 2).
- Produces (toutes protégées par `_require_token`) :
  - `GET /discord/roles` enrichi : `members` (nombre), `below_bot` (bool), en plus de `position`/`managed` existants.
  - `POST /discord/roles` `{name, color, hoist, mentionable}` → rôle créé (sous le bot) ; `PATCH /discord/roles/{id}` mêmes champs + `position` (bornée sous le bot) ; `DELETE /discord/roles/{id}` ; refus 403 (français) si `@everyone`, `managed` ou pas sous le bot ; `reason` d'audit Discord = « via le site par <pseudo> » (champ `actor_name` du corps).
  - `POST /discord/members/{user_id}/roles/{role_id}` et `DELETE` idem.
  - `POST /discord/roles/{role_id}/bulk` `{"action": "add"|"remove", "user_ids": [str] (≤ 500) | null, "from_role_id": str | null}` → `{"job_id": str}` ; `GET /discord/jobs/{job_id}` → `{"state": "running"|"done"|"interrupted"|"failed", "done": int, "total": int, "errors": int}` (travaux en mémoire ; au redémarrage, un travail inconnu répond 404 et le site affiche « interrompu »).
  - `POST /role-rules/reload`, `GET /role-rules/{id}/preview`, `POST /role-rules/{id}/apply`.

- [ ] **Step 1: Failing tests** (TestClient sur l'app FastAPI du bot avec guild simulé) : création sous le bot ; refus `managed`/`@everyone`/au-dessus ; lot de 3 membres → job `done` 3/3 ; `user_ids` > 500 → 422 ; preview renvoie la forme attendue.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** `cd bot && python -m pytest -q` → PASS.
- [ ] **Step 5: Commit** `feat(roles): API interne du bot pour les rôles, les membres et les règles`.

---

### Task 4: web-api (droits, anti-escalade, règles, journal)

**Files:**
- Create: `web-api/routes/roles.py` (router `prefix="/admin"`, enregistré dans `web-api/main.py`)
- Test: `web-api/tests/test_roles.py`

**Interfaces:**
- Consumes: Task 3 (via `_bot`), `require_permission`, rang de l'acteur (`GET /discord/members/{id}/rank`, étape 2) et `check_escalation`-like : réutiliser/extraire la logique de position de `web-api/routes/access.py`.
- Produces :
  - `GET /admin/roles` (`roles.manage` ou `members.roles`) → rôles + `editable` (sous l'acteur et sous le bot, non managed).
  - `POST/PATCH/DELETE /admin/roles[/{id}]` (`roles.manage`) ; validation : nom 1–100 caractères, couleur 0–0xFFFFFF ; suppression : corps `{"confirm_members": int}` qui doit égaler le nombre actuel de membres du rôle (sinon 409 « le nombre a changé »).
  - `POST/DELETE /admin/members/{user_id}/roles/{role_id}` (`members.roles`) ; `POST /admin/roles/{role_id}/bulk` (`members.roles`) `{action, user_ids?, from_role_id?, confirm_count}` ; `GET /admin/jobs/{job_id}`.
  - `GET/POST/PATCH/DELETE /admin/role-rules[/{id}]` (`roles.manage`) ; validation (conditions, valeurs, succès existant, `find_conflicts` porté en Python dans web-api ou appel bot) ; `GET /admin/role-rules/{id}/preview` ; `POST /admin/role-rules/{id}/apply` `{"confirm": true, "remove_previous_role_id": str | null}` ; `PATCH` avec `reconcile: true` exige qu'un aperçu ait été consulté (le site envoie `preview_seen: true`) ; après toute écriture → `POST /role-rules/reload` au bot.
  - Journal : chaque action → `_log` (kinds `role`, `member_role`, `setting`).

- [ ] **Step 1: Failing tests** : droits (403 sans le bon droit) ; anti-escalade (rôle ≥ acteur → 403, propriétaire exempté) ; validations 422 ; suppression avec `confirm_members` faux → 409 ; conflit de règles → 422 ; ligne de journal écrite ; reload envoyé au bot.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** `cd web-api && python -m pytest -q` → PASS.
- [ ] **Step 5: Commit** `feat(roles): gestion des rôles et des règles dans web-api`.

---

### Task 5: Site (pages Rôles et Règles, rôles d'un membre, lots)

**Files:**
- Create: `web/src/app/[locale]/admin/roles/page.tsx`, `web/src/app/[locale]/admin/regles/page.tsx`, composants `roles-admin.tsx`, `role-rules-admin.tsx`, `bulk-roles.tsx` dans `web/src/components/admin/`
- Modify: `web/src/lib/admin-sections.ts` (sections « Rôles » `roles.manage`, « Règles » `roles.manage`), `web/src/components/admin/member-inspector.tsx` (rôles du membre : ajouter/retirer si `members.roles`), client/types API
- Test: `web/src/app/[locale]/admin/__tests__/roles.test.tsx`, `regles.test.tsx`

Interfaces visibles :
```
Rôles                                         [+ Nouveau rôle]
● Modérateur   12 membres   [Modifier] [Supprimer]            (au-dessus de vous : grisé)
Attribuer en lot : rôle [Fortnite ▾]  [Ajouter|Retirer]  à [membres choisis | tous ceux qui ont le rôle ▾]  → « 37 membres concernés » [Confirmer]
```
```
Règles automatiques                           [+ Nouvelle règle]
Condition                  | Rôle donné        | Retiré si perdu | Mode       | Actif
Vocal total ≥ 100 h        | 🦇 Batman         | non            | Aperçu     | ✓   [Voir l'aperçu] [Valider]
Succès « Moulin à paroles »| créé au déblocage | non            | Aperçu     | ✓
```
Le mode « Aperçu » passe à « Appliquée » seulement après « Voir l'aperçu » puis « Valider » (affiche qui gagne/perd) ; « rôle introuvable » signalé ; changement du rôle d'une règle : case « retirer l'ancien rôle aux N membres » avec confirmation.

- [ ] **Step 1: Failing tests** : sections visibles selon droits ; création/suppression avec confirmation du nombre ; lot → suivi du travail jusqu'à « terminé » / « interrompu » ; règle : aperçu puis validation ; erreur 403/409/422 affichée (texte de l'API).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** `cd web && npm test && npm run lint && npm run build` → vert.
- [ ] **Step 5: Commit** `feat(roles): pages Rôles et Règles, rôles d'un membre et attribution en lot`.

---

## Déploiement (contrôleur, après relecture finale)

1. Sauvegarde, `git push`, `git pull` serveur, migration `022_role_rules.sql`, puis `docker compose up -d --build bot web-api web`.
2. Vérifier : aucune attribution/retrait massif au démarrage (journal `member_role` des 10 premières minutes) ; `/admin/regles` montre Batman et 35 règles de succès en « Aperçu » ; l'aperçu de Batman liste les gagnants éventuels ; création d'un rôle test, attribution à un membre, suppression.
