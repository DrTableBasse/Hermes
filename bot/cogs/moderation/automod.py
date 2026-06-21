"""Auto-modération : anti-spam, mentions massives, mots bloqués, liens, doublons."""
import re
import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import discord
from discord import app_commands
from discord.ext import commands
from utils.database import db_manager, warn_manager
from utils.decorators import administration_only, ADMIN_ROLE_NAME
from utils.command_manager import command_enabled
from utils.embed_style import hermes_embed, Colors

logger = logging.getLogger(__name__)

INVITE_RE = re.compile(r"discord(?:\.gg|(?:app)?\.com/invite)/\S+", re.IGNORECASE)

# Durées des sanctions
TIMEOUT_DURATIONS = [None, None, timedelta(minutes=5), timedelta(hours=1)]

# Seuil de reset du compteur de violations (secondes)
VIOLATION_RESET_SECONDS = 3600  # 1h sans incident → reset


class AutoModCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # {user_id: [timestamp, ...]}  — horodatages des messages dans la fenêtre
        self._spam_tracker: dict[int, list[float]] = defaultdict(list)

        # {user_id: {'count': int, 'last': float}}  — violations progressives
        self._violations: dict[int, dict] = defaultdict(lambda: {'count': 0, 'last': 0.0})

        # {user_id: {content_hash: last_timestamp}}  — détection doublons
        self._msg_cache: dict[int, dict[str, float]] = defaultdict(dict)

        # Cache config {guild_id: {'data': dict, 'expires': float}}
        self._cfg_cache: dict[int, dict] = {}

    # ── Config ────────────────────────────────────────────────────────────────

    async def _get_config(self, guild_id: int) -> dict:
        now = datetime.now(timezone.utc).timestamp()
        cached = self._cfg_cache.get(guild_id)
        if cached and cached['expires'] > now:
            return cached['data']

        row = await db_manager.fetchrow("SELECT * FROM automod_config WHERE guild_id = $1", guild_id)
        data = dict(row) if row else {
            'enabled':                  True,
            'blocked_words':            [],
            'max_mentions':             10,
            'spam_threshold':           3,
            'spam_window_seconds':      5,
            'invite_links_enabled':     True,
            'duplicate_window_seconds': 30,
            'log_channel_id':           None,
        }
        self._cfg_cache[guild_id] = {'data': data, 'expires': now + 60}
        return data

    def _invalidate_cache(self, guild_id: int):
        self._cfg_cache.pop(guild_id, None)

    # ── Sanctions progressives ────────────────────────────────────────────────

    async def _get_violation_count(self, user_id: int) -> int:
        v = self._violations[user_id]
        now = datetime.now(timezone.utc).timestamp()
        if now - v['last'] > VIOLATION_RESET_SECONDS:
            v['count'] = 0
        return v['count']

    async def _sanction(
        self,
        message: discord.Message,
        reason: str,
        extra_messages: list[discord.Message] | None = None,
    ):
        member = message.author
        guild_id = message.guild.id
        user_id = member.id
        now = datetime.now(timezone.utc).timestamp()

        # Incrémenter violations
        v = self._violations[user_id]
        if now - v['last'] > VIOLATION_RESET_SECONDS:
            v['count'] = 0
        v['count'] += 1
        v['last'] = now
        level = v['count']

        # Supprimer le message déclencheur + éventuels messages du burst
        to_delete = [message] + (extra_messages or [])
        try:
            if len(to_delete) > 1:
                await message.channel.delete_messages(
                    [m for m in to_delete if m is not None],
                    reason=f"AutoMod — {reason}",
                )
            else:
                await message.delete()
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass

        # Construire la réponse selon le niveau
        if level == 1:
            desc = f"⚠️ {member.mention} — {reason}\n*Prochain incident : avertissement formel + timeout.*"
            color = Colors.ORANGE
            timeout_duration = None
            formal_warn = False
        elif level == 2:
            desc = f"🔇 {member.mention} — {reason}\n*Avertissement enregistré + timeout 5 minutes.*"
            color = Colors.RED
            timeout_duration = TIMEOUT_DURATIONS[2]
            formal_warn = True
        else:
            desc = f"🔨 {member.mention} — {reason}\n*Avertissement enregistré + timeout 1 heure.*"
            color = Colors.RED
            timeout_duration = TIMEOUT_DURATIONS[3]
            formal_warn = True

        # Message dans le salon
        try:
            await message.channel.send(
                embed=hermes_embed(description=desc, color=color),
                delete_after=8,
            )
        except discord.Forbidden:
            pass

        # Warn formel en DB (visible sur le site + /warns)
        if formal_warn:
            await warn_manager.add_warn(
                user_id,
                f"[AutoMod] {reason}",
                self.bot.user.id,
            )

        # Timeout Discord
        if timeout_duration:
            try:
                await member.timeout(timeout_duration, reason=f"[AutoMod] {reason}")
            except (discord.Forbidden, discord.HTTPException):
                pass
            # DM à l'utilisateur
            try:
                dm = hermes_embed(
                    title="🔇 Timeout AutoMod",
                    description=(
                        f"Tu as reçu un timeout de **{'5 minutes' if level == 2 else '1 heure'}** "
                        f"sur **{message.guild.name}**.\n\n"
                        f"**Raison :** {reason}"
                    ),
                    color=Colors.RED,
                )
                await member.send(embed=dm)
            except discord.Forbidden:
                pass

        # Log DB
        await self._log_action(guild_id, user_id, 'spam' if level == 1 else 'timeout', reason, message.channel.id)

    async def _log_action(self, guild_id: int, user_id: int, action: str, reason: str, channel_id: int = None):
        try:
            await db_manager.execute("""
                INSERT INTO automod_logs (guild_id, user_id, action, reason, channel_id)
                VALUES ($1, $2, $3, $4, $5)
            """, guild_id, user_id, action, reason, channel_id)
        except Exception as e:
            logger.error(f"automod log error: {e}")

    # ── Listener principal ────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Bypass pour les admins Discord et le rôle Administration
        if message.author.guild_permissions.administrator:
            return
        admin_role = discord.utils.get(message.guild.roles, name=ADMIN_ROLE_NAME)
        if admin_role and admin_role in message.author.roles:
            return

        cfg = await self._get_config(message.guild.id)
        if not cfg['enabled']:
            return

        user_id = message.author.id
        now = datetime.now(timezone.utc).timestamp()

        # 1. Anti-spam (fréquence)
        window = cfg['spam_window_seconds']
        self._spam_tracker[user_id] = [t for t in self._spam_tracker[user_id] if now - t < window]
        self._spam_tracker[user_id].append(now)

        if len(self._spam_tracker[user_id]) >= cfg['spam_threshold']:
            # Récupérer les messages récents du burst pour tout supprimer
            burst = []
            try:
                burst = [
                    m async for m in message.channel.history(limit=20)
                    if m.author.id == user_id and now - m.created_at.timestamp() < window
                    and m.id != message.id
                ]
            except discord.Forbidden:
                pass
            self._spam_tracker[user_id] = []
            await self._sanction(message, "Spam détecté (messages trop fréquents)", burst)
            return

        # 2. Liens Discord (discord.gg / discord.com/invite)
        if cfg.get('invite_links_enabled', True) and INVITE_RE.search(message.content):
            await self._sanction(message, "Lien d'invitation Discord non autorisé")
            return

        # 3. Doublons (même message posté plusieurs fois rapidement)
        dup_window = cfg.get('duplicate_window_seconds', 30)
        content_key = message.content.strip().lower()
        if len(content_key) > 5:
            cache = self._msg_cache[user_id]
            # Nettoyer les entrées expirées
            self._msg_cache[user_id] = {k: v for k, v in cache.items() if now - v < dup_window}
            if content_key in self._msg_cache[user_id]:
                # Chercher le message précédent identique pour le supprimer aussi
                prev = []
                try:
                    prev = [
                        m async for m in message.channel.history(limit=20)
                        if m.author.id == user_id
                        and m.content.strip().lower() == content_key
                        and m.id != message.id
                    ]
                except discord.Forbidden:
                    pass
                del self._msg_cache[user_id][content_key]
                await self._sanction(message, "Message dupliqué (copier-coller répété)", prev)
                return
            self._msg_cache[user_id][content_key] = now

        # 4. Anti mentions massives
        if len(message.mentions) >= cfg['max_mentions']:
            await self._sanction(
                message,
                f"Mentions massives ({len(message.mentions)} mentions dans un message)",
            )
            return

        # 5. Mots bloqués
        blocked = cfg.get('blocked_words') or []
        content_lower = message.content.lower()
        for word in blocked:
            if word and word.lower() in content_lower:
                await self._sanction(message, f"Mot non autorisé")
                return

    # ── Commandes ─────────────────────────────────────────────────────────────

    @app_commands.command(name="automod-config", description="Configurer l'auto-modération")
    @administration_only()
    @command_enabled(guild_specific=True)
    async def automod_config(
        self,
        interaction: discord.Interaction,
        enabled: bool = None,
        max_mentions: int = None,
        spam_threshold: int = None,
        spam_window: int = None,
        invite_links: bool = None,
        duplicate_window: int = None,
    ):
        guild_id = interaction.guild_id
        await db_manager.execute("""
            INSERT INTO automod_config (
                guild_id, max_mentions, spam_threshold, spam_window_seconds,
                enabled, invite_links_enabled, duplicate_window_seconds
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (guild_id) DO UPDATE SET
                max_mentions             = COALESCE($2, automod_config.max_mentions),
                spam_threshold           = COALESCE($3, automod_config.spam_threshold),
                spam_window_seconds      = COALESCE($4, automod_config.spam_window_seconds),
                enabled                  = COALESCE($5, automod_config.enabled),
                invite_links_enabled     = COALESCE($6, automod_config.invite_links_enabled),
                duplicate_window_seconds = COALESCE($7, automod_config.duplicate_window_seconds),
                updated_at               = NOW()
        """, guild_id, max_mentions, spam_threshold, spam_window, enabled, invite_links, duplicate_window)

        self._invalidate_cache(guild_id)
        cfg = await self._get_config(guild_id)

        embed = hermes_embed(title="🛡️  Configuration Auto-Mod", color=Colors.GREEN)
        embed.add_field(name="Statut",         value="✅ Activé" if cfg['enabled'] else "❌ Désactivé", inline=True)
        embed.add_field(name="Max mentions",   value=f"**{cfg['max_mentions']}**", inline=True)
        embed.add_field(name="Anti-spam",      value=f"**{cfg['spam_threshold']}** msgs/**{cfg['spam_window_seconds']}**s", inline=True)
        embed.add_field(name="Liens Discord",  value="🚫 Bloqués" if cfg.get('invite_links_enabled') else "✅ Autorisés", inline=True)
        embed.add_field(name="Doublons",       value=f"Fenêtre **{cfg.get('duplicate_window_seconds', 30)}**s", inline=True)
        embed.add_field(
            name="Sanctions",
            value="1 infraction → avertissement\n2 infractions → warn DB + timeout 5min\n3+ infractions → warn DB + timeout 1h",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="automod-reset", description="Réinitialiser les violations d'un utilisateur")
    @administration_only()
    @command_enabled(guild_specific=True)
    async def automod_reset(self, interaction: discord.Interaction, member: discord.Member):
        self._violations.pop(member.id, None)
        self._spam_tracker.pop(member.id, None)
        self._msg_cache.pop(member.id, None)
        await interaction.response.send_message(
            embed=hermes_embed(
                description=f"✅ Compteur de violations de {member.mention} réinitialisé.",
                color=Colors.GREEN,
            ),
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(AutoModCog(bot))
