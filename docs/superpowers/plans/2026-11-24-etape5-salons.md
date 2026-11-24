# Étape 5 — Salons et modèles d'accès : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Une page `/admin/salons` pour voir l'arborescence du serveur, créer, renommer, déplacer et supprimer des salons, et appliquer en un geste un modèle d'accès (Public, Rôle requis, Annonces, Staff) à un salon ou à toute une catégorie, avec aperçu des permissions écrites et retirées.

**Architecture:** Fonctions pures de modèles dans le bot (`bot/utils/channel_templates.py`) ; table `channel_templates` qui mémorise le modèle appliqué (pour la resynchronisation quand `staff_roles` change) ; API interne du bot pour lire/écrire salons et surcharges ; web-api applique droits, anti-escalade et confirmations ; page du site.

**Tech Stack:** PostgreSQL 15, discord.py, FastAPI, Next.js 16 / vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-11-23-pilotage-discord-design.md` §4.1, §4.6.

## Global Constraints

- Droit du site : `channels.manage`. Modèle « Staff » et resynchronisation après changement de `staff_roles` : réservés aux admins (`is_admin`).
- Modèles (surcharges écrites ; `@everyone` = rôle par défaut ; « bot » = membre du bot, toujours voir/écrire/gérer) :
  - **Public** : aucune surcharge `@everyone` (retire les refus de vue/écriture existants) ;
  - **Rôle requis** (rôles R) : `@everyone` voir = non ; R : voir, écrire, se connecter (vocal) = oui ;
  - **Annonces** (rôles R) : `@everyone` voir = oui, écrire/créer des fils = non ; R : écrire = oui ;
  - **Staff** : `@everyone` voir = non ; rôles `staff_roles` : voir, écrire, gérer les messages = oui.
  Les surcharges de membres individuels et des rôles non concernés sont conservées ; l'aperçu liste chaque surcharge ajoutée, modifiée ou retirée (avant → après).
- Anti-escalade (§4.1), sauf propriétaire : l'acteur doit **voir** le salon dans Discord (permissions effectives calculées par le bot) ; tout rôle R cité doit être strictement sous son rôle le plus haut ; on ne peut pas retirer à un rôle au-dessus de soi une surcharge existante.
- Confirmations : suppression d'un salon = retaper son nom ; application d'un modèle = confirmation de l'aperçu (jeton d'aperçu renvoyé et vérifié à l'application, 409 si l'état a changé) ; application à une catégorie avec « synchroniser les salons » = nombre de salons affiché.
- Types de salons : texte, vocal, forum, annonces, catégorie. Noms : 1–100 caractères (Discord) ; pour le texte, minuscules et tirets (normalisés par Discord, affichés tels quels après création).
- Toute action journalisée (`audit_events`, kinds `channel` et `permission`, source `site`). Erreurs Discord traduites. Ne jamais afficher `.env` ni `docker compose config`. Commits en français terminés par la ligne Co-Authored-By de la consigne. Migration : `db/migrations/024_channel_templates.sql`.

## Review Focus

1. Appliquer « Public » à un salon caché du staff par un membre qui ne le voit pas → 403 (Task 3).
2. Rôle R au-dessus de l'acteur dans « Rôle requis » ou « Annonces » → 403 (Task 3).
3. L'état d'un salon change entre l'aperçu et l'application → 409 « l'aperçu n'est plus à jour » (Task 2/3).
4. Supprimer une catégorie qui contient des salons → refus 409 « videz d'abord la catégorie » (Task 2).
5. `staff_roles` changé → la page propose la resynchronisation des salons « Staff » avec aperçu (Task 3/4).

---

### Task 1: Modèles purs et table

**Files:** Create `bot/utils/channel_templates.py`, `db/migrations/024_channel_templates.sql` (+ `db/init.sql`) ; Test `bot/tests/test_channel_templates.py`.

**Interfaces:**
- Produces : `TEMPLATES = ("public", "role_required", "announcements", "staff")` ; `@dataclass Overwrite(target_id: int, target_type: Literal["role","member"], allow: int, deny: int)` ; `def template_overwrites(template: str, everyone_id: int, bot_id: int, roles: list[int], staff_roles: list[int], channel_type: str) -> dict[int, Overwrite]` ; `def plan(current: dict[int, Overwrite], wanted: dict[int, Overwrite], managed_ids: set[int]) -> list[dict]` (changements `{"target_id","target_type","action": "add"|"update"|"remove","before","after"}`, ne retire que les surcharges de `managed_ids` = `@everyone`, bot, rôles du modèle précédent et du nouveau ; conserve les autres) ; `def preview_token(channel_id: int, current: dict) -> str` (empreinte stable des surcharges actuelles).
- Produces : table `channel_templates(channel_id BIGINT PRIMARY KEY, template VARCHAR(20) NOT NULL, roles BIGINT[] NOT NULL DEFAULT '{}', applied_by BIGINT, applied_at TIMESTAMPTZ DEFAULT NOW())`.

- [ ] Tests : chaque modèle (bits attendus pour texte et vocal) ; `plan` conserve une surcharge de membre et d'un rôle tiers ; passage Rôle requis → Public retire le refus `@everyone` et la surcharge des rôles R ; jeton stable et sensible à un changement. Implémentation, `cd bot && python -m pytest -q`, commit `feat(salons): modèles d'accès et mémorisation des modèles appliqués`.

### Task 2: API interne du bot

**Files:** Modify `bot/api.py` (+ éventuel `bot/utils/channels_api.py`) ; Test `bot/tests/test_api_channels.py`.

**Interfaces:** `GET /discord/channels/tree?actor_id=` → catégories et salons (id, nom, type, position, parent, nombre de surcharges, modèle mémorisé, `visible_to_actor`) ; `POST /discord/channels` {name, type, parent_id?, actor_name} ; `PATCH /discord/channels/{id}` {name?, parent_id?, position?} ; `DELETE /discord/channels/{id}` (409 si catégorie non vide) ; `POST /discord/channels/{id}/template/preview` {template, roles, sync_children?, actor_id} → {changes par salon, token} ; `POST /discord/channels/{id}/template/apply` {template, roles, sync_children?, token, actor_id, actor_name} (409 si jeton périmé ; écrit `channel_templates`) ; `POST /discord/channels/staff-resync/preview` et `/apply` (salons au modèle « staff »). Refus 403 si l'acteur ne voit pas le salon (propriétaire exempté). Raison d'audit Discord « via le site par <actor_name> ».

- [ ] Tests (guild simulé), implémentation, `cd bot && python -m pytest -q` + `python -c "import main"`, commit `feat(salons): API interne du bot pour les salons et les modèles`.

### Task 3: web-api

**Files:** Create `web-api/routes/channels.py` (router `/admin`) ; Test `web-api/tests/test_channels.py`.

**Interfaces:** `GET /admin/channels` ; `POST/PATCH/DELETE /admin/channels[/{id}]` (suppression : `confirm_name`) ; `POST /admin/channels/{id}/template/preview|apply` ; `POST /admin/channels/staff-resync/preview|apply` (admin) — droits, anti-escalade (rôles R sous l'acteur via le rang étape 2 ; modèle « staff » réservé admin), relais des 403/409 du bot, journal `channel` / `permission`. Délai : le proxy Next à 70 s est déjà prévu pour `admin/games` ; ajoute les chemins `admin/channels/*/template/apply` et `staff-resync/apply` au même plafond (`web/src/lib/api/forward.ts`) si l'application sur une catégorie peut durer.

- [ ] Tests (droits, 403 escalade, 409 relayés, confirm_name), implémentation, suites vertes, commit `feat(salons): gestion des salons et des modèles dans web-api`.

### Task 4: Page Salons

**Files:** Create `web/src/app/[locale]/admin/salons/page.tsx`, composants `channels-admin.tsx`, `channel-template-panel.tsx` ; Modify `admin-sections.ts` (section « Salons », `channels.manage`) ; Test `web/src/app/[locale]/admin/__tests__/salons.test.tsx`.

```
Salons                                              [+ Nouveau salon]
▾ 🎮 JEUX                         Modèle : —          [Accès…] [Renommer] [Supprimer]
   # général-jeux                 Rôle requis (Fortnite)   [Accès…] [Renommer] [Déplacer] [Supprimer]
   🔊 Vocal jeux                  Public
Accès à « # tournoi » :  ○ Public  ● Rôle requis [Fortnite ▾]  ○ Annonces [..]  ○ Staff (admin)
  ☐ appliquer aussi aux salons de la catégorie (12)
  Aperçu : + Fortnite : voir, écrire   ~ @everyone : voir oui → non   − Ancien rôle : surcharge retirée
  [Appliquer]
```
Salons invisibles pour l'acteur : non affichés (ou grisés « vous ne voyez pas ce salon »). Bandeau si `staff_roles` a changé depuis la dernière application d'un modèle Staff : « Mettre à jour les salons Staff » (admin) avec aperçu.

- [ ] Tests (droits, création, suppression avec nom retapé, aperçu puis application, 409 jeton périmé affiché, catégorie avec synchronisation), implémentation, `cd web && npm test && npm run lint && npm run build`, commit `feat(salons): page Salons avec modèles d'accès`.

## Déploiement (contrôleur, après relecture finale)

Sauvegarde, push, pull, migration 024, `docker compose up -d --build web-api bot web` ; vérifier : arborescence affichée, création d'un salon test, modèle « Rôle requis » appliqué avec aperçu, suppression du salon test ; aucune surcharge existante modifiée au déploiement.
