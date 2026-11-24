"""Règles de rôles automatiques appliquées par le bot (évènements, aperçu, réconciliation).

Le calcul est dans ``utils.role_rules`` (pur) ; ce cog lit les règles et les
statistiques en base, puis ajoute ou retire les rôles Discord et journalise.
"""
from __future__ import annotations

import logging
import os
import time

import discord
from discord.ext import commands, tasks

from utils.audit_events import record
from utils.database import db_manager
from utils.grades import load_grades
from utils.role_rules import MemberStats, Rule, matches, plan_changes

logger = logging.getLogger(__name__)

GUILD_ID = int(os.getenv('GUILD_ID', '0'))
BATCH_SIZE = 500  # membres par requête de statistiques, jamais plus
CREATE_RETRY_SECONDS = 3600  # délai avant de retenter une création de rôle refusée (T2 n°2)

_RULE_COLUMNS = (
    "id, condition_type, condition_value, role_id, remove_when_lost, exclusive_group, "
    "active, reconcile, create_role_name, create_role_color"
)

# Une requête par lot de membres : vocal, messages, XP, série, bumps, invitations, succès.
STATS_SQL = """
    SELECT u.id AS user_id,
           COALESCE(v.total_time, 0)      AS voice_seconds,
           COALESCE(m.total, 0)           AS messages,
           COALESCE(x.current_level, 0)   AS level,
           COALESCE(s.current_streak, 0)  AS streak_days,
           COALESCE(b.bump_count, 0)      AS bumps,
           COALESCE(i.invite_count, 0)    AS invites,
           COALESCE(a.ids, '{}')          AS achievements
    FROM unnest($1::bigint[]) AS u(id)
    LEFT JOIN user_voice_data v   ON v.user_id = u.id
    LEFT JOIN user_xp x           ON x.user_id = u.id
    LEFT JOIN user_streaks s      ON s.user_id = u.id
    LEFT JOIN user_bump_stats b   ON b.user_id = u.id
    LEFT JOIN user_invite_stats i ON i.user_id = u.id
    LEFT JOIN (SELECT user_id, SUM(message_count) AS total
               FROM user_message_stats WHERE user_id = ANY($1::bigint[])
               GROUP BY user_id) m ON m.user_id = u.id
    LEFT JOIN (SELECT user_id, array_agg(achievement_id) AS ids
               FROM user_achievements WHERE user_id = ANY($1::bigint[])
               GROUP BY user_id) a ON a.user_id = u.id
"""


def _rule_from_row(row) -> Rule:
    return Rule(
        id=row["id"],
        condition_type=row["condition_type"],
        condition_value=row["condition_value"],
        role_id=row["role_id"],
        remove_when_lost=bool(row["remove_when_lost"]),
        exclusive_group=row["exclusive_group"],
        active=bool(row["active"]),
        reconcile=bool(row["reconcile"]),
        create_role_name=row["create_role_name"],
        create_role_color=row["create_role_color"],
    )


def _stats_from_row(row) -> MemberStats:
    return MemberStats(
        voice_hours=(row["voice_seconds"] or 0) / 3600,
        messages=int(row["messages"] or 0),
        level=int(row["level"] or 0),
        streak_days=int(row["streak_days"] or 0),
        bumps=int(row["bumps"] or 0),
        invites=int(row["invites"] or 0),
        achievements=frozenset(int(a) for a in (row["achievements"] or [])),
    )


class RoleEngine(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._rules: list[Rule] | None = None
        self._warned: set[tuple[int, int, str]] = set()
        self._create_failed: dict[int, float] = {}  # règle → heure (monotonic) du dernier échec
        self.reconcile_loop.start()

    def cog_unload(self):
        self.reconcile_loop.cancel()

    # ── Chargement ───────────────────────────────────────────────────────────

    async def reload(self) -> None:
        """Relit les règles en base (après une modification depuis le site)."""
        rows = await db_manager.fetch(f"SELECT {_RULE_COLUMNS} FROM role_rules ORDER BY id")
        self._rules = [_rule_from_row(r) for r in rows]
        logger.info("%d règles de rôles chargées", len(self._rules))

    async def _get_rules(self) -> list[Rule]:
        if self._rules is None:
            await self.reload()
        return self._rules

    async def _grades(self) -> dict[str, int]:
        return {g["slug"]: g["level_min"] for g in await load_grades(db_manager)}

    async def _stats(self, user_ids: list[int]) -> dict[int, MemberStats]:
        """Statistiques des membres, une requête par lot de BATCH_SIZE au plus."""
        stats: dict[int, MemberStats] = {}
        for start in range(0, len(user_ids), BATCH_SIZE):
            batch = user_ids[start:start + BATCH_SIZE]
            for row in await db_manager.fetch(STATS_SQL, batch):
                stats[row["user_id"]] = _stats_from_row(row)
        return stats

    # ── Rôles ────────────────────────────────────────────────────────────────

    def _warn_once(self, rule: Rule, reason: str, message: str, *args) -> None:
        key = (rule.id, rule.role_id or 0, reason)
        if key in self._warned:
            return
        self._warned.add(key)
        logger.warning(message, *args)

    def _usable_role(self, guild: discord.Guild, rule: Rule) -> discord.Role | None:
        """Rôle cible s'il existe et que le bot peut le gérer ; sinon None (un avertissement)."""
        role = guild.get_role(rule.role_id)
        if role is None:
            self._warn_once(rule, "missing", "Règle de rôle %s : le rôle %s est introuvable",
                            rule.id, rule.role_id)
            return None
        if not role.is_assignable():
            self._warn_once(rule, "unmanageable", "Règle de rôle %s : le rôle %s n'est pas gérable par le bot",
                            rule.id, role.name)
            return None
        return role

    def _is_missing(self, guild: discord.Guild, rule: Rule) -> bool:
        if rule.role_id is None:
            return False  # « créer au premier déblocage » : rien n'est encore attendu
        return self._usable_role(guild, rule) is None

    async def _ensure_rule_role(self, guild: discord.Guild, rule: Rule) -> None:
        """« Créer au premier déblocage » : rôle homonyme existant réutilisé, sinon créé ;
        son identifiant est enregistré dans la règle."""
        name = rule.create_role_name
        role = discord.utils.get(guild.roles, name=name)
        if role is None:
            failed_at = self._create_failed.get(rule.id)
            if failed_at is not None and time.monotonic() - failed_at < CREATE_RETRY_SECONDS:
                return  # échec récent (ex. 250 rôles atteints) : pas d'appel Discord à chaque évènement
        if role is not None and (role.managed or not role.is_assignable()):
            # Défense en profondeur (C1) : un homonyme hors de portée n'est jamais donné.
            self._warn_once(rule, "homonym", "Règle de rôle %s : le rôle '%s' existe mais n'est pas "
                            "gérable par le bot ; règle ignorée", rule.id, name)
            return
        if role is None:
            try:
                role = await guild.create_role(
                    name=name,
                    color=discord.Color(rule.create_role_color or 0),
                    reason="Rôle de succès créé automatiquement par Hermes",
                )
            except discord.HTTPException as e:
                self._create_failed[rule.id] = time.monotonic()
                self._warn_once(rule, "create", "Règle de rôle %s : création du rôle '%s' impossible (%s)",
                                rule.id, name, e)
                return
            self._create_failed.pop(rule.id, None)
            logger.info("Rôle de succès créé : '%s'", name)
            await record(
                kind="role", action="create", source="hermes",
                actor_id=self._bot_id(), actor_name=self._bot_name(),
                target_id=role.id, target_name=role.name, details={"rule_id": rule.id},
            )
        # Une règle résolue ne garde que role_id : « l'un ou l'autre » (I1, web-api le vérifie).
        await db_manager.execute(
            "UPDATE role_rules SET role_id = $1, create_role_name = NULL, create_role_color = NULL, "
            "updated_at = NOW() WHERE id = $2 AND role_id IS NULL",
            role.id, rule.id,
        )
        rule.role_id = role.id
        rule.create_role_name = rule.create_role_color = None

    def _bot_id(self) -> int | None:
        return getattr(getattr(self.bot, "user", None), "id", None)

    def _bot_name(self) -> str | None:
        return getattr(getattr(self.bot, "user", None), "name", None)

    def _rule_for_role(self, rules: list[Rule], role_id: int) -> Rule | None:
        return next((r for r in rules if r.active and r.role_id == role_id), None)

    async def _change(self, member: discord.Member, role: discord.Role, rule: Rule | None, add: bool) -> bool:
        reason = f"Règle de rôle automatique #{rule.id}" if rule else "Règle de rôle automatique"
        try:
            if add:
                await member.add_roles(role, reason=reason)
            else:
                await member.remove_roles(role, reason=reason)
        except discord.HTTPException as e:
            logger.warning("Rôle '%s' %s pour %s impossible : %s",
                           role.name, "ajouté" if add else "retiré", member.id, e)
            return False
        await record(
            kind="member_role", action="add" if add else "remove", source="hermes",
            actor_id=self._bot_id(), actor_name=self._bot_name(),
            target_id=member.id, target_name=member.display_name,
            details={"rule_id": rule.id if rule else None, "role_id": role.id, "role_name": role.name},
        )
        return True

    async def _apply_plan(self, member: discord.Member, rules: list[Rule],
                          to_add: set[int], to_remove: set[int]) -> tuple[list[int], list[int]]:
        added: list[int] = []
        removed: list[int] = []
        for role_ids, add, done in ((to_add, True, added), (to_remove, False, removed)):
            for role_id in sorted(role_ids):
                rule = self._rule_for_role(rules, role_id)
                role = self._usable_role(member.guild, rule) if rule else member.guild.get_role(role_id)
                if role is not None and await self._change(member, role, rule, add):
                    done.append(role_id)
        return added, removed

    # ── API ──────────────────────────────────────────────────────────────────

    async def evaluate_member(self, member: discord.Member) -> tuple[list[int], list[int]]:
        """Applique toutes les règles actives à un membre ; renvoie (rôles ajoutés, retirés)."""
        if member.bot:
            return [], []
        rules = await self._get_rules()
        grades = await self._grades()
        stats = (await self._stats([member.id])).get(member.id, MemberStats())
        for rule in rules:
            if (rule.active and rule.role_id is None and rule.create_role_name
                    and matches(rule, stats, grades)):
                await self._ensure_rule_role(member.guild, rule)
        usable = [r for r in rules if r.role_id is None or not self._is_missing(member.guild, r)]
        to_add, to_remove = plan_changes(usable, stats, {r.id for r in member.roles}, grades)
        return await self._apply_plan(member, rules, to_add, to_remove)

    def _guild(self) -> discord.Guild | None:
        return self.bot.get_guild(GUILD_ID)

    async def _rule_changes(self, guild: discord.Guild, rule: Rule) -> tuple[list, list]:
        """Membres qui gagneraient / perdraient le rôle de la règle (rien n'est modifié)."""
        rules = [r for r in await self._get_rules() if r.id != rule.id]
        probe = Rule(**{**rule.__dict__, "active": True})
        if probe.role_id is None and probe.create_role_name:
            # Rôle homonyme déjà présent : c'est lui que la règle utilisera (lecture seule, T2 n°1).
            homonym = discord.utils.get(guild.roles, name=probe.create_role_name)
            if homonym is not None and not homonym.managed and homonym.is_assignable():
                probe.role_id = homonym.id
        rules.append(probe)
        grades = await self._grades()
        members = [m for m in guild.members if not m.bot]
        stats = await self._stats([m.id for m in members])
        gain, lose = [], []
        for m in members:
            s = stats.get(m.id, MemberStats())
            held = {r.id for r in m.roles}
            if probe.role_id is None:
                # Rôle pas encore créé : gagnent ceux qui remplissent la condition.
                if matches(probe, s, grades):
                    gain.append(m)
                continue
            to_add, to_remove = plan_changes(rules, s, held, grades)
            if probe.role_id in to_add:
                gain.append(m)
            elif probe.role_id in to_remove:
                lose.append(m)
        return gain, lose

    async def _find_rule(self, rule_id: int) -> Rule:
        rule = next((r for r in await self._get_rules() if r.id == rule_id), None)
        if rule is None:
            await self.reload()
            rule = next((r for r in self._rules if r.id == rule_id), None)
        if rule is None:
            raise KeyError(f"règle {rule_id} introuvable")
        return rule

    async def preview(self, rule_id: int) -> dict:
        """Aperçu d'une règle sur tous les membres : {"gain", "lose", "missing_role"}."""
        rule = await self._find_rule(rule_id)
        guild = self._guild()
        if guild is None:
            return {"gain": [], "lose": [], "missing_role": False}
        missing = self._is_missing(guild, rule)
        gain, lose = await self._rule_changes(guild, rule)
        return {"gain": [m.id for m in gain], "lose": [m.id for m in lose], "missing_role": missing}

    async def apply(self, rule_id: int) -> dict:
        """Réconcilie une règle sur tous les membres ; même forme que preview + comptes."""
        rule = await self._find_rule(rule_id)
        guild = self._guild()
        result = {"gain": [], "lose": [], "missing_role": False, "added": 0, "removed": 0,
                  "skipped": 0}
        if guild is None:
            return result
        gain, lose = await self._rule_changes(guild, rule)
        result["gain"] = [m.id for m in gain]
        result["lose"] = [m.id for m in lose]
        if gain and rule.role_id is None and rule.create_role_name:
            await self._ensure_rule_role(guild, rule)
        if rule.role_id is None or self._is_missing(guild, rule):
            result["missing_role"] = rule.role_id is not None
            return result
        role = guild.get_role(rule.role_id)
        for m in gain:  # séquentiel : discord.py gère les limites
            if role in m.roles:  # rôle homonyme réutilisé, déjà porté
                result["skipped"] += 1
                continue
            if await self._change(m, role, rule, True):
                result["added"] += 1
        for m in lose:
            if await self._change(m, role, rule, False):
                result["removed"] += 1
        return result

    # ── Réconciliation périodique (règles validées seulement) ────────────────

    @tasks.loop(hours=6)
    async def reconcile_loop(self):
        try:
            await self.reload()
            for rule in [r for r in self._rules if r.active and r.reconcile]:
                result = await self.apply(rule.id)
                if result["added"] or result["removed"]:
                    logger.info("Règle de rôle %s réconciliée : +%d / -%d",
                                rule.id, result["added"], result["removed"])
        except Exception as e:
            logger.error("Réconciliation des règles de rôles : %s", e, exc_info=True)

    @reconcile_loop.before_loop
    async def _before_reconcile(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleEngine(bot))
