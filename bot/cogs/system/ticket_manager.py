"""
Système de tickets Discord-only.
Flux : /newticket [sujet] → salon privé créé → bouton Fermer → transcript envoyé
Contrôle staff : /ticket close | /ticket add | /ticket remove | /ticket list
"""

import io
import html
import asyncio
import unicodedata
import re
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime

from utils.database import db_manager

# ── Configuration pré-câblée ──────────────────────────────────────────────────

TICKET_CATEGORY_ID    = 777139814599491584
TICKET_TRANSCRIPT_ID  = 777140940053151774

# ─────────────────────────────────────────────────────────────────────────────


def _slug(text: str, max_len: int = 20) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:max_len] or "ticket"


# ── Vue de contrôle (persistante – survit au restart) ─────────────────────────

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Fermer le ticket", style=discord.ButtonStyle.danger,
        emoji="🔒", custom_id="ticket_ctrl_close",
    )
    async def btn_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog: Tickets = interaction.client.get_cog("Tickets")
        await cog.close_ticket(interaction)

    @discord.ui.button(
        label="Ajouter un membre", style=discord.ButtonStyle.primary,
        emoji="➕", custom_id="ticket_ctrl_add",
    )
    async def btn_add(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Sélectionnez le membre à ajouter :",
            view=AddMemberView(interaction.channel),
            ephemeral=True,
        )


class AddMemberView(discord.ui.View):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(timeout=60)
        self.channel = channel

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Choisir un membre…")
    async def sel(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        member = select.values[0]
        await self.channel.set_permissions(
            member, read_messages=True, send_messages=True, attach_files=True
        )
        await self.channel.send(
            embed=discord.Embed(
                description=f"➕ {member.mention} ajouté par {interaction.user.mention}.",
                color=discord.Color.green(),
            )
        )
        await interaction.response.edit_message(content=f"✅ {member.mention} ajouté.", view=None)


class CloseConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)
        self.confirmed = False

    @discord.ui.button(label="Confirmer", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.send_message("❌ Fermeture annulée.", ephemeral=True)

    async def on_timeout(self):
        self.stop()


# ── Modal formulaire ──────────────────────────────────────────────────────────

class NewTicketModal(discord.ui.Modal, title="🎫 Ouvrir un ticket"):
    sujet = discord.ui.TextInput(
        label="Sujet",
        placeholder="Ex : Problème avec mon rang, Demande de partenariat…",
        max_length=100,
        required=True,
    )
    description = discord.ui.TextInput(
        label="Description",
        placeholder="Décrivez votre demande en détail…",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cog: Tickets = interaction.client.get_cog("Tickets")
        await cog._create_ticket(interaction, self.sujet.value, self.description.value)


# ── Cog ───────────────────────────────────────────────────────────────────────

class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(TicketControlView())
        self._cleanup_closed_tickets.start()

    # ── /newticket ────────────────────────────────────────────────────────────

    @app_commands.command(name="newticket", description="Ouvrir un ticket de support")
    async def newticket(self, interaction: discord.Interaction):
        existing = await db_manager.fetchrow(
            "SELECT channel_id FROM tickets WHERE guild_id = $1 AND user_id = $2 AND status = 'open'",
            interaction.guild.id, interaction.user.id,
        )
        if existing:
            ch = interaction.guild.get_channel(existing["channel_id"])
            if ch:
                return await interaction.response.send_message(
                    f"❌ Vous avez déjà un ticket ouvert : {ch.mention}", ephemeral=True
                )
        await interaction.response.send_modal(NewTicketModal())

    async def _create_ticket(self, interaction: discord.Interaction, sujet: str, description: str):
        guild = interaction.guild

        category = guild.get_channel(TICKET_CATEGORY_ID)
        if not category:
            return await interaction.followup.send(
                "❌ Catégorie de tickets introuvable. Contactez un administrateur.", ephemeral=True
            )

        ticket_num = (
            await db_manager.fetchval("SELECT COUNT(*) FROM tickets WHERE guild_id = $1", guild.id) or 0
        ) + 1

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(
                read_messages=True, send_messages=True, attach_files=True
            ),
            guild.me: discord.PermissionOverwrite(
                read_messages=True, send_messages=True,
                manage_channels=True, manage_messages=True,
            ),
        }
        for role in guild.roles:
            if role.permissions.administrator or role.permissions.manage_channels:
                overwrites[role] = discord.PermissionOverwrite(
                    read_messages=True, send_messages=True
                )

        channel_name = f"ticket-{_slug(interaction.user.display_name)}"
        try:
            channel = await category.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                topic=f"Ticket de {interaction.user} | {sujet[:80]}",
            )
        except discord.Forbidden:
            return await interaction.followup.send(
                "❌ Je n'ai pas la permission de créer des salons dans cette catégorie.", ephemeral=True
            )

        await db_manager.execute(
            "INSERT INTO tickets (guild_id, channel_id, user_id, ticket_number, subject) "
            "VALUES ($1, $2, $3, $4, $5)",
            guild.id, channel.id, interaction.user.id, ticket_num, sujet[:200],
        )

        welcome = discord.Embed(
            title=f"🎫 Ticket #{ticket_num:04d} — {sujet}",
            color=0x5865F2,
            timestamp=discord.utils.utcnow(),
        )
        welcome.add_field(name="👤 Ouvert par", value=interaction.user.mention, inline=True)
        welcome.add_field(name="📋 Sujet", value=sujet, inline=True)
        welcome.add_field(name="📝 Description", value=description, inline=False)
        welcome.set_thumbnail(url=interaction.user.display_avatar.url)
        welcome.set_footer(text=f"Ticket #{ticket_num:04d} • Le staff vous répondra dès que possible")
        await channel.send(content=interaction.user.mention, embed=welcome, view=TicketControlView())

        trans_ch = guild.get_channel(TICKET_TRANSCRIPT_ID)
        if trans_ch:
            log_e = discord.Embed(
                title="🎫 Nouveau ticket ouvert",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )
            log_e.add_field(name="Utilisateur", value=f"{interaction.user.mention} (`{interaction.user.id}`)")
            log_e.add_field(name="Salon", value=channel.mention)
            log_e.add_field(name="Sujet", value=sujet)
            log_e.add_field(name="Description", value=description[:500], inline=False)
            await trans_ch.send(embed=log_e)

        await interaction.followup.send(f"✅ Votre ticket a été créé : {channel.mention}", ephemeral=True)

    # ── Fermeture ─────────────────────────────────────────────────────────────

    async def close_ticket(self, interaction: discord.Interaction):
        ticket = await db_manager.fetchrow(
            "SELECT id, user_id, subject, ticket_number FROM tickets "
            "WHERE channel_id = $1 AND status = 'open'",
            interaction.channel.id,
        )
        if not ticket:
            return await interaction.response.send_message(
                "❌ Ce salon n'est pas un ticket actif.", ephemeral=True
            )

        # Seuls le créateur du ticket et le staff (manage_channels) peuvent fermer
        is_owner = interaction.user.id == ticket["user_id"]
        is_staff = interaction.channel.permissions_for(interaction.user).manage_channels
        if not is_owner and not is_staff:
            return await interaction.response.send_message(
                "❌ Seul le créateur du ticket ou un membre du staff peut fermer ce ticket.",
                ephemeral=True,
            )

        view = CloseConfirmView()
        await interaction.response.send_message(
            "⚠️ Confirmer la fermeture de ce ticket ?", view=view, ephemeral=True
        )
        await view.wait()
        if not view.confirmed:
            return

        transcript_bytes = await self._html_transcript(interaction.channel, ticket["ticket_number"])
        filename = f"ticket-{ticket['ticket_number']:04d}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.html"

        user = interaction.guild.get_member(ticket["user_id"])

        trans_ch = interaction.guild.get_channel(TICKET_TRANSCRIPT_ID)
        if trans_ch:
            t_embed = discord.Embed(
                title=f"📄 Transcript — {ticket['subject']}",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow(),
            )
            t_embed.add_field(name="Salon", value=interaction.channel.name)
            t_embed.add_field(name="Ouvert par", value=user.mention if user else f"`{ticket['user_id']}`")
            t_embed.add_field(name="Fermé par", value=interaction.user.mention)
            t_embed.set_footer(text=f"Ticket #{ticket['ticket_number']:04d}")
            await trans_ch.send(
                embed=t_embed,
                file=discord.File(io.BytesIO(transcript_bytes), filename=filename),
            )

        await db_manager.execute(
            "UPDATE tickets SET status = 'closed', closed_at = NOW() WHERE id = $1",
            ticket["id"],
        )

        # Renommer le salon : ticket-pseudo✅
        try:
            display = user.display_name if user else str(ticket["user_id"])
            await interaction.channel.edit(name=f"ticket-{_slug(display)}✅")
        except (discord.Forbidden, discord.HTTPException):
            pass

        close_e = discord.Embed(
            title="🔒 Ticket fermé",
            description=(
                "Ce ticket a été fermé et le transcript a été sauvegardé.\n"
                "**Ce salon sera supprimé automatiquement dans 48h.**"
            ),
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        close_e.set_footer(text=f"Fermé par {interaction.user}")
        await interaction.channel.send(embed=close_e)

    # ── Tâche de suppression différée (48h après fermeture) ───────────────────

    @tasks.loop(minutes=10)
    async def _cleanup_closed_tickets(self):
        rows = await db_manager.fetch(
            "SELECT guild_id, channel_id FROM tickets "
            "WHERE status = 'closed' AND closed_at IS NOT NULL "
            "AND closed_at + interval '48 hours' <= NOW() AND channel_id IS NOT NULL"
        )
        for row in rows:
            guild = self.bot.get_guild(row["guild_id"])
            if not guild:
                continue
            channel = guild.get_channel(row["channel_id"])
            if channel:
                try:
                    await channel.delete(reason="Ticket fermé depuis 48h")
                except (discord.NotFound, discord.Forbidden):
                    pass
            # Marquer channel_id comme nul pour ne plus tenter de supprimer
            await db_manager.execute(
                "UPDATE tickets SET channel_id = NULL WHERE channel_id = $1",
                row["channel_id"],
            )

    @_cleanup_closed_tickets.before_loop
    async def _before_cleanup(self):
        await self.bot.wait_until_ready()

    # ── HTML transcript ───────────────────────────────────────────────────────

    async def _html_transcript(self, channel: discord.TextChannel, ticket_num: int) -> bytes:
        messages_html = ""
        async for msg in channel.history(limit=500, oldest_first=True):
            content = html.escape(msg.content) if msg.content else ""
            embed_html = ""
            for emb in msg.embeds:
                embed_html += '<div class="emb">'
                if emb.title:
                    embed_html += f'<b>{html.escape(emb.title)}</b><br>'
                if emb.description:
                    embed_html += f'<span>{html.escape(emb.description)}</span>'
                for fld in emb.fields:
                    embed_html += f'<div><b>{html.escape(fld.name)}</b>: {html.escape(fld.value)}</div>'
                embed_html += "</div>"
            attach_html = "".join(
                f'<div class="att">📎 <a href="{a.url}">{html.escape(a.filename)}</a></div>'
                for a in msg.attachments
            )
            bot_tag = '<span class="bt">BOT</span>' if msg.author.bot else ""
            ts = msg.created_at.strftime("%d/%m/%Y %H:%M:%S")
            initials = msg.author.display_name[:2].upper()
            content_div = '<div class="mt">' + content + '</div>' if content else ''
            messages_html += (
                f'<div class="mg"><div class="av">{initials}</div><div class="mc">'
                f'<div class="mh"><span class="un">{html.escape(str(msg.author))}</span>'
                f'{bot_tag}<span class="ts">{ts}</span></div>'
                f'{content_div}{embed_html}{attach_html}</div></div>'
            )
        doc = (
            f'<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">'
            f'<title>Ticket #{ticket_num:04d}</title>'
            f'<style>*{{box-sizing:border-box;margin:0;padding:0}}'
            f'body{{background:#36393f;color:#dcddde;font-family:Arial,sans-serif;line-height:1.4}}'
            f'.hd{{background:#2f3136;padding:20px;border-bottom:2px solid #202225}}'
            f'.hd h1{{color:#fff}}.hd p{{color:#8e9297;font-size:.85em;margin-top:4px}}'
            f'.mg{{display:flex;align-items:flex-start;padding:8px 16px}}.mg:hover{{background:#32353b}}'
            f'.av{{width:40px;height:40px;border-radius:50%;background:#5865f2;margin-right:14px;'
            f'flex-shrink:0;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700}}'
            f'.mc{{flex:1;min-width:0}}.mh{{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}}'
            f'.un{{font-weight:700;color:#fff}}.bt{{background:#5865f2;color:#fff;font-size:.6em;padding:1px 5px;border-radius:3px}}'
            f'.ts{{color:#72767d;font-size:.72em}}.mt{{margin-top:3px;white-space:pre-wrap;word-break:break-word}}'
            f'.emb{{border-left:4px solid #5865f2;background:#2f3136;border-radius:0 4px 4px 0;'
            f'padding:10px 14px;margin-top:6px;max-width:520px}}'
            f'.att{{margin-top:4px;font-size:.85em}}.att a{{color:#00b0f4}}'
            f'.ft{{background:#2f3136;padding:14px;text-align:center;color:#72767d;font-size:.78em;'
            f'border-top:1px solid #202225}}</style></head>'
            f'<body><div class="hd">'
            f'<h1>🎫 Transcript — Ticket #{ticket_num:04d} ({html.escape(channel.name)})</h1>'
            f'<p>Généré le {datetime.now().strftime("%d/%m/%Y à %H:%M:%S")} • {html.escape(channel.guild.name)}</p></div>'
            f'{messages_html}<div class="ft">Hermes — Système de tickets</div></body></html>'
        )
        return doc.encode("utf-8")

    # ── Slash commands de gestion ─────────────────────────────────────────────

    ticket_group = app_commands.Group(name="ticket", description="Gestion des tickets (staff)")

    @ticket_group.command(name="close", description="Fermer le ticket dans ce salon")
    async def ticket_close(self, interaction: discord.Interaction):
        await self.close_ticket(interaction)

    @ticket_group.command(name="add", description="Ajouter un membre à ce ticket")
    @app_commands.describe(member="Le membre à ajouter")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_add(self, interaction: discord.Interaction, member: discord.Member):
        if not await db_manager.fetchrow(
            "SELECT id FROM tickets WHERE channel_id = $1 AND status = 'open'",
            interaction.channel.id,
        ):
            return await interaction.response.send_message(
                "❌ Ce salon n'est pas un ticket actif.", ephemeral=True
            )
        await interaction.channel.set_permissions(
            member, read_messages=True, send_messages=True, attach_files=True
        )
        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"➕ {member.mention} ajouté par {interaction.user.mention}.",
                color=discord.Color.green(),
            )
        )

    @ticket_group.command(name="remove", description="Retirer un membre de ce ticket")
    @app_commands.describe(member="Le membre à retirer")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_remove(self, interaction: discord.Interaction, member: discord.Member):
        if not await db_manager.fetchrow(
            "SELECT id FROM tickets WHERE channel_id = $1 AND status = 'open'",
            interaction.channel.id,
        ):
            return await interaction.response.send_message(
                "❌ Ce salon n'est pas un ticket actif.", ephemeral=True
            )
        await interaction.channel.set_permissions(member, overwrite=None)
        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"➖ {member.mention} retiré par {interaction.user.mention}.",
                color=discord.Color.red(),
            )
        )

    @ticket_group.command(name="list", description="Lister les tickets ouverts")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_list(self, interaction: discord.Interaction):
        tickets = await db_manager.fetch(
            "SELECT channel_id, user_id, subject, created_at FROM tickets "
            "WHERE guild_id = $1 AND status = 'open' ORDER BY created_at DESC",
            interaction.guild.id,
        )
        if not tickets:
            return await interaction.response.send_message("✅ Aucun ticket ouvert.", ephemeral=True)

        embed = discord.Embed(
            title=f"🎫 Tickets ouverts ({len(tickets)})",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        for t in tickets[:25]:
            ch = interaction.guild.get_channel(t["channel_id"])
            member = interaction.guild.get_member(t["user_id"])
            embed.add_field(
                name=ch.name if ch else str(t["channel_id"]),
                value=f"👤 {member.mention if member else t['user_id']}\n📋 {t['subject']}\n📅 {str(t['created_at'])[:10]}",
                inline=True,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
