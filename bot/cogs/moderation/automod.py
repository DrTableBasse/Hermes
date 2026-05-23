"""Auto-modération : anti-spam, mentions massives, mots bloqués."""
import logging
from collections import defaultdict
from datetime import datetime, timezone
import discord
from discord import app_commands
from discord.ext import commands
from utils.database import db_manager
from utils.decorators import administration_only
from utils.command_manager import command_enabled
from utils.embed_style import hermes_embed, Colors

logger = logging.getLogger(__name__)


class AutoModCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._spam_tracker: dict = defaultdict(list)

    async def _get_config(self, guild_id: int) -> dict:
        row = await db_manager.fetchrow("SELECT * FROM automod_config WHERE guild_id = $1", guild_id)
        if row:
            return dict(row)
        return {
            'enabled': True,
            'blocked_words': [],
            'max_mentions': 10,
            'spam_threshold': 3,
            'spam_window_seconds': 5,
            'log_channel_id': None,
        }

    async def _log_action(self, guild_id: int, user_id: int, action: str, reason: str, channel_id: int = None):
        await db_manager.execute("""
            INSERT INTO automod_logs (guild_id, user_id, action, reason, channel_id)
            VALUES ($1, $2, $3, $4, $5)
        """, guild_id, user_id, action, reason, channel_id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        cfg = await self._get_config(message.guild.id)
        if not cfg['enabled']:
            return

        user_id = message.author.id
        guild_id = message.guild.id
        now = datetime.now(timezone.utc).timestamp()

        # Anti-spam
        window = cfg['spam_window_seconds']
        self._spam_tracker[user_id] = [t for t in self._spam_tracker[user_id] if now - t < window]
        self._spam_tracker[user_id].append(now)
        if len(self._spam_tracker[user_id]) >= cfg['spam_threshold']:
            try:
                await message.delete()
                await message.channel.send(
                    embed=hermes_embed(
                        description=f"⚠️ {message.author.mention} — Spam détecté, ralentis !",
                        color=Colors.ORANGE,
                    ),
                    delete_after=5,
                )
                await self._log_action(guild_id, user_id, 'spam', 'Messages répétés trop vite', message.channel.id)
                self._spam_tracker[user_id] = []
            except discord.Forbidden:
                pass
            return

        # Anti mentions massives
        if len(message.mentions) >= cfg['max_mentions']:
            try:
                await message.delete()
                await message.channel.send(
                    embed=hermes_embed(
                        description=f"⚠️ {message.author.mention} — Trop de mentions dans un seul message.",
                        color=Colors.ORANGE,
                    ),
                    delete_after=5,
                )
                await self._log_action(
                    guild_id, user_id, 'mass_mention',
                    f'{len(message.mentions)} mentions', message.channel.id,
                )
            except discord.Forbidden:
                pass
            return

        # Mots bloqués
        blocked = cfg.get('blocked_words') or []
        content_lower = message.content.lower()
        for word in blocked:
            if word and word.lower() in content_lower:
                try:
                    await message.delete()
                    await message.channel.send(
                        embed=hermes_embed(
                            description=f"⚠️ {message.author.mention} — Message supprimé : contenu non autorisé.",
                            color=Colors.ORANGE,
                        ),
                        delete_after=5,
                    )
                    await self._log_action(guild_id, user_id, 'blocked_word', f'Mot: {word}', message.channel.id)
                except discord.Forbidden:
                    pass
                return

    @app_commands.command(name="automod-config", description="Configurer l'auto-modération")
    @administration_only()
    @command_enabled(guild_specific=True)
    async def automod_config(
        self,
        interaction: discord.Interaction,
        max_mentions: int = None,
        spam_threshold: int = None,
        spam_window: int = None,
        enabled: bool = None,
    ):
        guild_id = interaction.guild_id
        await db_manager.execute("""
            INSERT INTO automod_config (guild_id, max_mentions, spam_threshold, spam_window_seconds, enabled)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (guild_id) DO UPDATE SET
                max_mentions = COALESCE($2, automod_config.max_mentions),
                spam_threshold = COALESCE($3, automod_config.spam_threshold),
                spam_window_seconds = COALESCE($4, automod_config.spam_window_seconds),
                enabled = COALESCE($5, automod_config.enabled)
        """, guild_id, max_mentions, spam_threshold, spam_window, enabled)

        cfg = await self._get_config(guild_id)
        embed = hermes_embed(
            title="🛡️  Configuration Auto-Mod",
            color=Colors.GREEN,
        )
        embed.add_field(name="Statut", value="✅ Activé" if cfg['enabled'] else "❌ Désactivé", inline=True)
        embed.add_field(name="Max mentions", value=f"**{cfg['max_mentions']}**", inline=True)
        embed.add_field(
            name="Anti-spam",
            value=f"**{cfg['spam_threshold']}** msgs / **{cfg['spam_window_seconds']}**s",
            inline=True,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(AutoModCog(bot))
