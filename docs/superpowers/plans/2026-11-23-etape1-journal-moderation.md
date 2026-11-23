# Étape 1 — Journal unique et page Modération : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un journal unique en base (`audit_events`) de **tout ce qui se passe sur le serveur** (commandes, sanctions, messages modifiés/supprimés, vocal, membres, rôles, salons, invitations, fils, émojis, réglages du serveur) et des actions du site, consultable dans `/admin/moderation` avec des filtres qui s'adaptent au type choisi, et export CSV.

**Architecture:** Nouvelle table `audit_events` (migration 020, reprise de `admin_logs`). Écrivains : web-api (`_log`, source `site`), bot (module `utils/audit_events.py` : commandes, sanctions Hermes, entrées du journal d'audit Discord, purge 365 j). Lecture : web-api `GET /admin/audit` et `GET /admin/audit.csv`. Affichage : composant `AuditJournal` qui remplace `AdminLogs`.

**Tech Stack:** PostgreSQL 15, FastAPI + asyncpg (web-api), discord.py 2.x (bot), Next.js 16 / React 19 / Tailwind 4 / vitest (web), pytest.

**Spec:** `docs/superpowers/specs/2026-11-23-pilotage-discord-design.md` (§4.1, §4.2)

## Global Constraints

- Async uniquement ; aucune I/O bloquante dans le bot ni dans web-api.
- Toute écriture de journal ne lève jamais d'exception vers l'appelant (une panne de journal ne casse pas une sanction).
- Rétention : lignes de plus de **365 jours** purgées une fois par jour.
- Sources : `site`, `hermes`, `discord`. Kinds : `command`, `sanction`, `message`, `voice`, `member`, `member_role`, `role`, `channel`, `thread`, `invite`, `emoji`, `server`, `permission`, `setting`, `game`, `site_access`, `content`.
- Actions par kind (liste fermée, sert aux filtres) : `message` → `edit`, `delete`, `bulk_delete` ; `voice` → `join`, `leave`, `move`, `server_mute`, `server_deafen`, `self_mute`, `self_deafen`, `stream_start`, `stream_stop` ; `member` → `join`, `leave`, `nickname`, `avatar` ; `member_role` → `add`, `remove` ; `role`/`channel`/`thread`/`emoji` → `create`, `update`, `delete` ; `invite` → `create`, `delete` ; `server` → `update` ; `sanction` → `kick`, `ban`, `unban`, `timeout`, `untimeout`, `warn`, `clear`, `message_delete` ; `command` → `/<nom>`.
- Contenu des messages : enregistré pour `edit` (avant/après) et `delete` (si le message était en cache ; sinon `"[contenu indisponible]"`), tronqué à 2 000 caractères ; les messages **envoyés** ne sont pas journalisés (volume). Les messages des bots sont ignorés.
- Qui a fait quoi : les changements structurels (rôles, salons, fils, émojis, invitations, réglages du serveur, rôles et pseudos des membres) sont lus **dans le journal d'audit Discord** (auteur et avant/après fiables) ; les évènements sans entrée d'audit (vocal, message modifié/supprimé par son auteur, arrivée/départ) viennent des évènements Discord directs. Une suppression de message par un modérateur complète la ligne `message`/`delete` avec `details.deleted_by`.
- Commandes anonymes (`confess`) : valeurs des options remplacées par `"[masqué]"`.
- Entrée du journal d'audit Discord dont l'auteur est le bot : pas de doublon ; elle complète la ligne `site`/`hermes` correspondante (même `action`, même `target_id`, moins de 120 s) via `details.discord_audit_id` ; sans correspondance, ligne `source='discord'`.
- Accès : routes de lecture réservées aux admins (`require_admin`) — les accès partiels arrivent à l'étape 2.
- Textes de l'interface en français ; dates stockées en UTC, affichées en Europe/Paris.
- Migrations SQL manuelles, numérotées : celle-ci est `db/migrations/020_audit_events.sql` ; `db/init.sql` reçoit la même table pour les nouvelles installations.
- Commits en français, terminés par `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Ne jamais afficher `.env` ni `docker compose config`.

## Review Focus

1. Message modifié/supprimé avec pièces jointes et embeds → noms des fichiers et nombre d'embeds enregistrés, pas les fichiers (Task 4).
2. Valeur d'option de commande très longue ou binaire (pièce jointe) → tronquée à 500 caractères, pièce jointe enregistrée par son nom de fichier seulement (Task 2).
3. Cellule CSV commençant par `=`, `+`, `-`, `@` (nom Discord piégé) → préfixée d'une apostrophe, pas de formule dans le tableur (Task 5).
4. Bot sans la permission « Voir les logs du serveur » → aucun crash, un avertissement unique dans les logs (Task 3).
5. Filtre de dates : jour « au » inclus jusqu'à 23:59:59 Europe/Paris ; dates invalides → 422, pas 500 (Task 5).
6. Commande utilisée en message privé (pas de salon ni de serveur) → ligne enregistrée avec `channel_id` nul (Task 3).

---

### Task 1: Table `audit_events` et écriture côté web-api

**Files:**
- Create: `db/migrations/020_audit_events.sql`
- Modify: `db/init.sql` (après la table `admin_logs`, ~l. 552)
- Modify: `web-api/routes/admin.py:42-69` (`_log`)
- Test: `web-api/tests/test_audit_log_write.py`

**Interfaces:**
- Produces: table `audit_events(id BIGSERIAL PK, occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), kind VARCHAR(32) NOT NULL, action VARCHAR(100) NOT NULL, source VARCHAR(16) NOT NULL CHECK (source IN ('site','hermes','discord')), actor_id BIGINT, actor_name VARCHAR(255), target_id BIGINT, target_name VARCHAR(255), channel_id BIGINT, channel_name VARCHAR(255), success BOOLEAN NOT NULL DEFAULT TRUE, details JSONB NOT NULL DEFAULT '{}')` ; index `(occurred_at DESC)`, `(kind, occurred_at DESC)`, `(actor_id)`, `(target_id)`, `(action)`.
- Produces: `KIND_OF_ACTION: dict[str, str]` dans `web-api/routes/admin.py` ; `_log(action_type, actor_id, target_id=None, details=None)` garde sa signature et écrit dans `audit_events` avec `source='site'`.

- [ ] **Step 1: Write the failing tests**

```python
def test_log_writes_audit_event_with_kind_and_source(fake_db):
    import asyncio
    from routes.admin import _log
    fake_db.on("FROM user_voice_data", {"name": "Kéfir"})
    asyncio.run(_log("kick", 1, 2, {"reason": "spam"}))
    method, sql, args = [c for c in fake_db.calls if c[0] == "execute"][0]
    assert "INSERT INTO audit_events" in sql
    assert args[:4] == ("sanction", "kick", "site", 1)
    assert "admin_logs" not in sql

def test_log_kinds_cover_existing_actions():
    from routes.admin import KIND_OF_ACTION
    assert KIND_OF_ACTION["command_toggle"] == "setting"
    assert {KIND_OF_ACTION[a] for a in ("kick", "ban", "timeout", "warn", "delete_warn")} == {"sanction"}
    assert KIND_OF_ACTION["quest_deploy"] == "content"

def test_log_never_raises(fake_db):
    import asyncio
    from routes.admin import _log
    fake_db.on("INSERT INTO audit_events", lambda *a: (_ for _ in ()).throw(RuntimeError("db down")))
    asyncio.run(_log("ban", 1, 2))  # ne lève pas
```

- [ ] **Step 2: Run to verify they fail** — `cd web-api && python -m pytest -q tests/test_audit_log_write.py` → FAIL (`KIND_OF_ACTION` absent, INSERT dans admin_logs).

- [ ] **Step 3: Write the migration** `020_audit_events.sql` : création de la table et des index (idempotente, `IF NOT EXISTS`), puis reprise de l'historique :
  `INSERT INTO audit_events (occurred_at, kind, action, source, actor_id, actor_name, target_id, target_name, details) SELECT created_at, CASE … END, action_type, 'site', actor_id, actor_name, target_id, target_name, details FROM admin_logs WHERE NOT EXISTS (SELECT 1 FROM audit_events)` avec le même mapping que `KIND_OF_ACTION` (défaut `'setting'`). `admin_logs` n'est pas supprimée. Ajouter la table et les index à `db/init.sql`.

- [ ] **Step 4: Implement** `KIND_OF_ACTION` (kick/ban/timeout/warn/delete_warn → sanction ; command_toggle → setting ; quest_* → content ; défaut `setting`) et réécrire l'INSERT de `_log` vers `audit_events (kind, action, source, actor_id, actor_name, target_id, target_name, details)`.

- [ ] **Step 5: Run tests** — `cd web-api && python -m pytest -q` → tout PASS.

- [ ] **Step 6: Commit** — `git add db/migrations/020_audit_events.sql db/init.sql web-api/routes/admin.py web-api/tests/test_audit_log_write.py` ; `git commit -m "feat(journal): table audit_events, reprise d'admin_logs, écriture du site"`.

---

### Task 2: Module de journal du bot (fonctions pures + écriture)

**Files:**
- Create: `bot/utils/audit_events.py`
- Test: `bot/tests/test_audit_events.py`

**Interfaces:**
- Consumes: table `audit_events` (Task 1) ; `utils.database` (`db_manager.execute/fetchval/fetchrow`).
- Produces:
  - `MASKED_COMMANDS: frozenset[str] = frozenset({"confess"})`
  - `MAX_VALUE_LEN = 500`
  - `def command_options(command_name: str, raw: dict[str, object]) -> dict[str, str]` — valeurs converties en texte, tronquées à `MAX_VALUE_LEN` (suffixe `…`), pièce jointe (`discord.Attachment`) → `filename`, membre/rôle/salon → `"<nom> (<id>)"`, tout masqué si `command_name in MASKED_COMMANDS`.
  - `def map_audit_action(action: discord.AuditLogAction) -> tuple[str, str] | None` — `kick→("sanction","kick")`, `ban→("sanction","ban")`, `unban→("sanction","unban")`, `member_update` avec timeout → géré par l'appelant (voir Task 3), `message_delete→("sanction","message_delete")`, `message_bulk_delete→("sanction","message_bulk_delete")`, autre → `None`.
  - `def timeout_change(before, after) -> str | None` — `"timeout"` si `timed_out_until` passe de nul à une date future, `"untimeout"` si l'inverse, sinon `None`.
  - `async def record(*, kind: str, action: str, source: str, actor_id: int | None, actor_name: str | None, target_id: int | None = None, target_name: str | None = None, channel_id: int | None = None, channel_name: str | None = None, success: bool = True, details: dict | None = None) -> int | None` — INSERT … RETURNING id ; ne lève jamais (log warning, retourne `None`).
  - `async def attach_discord_entry(*, action: str, target_id: int | None, audit_id: int, window_s: int = 120) -> bool` — met `details = details || {"discord_audit_id": …}` sur la ligne la plus récente `source IN ('site','hermes') AND action=$ AND target_id=$ AND occurred_at > NOW() - window AND NOT details ? 'discord_audit_id'` ; retourne True si une ligne a été complétée.
  - `async def purge_older_than(days: int = 365) -> int` — DELETE, retourne le nombre de lignes.

- [ ] **Step 1: Write the failing tests** (fonctions pures + SQL via un faux `db_manager` monkeypatché, sur le modèle de `bot/tests/test_settings_warn_once.py`)

```python
def test_command_options_truncates_and_masks():
    from utils.audit_events import command_options, MAX_VALUE_LEN
    long = "x" * 900
    assert len(command_options("blague", {"texte": long})["texte"]) == MAX_VALUE_LEN + 1  # « … »
    assert command_options("confess", {"message": "secret"}) == {"message": "[masqué]"}

def test_map_audit_action():
    import discord
    from utils.audit_events import map_audit_action
    assert map_audit_action(discord.AuditLogAction.kick) == ("sanction", "kick")
    assert map_audit_action(discord.AuditLogAction.ban) == ("sanction", "ban")
    assert map_audit_action(discord.AuditLogAction.channel_create) is None

def test_timeout_change():
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace as N
    from utils.audit_events import timeout_change
    fut = datetime.now(timezone.utc) + timedelta(minutes=10)
    assert timeout_change(N(timed_out_until=None), N(timed_out_until=fut)) == "timeout"
    assert timeout_change(N(timed_out_until=fut), N(timed_out_until=None)) == "untimeout"
    assert timeout_change(N(timed_out_until=None), N(timed_out_until=None)) is None

def test_record_never_raises(monkeypatch):  # db_manager.fetchval lève → record retourne None
    ...

def test_attach_discord_entry_targets_recent_site_or_hermes_row(monkeypatch):
    # capture le SQL : contient "source IN ('site','hermes')", "discord_audit_id", intervalle 120 s
    ...

def test_purge_uses_365_days(monkeypatch):
    # capture le SQL du DELETE et l'argument 365
    ...
```

  (Les trois derniers : assertions sur le SQL capturé et les arguments, comme indiqué en commentaire.)

- [ ] **Step 2: Run to verify they fail** — `cd bot && python -m pytest -q tests/test_audit_events.py` → FAIL (module absent).
- [ ] **Step 3: Implement** `bot/utils/audit_events.py` selon les signatures ci-dessus (`timeout_change` lit l'attribut `timed_out_until` des objets `AuditLogDiff`/membre).
- [ ] **Step 4: Run tests** — `cd bot && python -m pytest -q` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(journal): module audit_events du bot"`.

---

### Task 3: Branchements du bot (commandes, sanctions Hermes, journal d'audit Discord, purge)

**Files:**
- Modify: `bot/main.py:227-250` (`on_app_command_completion`) + ajouter `on_app_command_error` (enregistrer puis laisser la gestion d'erreur existante telle quelle)
- Modify: `bot/cogs/moderation/kick.py`, `tempban.py` (ban et unban), `tempmute.py`, `clear.py`, `warn.py` — un `record(kind="sanction", source="hermes", …)` après l'action réussie
- Create: `bot/cogs/system/audit_journal.py` (cog : `on_audit_log_entry_create`, tâche de purge quotidienne)
- Modify: liste de chargement des cogs si elle est explicite (vérifier `bot/main.py`)
- Test: `bot/tests/test_audit_journal.py`

**Interfaces:**
- Consumes: `record`, `attach_discord_entry`, `purge_older_than`, `command_options`, `map_audit_action`, `timeout_change` (Task 2).
- Produces: actions journalisées — commandes : `kind="command"`, `action="/<nom complet>"` (sous-commandes incluses, ex. `/rang voir`), `details={"options": …}`, `success` ; sanctions Hermes : actions `kick`, `ban`, `unban`, `timeout`, `warn`, `clear` (`details`: `reason`, `duration_minutes`, `count`).
- Produces: `def should_merge(entry_user_id: int, bot_user_id: int) -> bool` dans `audit_journal.py` (vrai si l'auteur de l'entrée est le bot).

- [ ] **Step 1: Write the failing tests**

```python
def test_should_merge_only_bot_entries():
    from cogs.system.audit_journal import should_merge
    assert should_merge(42, 42) is True
    assert should_merge(7, 42) is False

def test_bot_entry_without_match_falls_back_to_discord_row(monkeypatch):
    # attach_discord_entry → False ⇒ record(source="discord", actor_id=<bot>) est appelé
    ...

def test_human_entry_recorded_as_discord_source(monkeypatch):
    # entrée kick d'un modérateur humain ⇒ record(kind="sanction", action="kick", source="discord", actor_id=<modo>)
    ...

def test_dm_command_has_no_channel(monkeypatch):
    # interaction sans guild/channel ⇒ record(..., channel_id=None)
    ...
```

- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement** :
  - `on_app_command_completion` / `on_app_command_error` → `record(kind="command", source="hermes", actor_id=interaction.user.id, actor_name=display_name, channel_id/channel_name si présents, action="/"+command.qualified_name, success=…, details={"options": command_options(...)})` (options lues dans `interaction.namespace`) ; l'existant (stats, succès) est conservé.
  - Cogs de sanction : `record(...)` après l'appel Discord réussi.
  - `audit_journal.py` : `on_audit_log_entry_create(entry)` — `member_update` → `timeout_change(entry.before, entry.after)` ; sinon `map_audit_action` ; si `should_merge` → `attach_discord_entry`, et à défaut `record(source="discord")` ; sinon `record(source="discord", actor=entry.user, target=entry.target, details={"reason": entry.reason, "discord_audit_id": entry.id})`. Si le bot n'a pas `view_audit_log` au démarrage (`guild.me.guild_permissions.view_audit_log`), écrire **un** avertissement « permission Voir les logs du serveur manquante : sanctions natives non journalisées ».
  - Tâche `@tasks.loop(hours=24)` → `purge_older_than(365)`, log du nombre supprimé.
- [ ] **Step 4: Run tests** — `cd bot && python -m pytest -q` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(journal): commandes, sanctions Hermes et Discord journalisées, purge à 365 jours"`.

---

### Task 4: Journal des évènements du serveur

**Files:**
- Create: `bot/cogs/system/server_journal.py` (cog d'écoute : messages, vocal, membres) et `bot/utils/server_events.py` (fonctions pures de mise en forme)
- Modify: `bot/cogs/system/audit_journal.py` (Task 3) — couvrir **toutes** les entrées utiles du journal d'audit Discord (rôles, salons, surcharges de permissions, fils, émojis/stickers, invitations, réglages du serveur, rôles et pseudos des membres), pas seulement les sanctions
- Test: `bot/tests/test_server_events.py`

**Interfaces:**
- Consumes: `record` (Task 2).
- Produces (`bot/utils/server_events.py`) :
  - `MAX_CONTENT_LEN = 2000`
  - `def message_snapshot(content: str | None, attachments: list[str], embeds: int) -> dict` → `{"content": tronqué | "[contenu indisponible]", "attachments": [noms], "embeds": n}`
  - `def voice_actions(before, after) -> list[str]` — compare deux `VoiceState` (`channel`, `self_mute`, `self_deaf`, `mute`, `deaf`, `self_stream`) et renvoie les actions du Global Constraints ; un passage salon A → salon B donne `["move"]`, pas `leave` + `join`.
  - `def audit_to_events(action: discord.AuditLogAction, before: dict, after: dict) -> list[tuple[str, str, dict]]` — liste de `(kind, action, details)` selon les listes du Global Constraints : `role_create` → `[("role","create",…)]` ; `member_role_update` → une entrée par rôle ajouté (`("member_role","add",{"role": …})`) ou retiré ; `member_update` avec pseudo → `("member","nickname",…)` ; `overwrite_*` → `("channel","update",{"permissions": …})` ; `guild_update` → `("server","update",…)` ; liste vide pour ce qui n'est pas suivi.
  - `def diff_details(before: dict, after: dict) -> dict` → `{"changes": {champ: {"avant": …, "après": …}}}` pour les seuls champs modifiés, valeurs rendues lisibles (couleurs `#RRGGBB`, permissions par nom).

- [ ] **Step 1: Write the failing tests**

```python
from types import SimpleNamespace as V

def vs(**kw):
    base = dict(channel=None, self_mute=False, self_deaf=False, mute=False, deaf=False, self_stream=False)
    return V(**{**base, **kw})

def test_voice_move_is_single_action():
    from utils.server_events import voice_actions
    assert voice_actions(vs(channel=1), vs(channel=2)) == ["move"]

def test_voice_join_leave_and_mute():
    from utils.server_events import voice_actions
    assert voice_actions(vs(), vs(channel=1)) == ["join"]
    assert voice_actions(vs(channel=1), vs()) == ["leave"]
    assert voice_actions(vs(channel=1), vs(channel=1, self_mute=True)) == ["self_mute"]
    assert voice_actions(vs(channel=1), vs(channel=1, mute=True)) == ["server_mute"]

def test_message_snapshot_truncates_and_marks_unavailable():
    from utils.server_events import message_snapshot, MAX_CONTENT_LEN
    assert len(message_snapshot("x" * 5000, [], 0)["content"]) == MAX_CONTENT_LEN + 1
    assert message_snapshot(None, ["a.png"], 2) == {"content": "[contenu indisponible]", "attachments": ["a.png"], "embeds": 2}

def test_audit_member_role_update_splits_add_remove():
    import discord
    from utils.server_events import audit_to_events
    ev = audit_to_events(discord.AuditLogAction.member_role_update, {"roles": [V(id=1, name="A")]}, {"roles": [V(id=2, name="B")]})
    assert [(k, a) for k, a, _ in ev] == [("member_role", "add"), ("member_role", "remove")]

def test_diff_details_only_changed_fields():
    from utils.server_events import diff_details
    assert diff_details({"name": "a", "hoist": False}, {"name": "b", "hoist": False}) == {"changes": {"name": {"avant": "a", "après": "b"}}}
```

- [ ] **Step 2: Run to verify they fail** — `cd bot && python -m pytest -q tests/test_server_events.py`.
- [ ] **Step 3: Implement** `server_events.py` puis `server_journal.py` :
  - `on_raw_message_edit` : contenu avant depuis le cache s'il existe, après depuis la charge utile ; ignorer si le texte n'a pas changé (les mises à jour automatiques d'embeds ne sont pas des éditions) ; `on_raw_message_delete`, `on_raw_bulk_message_delete` → `kind="message"`, acteur = auteur du message, salon renseigné ; messages de bots ignorés ;
  - `on_voice_state_update` → une ligne par action de `voice_actions`, salon = salon d'arrivée (de départ pour `leave`), `details.from_channel` pour `move` ;
  - `on_member_join` / `on_member_remove` → `kind="member"` (`details.invite_code` via l'évènement existant `on_member_join_tracked` quand il est disponible) ;
  - `audit_journal.py` : toute entrée → `audit_to_events` ; les sanctions gardent la fusion de Task 3 ; `message_delete` par un modérateur → compléter la dernière ligne `message`/`delete` du même auteur et salon (moins de 10 s) avec `details.deleted_by`.
  - Ne pas modifier le comportement des cogs existants (`message_logs`, `voice`, `invite_tracker`, `welcome`) : on ajoute des écouteurs.
- [ ] **Step 4: Run tests** — `cd bot && python -m pytest -q` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(journal): messages, vocal, membres et changements du serveur journalisés"`.

---

### Task 5: Lecture du journal dans web-api (filtres + CSV)

**Files:**
- Create: `web-api/routes/audit.py` (router `prefix="/admin"`), enregistré dans `web-api/main.py`
- Modify: `web-api/routes/admin.py` — supprimer `GET /admin/logs`
- Test: `web-api/tests/test_audit_read.py`

**Interfaces:**
- Consumes: table `audit_events`.
- Produces:
  - `GET /admin/audit?kind=&action=&source=&success=&actor=&target=&channel_id=&from=&to=&q=&page=1` → `{"events": [AuditEvent], "total": int, "page": int, "pages": int}`, 50 par page, tri `occurred_at DESC, id DESC`. `AuditEvent` = `{id, occurred_at (ISO), kind, action, source, actor_id: str|null, actor_name, target_id: str|null, target_name, channel_id: str|null, channel_name, success, details}`. `kind`/`source`/`action` acceptent une liste séparée par des virgules ; `actor`/`target` = identifiant exact si numérique, sinon recherche `ILIKE` sur le nom ; `from`/`to` = dates `YYYY-MM-DD` interprétées en Europe/Paris, `to` inclusif ; `q` = `ILIKE` sur action, noms et `details::text`.
  - `GET /admin/audit.csv` (mêmes filtres) → `text/csv; charset=utf-8`, BOM UTF-8, séparateur `;`, en-tête `Date;Type;Action;Source;Auteur;Cible;Salon;Succès;Détails`, au plus **10 000** lignes, `Content-Disposition: attachment; filename="journal-hermes-<AAAAMMJJ>.csv"`.
  - `def build_audit_filters(params) -> tuple[str, list]` (clause WHERE + arguments, testable seule).
  - `def csv_cell(value: str) -> str` — préfixe `'` si la valeur commence par `=`, `+`, `-`, `@`, tabulation ou retour chariot.
  - `GET /admin/audit/facets` → `{"kinds": {kind: [actions présentes en base, triées]}, "channels": [{"id": str, "name": str}]}` (seulement ce qui a au moins une ligne ; cache 60 s) — rend les filtres **cohérents** : la liste des actions dépend du type choisi.

- [ ] **Step 1: Write the failing tests**

```python
def test_filters_combine_and_parametrize():
    from routes.audit import build_audit_filters
    where, args = build_audit_filters({"kind": "command,sanction", "actor": "Kéfir", "success": "false"})
    assert "kind = ANY(" in where and "actor_name ILIKE" in where and "success =" in where
    assert ["command", "sanction"] in args and "%Kéfir%" in args and False in args

def test_numeric_actor_is_exact_id():
    from routes.audit import build_audit_filters
    where, args = build_audit_filters({"actor": "279205522970902528"})
    assert "actor_id =" in where and 279205522970902528 in args

def test_date_range_paris_inclusive():
    from routes.audit import build_audit_filters
    where, args = build_audit_filters({"from": "2026-11-01", "to": "2026-11-23"})
    # bornes : 2026-11-01 00:00 Europe/Paris ≤ occurred_at < 2026-11-24 00:00 Europe/Paris
    ...

def test_invalid_date_is_422(client, admin_session):
    assert client.get("/admin/audit?from=2026-13-40").status_code == 422

def test_audit_requires_admin(client, member_session):
    assert client.get("/admin/audit").status_code == 403

def test_csv_neutralises_formulas():
    from routes.audit import csv_cell
    assert csv_cell("=HYPERLINK(\"x\")").startswith("'")
    assert csv_cell("Kéfir") == "Kéfir"

def test_csv_headers_and_disposition(client, admin_session, fake_db):
    r = client.get("/admin/audit.csv")
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    assert r.content.startswith("﻿Date;Type;Action".encode("utf-8"))
```

  (Fixtures `admin_session`/`member_session` : réutiliser ou créer sur le modèle des tests web-api existants qui simulent une session admin.)

- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement** `routes/audit.py` et l'enregistrement du router ; retirer `GET /admin/logs`.
- [ ] **Step 4: Run tests** — `cd web-api && python -m pytest -q` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(journal): lecture filtrée du journal et export CSV"`.

---

### Task 6: Journal dans `/admin/moderation`

**Files:**
- Create: `web/src/components/admin/audit-journal.tsx`, `web/src/lib/audit.ts` (libellés, formatage, construction de la query)
- Modify: `web/src/components/admin/moderation-panel.tsx` (remplacer `AdminLogs` par `AuditJournal`), `web/src/lib/api/client.ts` (`admin.audit(filters)`, URL CSV), `web/src/lib/api/types.ts` (`AuditEvent`, `AuditPage`, `AuditFilters` ; retirer `AdminLog*`)
- Delete: `web/src/components/admin/admin-logs.tsx` (et son test s'il existe)
- Test: `web/src/lib/__tests__/audit.test.ts`, `web/src/components/admin/__tests__/audit-journal.test.tsx`

**Interfaces:**
- Consumes: `GET /admin/audit`, `GET /admin/audit.csv`, `GET /admin/audit/facets` (Task 5) via le proxy `/api/proxy`.
- Produces: `AuditJournal` (composant client) ; `auditQuery(filters: AuditFilters, page: number): string` ; `KIND_LABELS: Record<string, string>` (`command`: « Commande », `sanction`: « Sanction », `role`: « Rôle », `channel`: « Salon », `member_role`: « Rôle de membre », `permission`: « Permission », `setting`: « Réglage », `game`: « Jeu », `site_access`: « Accès au site », `content`: « Contenu ») ; `SOURCE_LABELS` (`site`: « Site », `hermes`: « Hermes », `discord`: « Discord »).

Interface (texte et disposition) :
```
Journal                                             [Exporter CSV]
Raccourcis : [Tout] [Sanctions] [Messages] [Vocal] [Membres] [Rôles] [Salons] [Commandes] [Site]
[Type ▾] [Action ▾ (selon le type)] [Source ▾] [Salon ▾] [Auteur] [Cible] [Du] [Au] [☐ échecs seulement] [Rechercher…]
Date (Europe/Paris) | Type | Action | Auteur | Cible | Salon | Détail (dépliable)
… pagination « Page 2 / 14 » …
```
`KIND_LABELS` couvre tous les kinds du Global Constraints (dont `message`: « Message », `voice`: « Vocal », `member`: « Membre », `thread`: « Fil », `invite`: « Invitation », `emoji`: « Émoji », `server`: « Serveur ») et `ACTION_LABELS` toutes les actions (`edit`: « modifié », `delete`: « supprimé », `join`: « arrivée », `leave`: « départ », `move`: « déplacé », …). Le menu Action est rempli par `GET /admin/audit/facets` pour le type choisi ; changer de type réinitialise l'action. Le détail d'un message modifié affiche avant/après ; d'un changement de rôle ou de salon, les champs avant → après. Les filtres sont reflétés dans l'URL (`?type=…`) pour être partageables ; auteur et cible sont des liens vers la fiche membre (`MemberInspector` existant) ; une ligne en échec est marquée « échec » ; le détail affiche `details` en paires clé/valeur lisibles (raison, durée, options de commande).

- [ ] **Step 1: Write the failing tests**

```ts
it("auditQuery sérialise les filtres non vides et la page", () => {
  expect(auditQuery({ kind: ["command", "sanction"], actor: "Kéfir", failedOnly: true }, 2))
    .toBe("kind=command%2Csanction&actor=K%C3%A9fir&success=false&page=2")
})
it("auditQuery ignore les champs vides", () => {
  expect(auditQuery({ actor: "  " }, 1)).toBe("page=1")
})
it("affiche les lignes, l'échec et le lien CSV filtré", async () => {
  // mock api.admin.audit → 2 évènements dont un success=false
  // attendu : « Commande », « /fortnite », « échec », lien « Exporter CSV » vers /api/proxy/admin/audit.csv?kind=… 
})
it("changer un filtre recharge la page 1", async () => { /* … */ })
it("le menu Action ne propose que les actions du type choisi", async () => {
  // facets : { kinds: { voice: ["join", "leave"], message: ["edit"] } } ; choisir « Vocal » → options « arrivée », « départ » uniquement
})
it("le raccourci « Messages » pose type=message", async () => { /* … */ })
it("API en erreur : message, pas de tableau", async () => { /* … */ })
```

- [ ] **Step 2: Run to verify they fail** — `cd web && npx vitest run src/lib/__tests__/audit.test.ts src/components/admin/__tests__/audit-journal.test.tsx`.
- [ ] **Step 3: Implement** `lib/audit.ts`, `audit-journal.tsx`, branchement dans `moderation-panel.tsx`, types et client ; supprimer `admin-logs.tsx`.
- [ ] **Step 4: Run** — `cd web && npm test && npm run lint && npm run build` → tout vert.
- [ ] **Step 5: Commit** — `git commit -m "feat(journal): journal filtrable et export CSV dans la page Modération"`.

---

## Déploiement (contrôleur, après relecture finale)

1. Ajouter au rôle du bot la permission Discord « Voir les logs du serveur » (propriétaire, ou contrôleur avec son accord).
2. `git push`, puis sur le serveur : `git pull`, appliquer `db/migrations/020_audit_events.sql`, `docker compose up -d --build bot web-api web`.
3. Vérifier : une commande `/blague` apparaît dans le journal ; un message modifié puis supprimé, une connexion vocale, un rôle ajouté à un membre dans Discord apparaissent avec le bon auteur ; une sanction depuis le site apparaît **une fois** (source Site) ; un timeout posé directement dans Discord apparaît (source Discord) ; filtres et CSV.
