# bot/cogs/system/ticket_manager.py
"""Ticket manager — /newticket command + Discord ↔ web sync listener."""
import os
import logging
import discord
from discord import app_commands
from discord.ext import commands
from utils.database import db_manager
from utils.command_manager import command_enabled

logger = logging.getLogger(__name__)
TICKET_CATEGORY_ID = 777139814599491584


class TicketManagerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._ticket_channels: dict[int, int] = {}  # discord_channel_id -> ticket_id

    async def cog_load(self):
        """Load active ticket channels from DB into memory cache on startup."""
        rows = await db_manager.fetch(
            "SELECT id, discord_channel_id FROM tickets "
            "WHERE discord_channel_id IS NOT NULL AND status = 'open'"
        )
        self._ticket_channels = {row["discord_channel_id"]: row["id"] for row in rows}
        logger.info("TicketManagerCog: %d salon(s) ticket actif(s) chargé(s)", len(self._ticket_channels))

    @app_commands.command(name="newticket", description="Ouvrir un ticket de support")
    @command_enabled(guild_specific=True)
    async def newticket(self, interaction: discord.Interaction, titre: str):
        await interaction.response.defer(ephemeral=True)

        existing = await db_manager.fetchval(
            "SELECT id FROM tickets WHERE user_id = $1 AND status = 'open'",
            interaction.user.id,
        )
        if existing:
            await interaction.followup.send(
                f"❌ Tu as déjà un ticket ouvert (#{existing}). "
                "Ferme-le avant d'en créer un nouveau.",
                ephemeral=True,
            )
            return

        ticket_id = await db_manager.fetchval(
            "INSERT INTO tickets (user_id, title) VALUES ($1, $2) RETURNING id",
            interaction.user.id,
            titre,
        )

        channel_id = await self.create_ticket_channel(
            interaction.guild, interaction.user, ticket_id, titre
        )

        await db_manager.execute(
            "UPDATE tickets SET discord_channel_id = $1 WHERE id = $2",
            channel_id,
            ticket_id,
        )
        self._ticket_channels[channel_id] = ticket_id

        await interaction.followup.send(
            f"✅ Ticket **#{ticket_id}** créé ! → <#{channel_id}>",
            ephemeral=True,
        )

    async def create_ticket_channel(
        self,
        guild: discord.Guild,
        user: discord.Member | discord.User,
        ticket_id: int,
        title: str,
    ) -> int:
        """Create a ticket text channel in the ticket category. Returns the channel ID."""
        category = guild.get_channel(TICKET_CATEGORY_ID)
        admin_role_name = os.getenv("ADMIN_ROLE_NAME", "Administration")
        admin_role = discord.utils.get(guild.roles, name=admin_role_name)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_channels=True
            ),
        }
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True
            )

        safe_name = "".join(
            c if c.isalnum() or c == "-" else "-"
            for c in user.display_name.lower()
        )[:20].strip("-")
        safe_name = safe_name or "user"
        channel = await guild.create_text_channel(
            name=f"ticket-{safe_name}-{ticket_id}",
            category=category,
            overwrites=overwrites,
            reason=f"Ticket #{ticket_id}",
        )

        embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_id} — {title}",
            description=(
                f"Ouvert par {user.mention}\n"
                "Répondez ici ou sur le site web."
            ),
            color=0x57F287,
        )
        embed.set_footer(text="Hermes · SaucisseLand")
        await channel.send(embed=embed)
        return channel.id

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        ticket_id = self._ticket_channels.get(message.channel.id)
        if ticket_id is None:
            return

        status = await db_manager.fetchval(
            "SELECT status FROM tickets WHERE id = $1", ticket_id
        )
        if status != "open":
            return

        await db_manager.execute(
            """INSERT INTO ticket_messages
                   (ticket_id, author_id, author_name, content, source)
               VALUES ($1, $2, $3, $4, 'discord')""",
            ticket_id,
            message.author.id,
            message.author.display_name,
            message.content,
        )


async def setup(bot):
    await bot.add_cog(TicketManagerCog(bot))
