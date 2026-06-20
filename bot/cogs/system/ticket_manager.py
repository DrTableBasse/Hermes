"""
Système de tickets Discord-only.
Flux admin  : /ticket setup → wizard 4 étapes → panneau avec menu de sélection
Flux user   : sélectionner un type → formulaire (optionnel) → salon créé
Contrôle    : /ticket close | /ticket add | /ticket remove | /ticket list
"""

import re
import unicodedata
import io
import html
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

from utils.db import db_manager


def _slug(text: str, max_len: int = 25) -> str:
    normalized = unicodedata.normalize("NFD", text)
    text = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:max_len] or "ticket"


# ── Wizard session storage ─────────────────────────────────────────────────────

_sessions: dict[tuple[int, int], dict] = {}
_TICKETS_PER_PAGE = 10


def _new_sess(guild_id: int, user_id: int) -> dict:
    key = (guild_id, user_id)
    _sessions[key] = {
        "panel_channel_id": None,
        "category_id": None,
        "log_channel_id": None,
        "transcript_channel_id": None,
        "panel_title": None,
        "panel_description": None,
        "panel_color": 0x5865F2,
        "panel_footer": None,
        "num_types": 0,
        "types": [],
    }
    return _sessions[key]


def _parse_color(s: str) -> int:
    try:
        return int(s.strip().lstrip("#"), 16)
    except ValueError:
        return 0x5865F2


def _ch_name(guild: discord.Guild, cid: int | None) -> str:
    if not cid:
        return "❌ Non sélectionné"
    ch = guild.get_channel(cid)
    return ch.mention if ch else "❌ Introuvable"


# ── Wizard Step 1 : démarrage ──────────────────────────────────────────────────

class WizardStartView(discord.ui.View):
    def __init__(self, key: tuple):
        super().__init__(timeout=300)
        self.key = key

    @discord.ui.button(label="🚀 Commencer la configuration", style=discord.ButtonStyle.primary)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.key not in _sessions:
            return await interaction.response.send_message(
                "❌ Session expirée. Relancez `/ticket setup`.", ephemeral=True
            )
        view = WizardChannelsView(self.key)
        await interaction.response.edit_message(embed=view.make_embed(interaction.guild), view=view)


# ── Wizard Step 2 : sélection des salons ──────────────────────────────────────

class WizardChannelsView(discord.ui.View):
    def __init__(self, key: tuple):
        super().__init__(timeout=300)
        self.key = key
        sess = _sessions[key]
        self.sel_panel_id = sess.get("panel_channel_id")
        self.sel_cat_id = sess.get("category_id")
        self.sel_log_id = sess.get("log_channel_id")
        self.sel_trans_id = sess.get("transcript_channel_id")

    def make_embed(self, guild: discord.Guild) -> discord.Embed:
        e = discord.Embed(
            title="⚙️ Étape 1/4 — Salons et catégorie",
            description=(
                "Sélectionnez les **4 salons** ci-dessous puis cliquez **Confirmer**.\n\n"
                "Les salons de logs et transcripts doivent être accessibles uniquement au staff."
            ),
            color=0x5865F2,
        )
        e.add_field(name="1️⃣ Panneau (visible par tous)", value=_ch_name(guild, self.sel_panel_id), inline=True)
        e.add_field(name="2️⃣ Catégorie des tickets", value=_ch_name(guild, self.sel_cat_id), inline=True)
        e.add_field(name="3️⃣ Logs (staff)", value=_ch_name(guild, self.sel_log_id), inline=True)
        e.add_field(name="4️⃣ Transcripts (staff)", value=_ch_name(guild, self.sel_trans_id), inline=True)
        return e

    @discord.ui.select(cls=discord.ui.ChannelSelect, placeholder="1️⃣ Salon du panneau (texte)", channel_types=[discord.ChannelType.text], row=0)
    async def sel_panel(self, interaction: discord.Interaction, sel: discord.ui.ChannelSelect):
        self.sel_panel_id = sel.values[0].id
        _sessions[self.key]["panel_channel_id"] = sel.values[0].id
        await interaction.response.edit_message(embed=self.make_embed(interaction.guild), view=self)

    @discord.ui.select(cls=discord.ui.ChannelSelect, placeholder="2️⃣ Catégorie pour les tickets", channel_types=[discord.ChannelType.category], row=1)
    async def sel_category(self, interaction: discord.Interaction, sel: discord.ui.ChannelSelect):
        self.sel_cat_id = sel.values[0].id
        _sessions[self.key]["category_id"] = sel.values[0].id
        await interaction.response.edit_message(embed=self.make_embed(interaction.guild), view=self)

    @discord.ui.select(cls=discord.ui.ChannelSelect, placeholder="3️⃣ Salon des logs (staff)", channel_types=[discord.ChannelType.text], row=2)
    async def sel_log(self, interaction: discord.Interaction, sel: discord.ui.ChannelSelect):
        self.sel_log_id = sel.values[0].id
        _sessions[self.key]["log_channel_id"] = sel.values[0].id
        await interaction.response.edit_message(embed=self.make_embed(interaction.guild), view=self)

    @discord.ui.select(cls=discord.ui.ChannelSelect, placeholder="4️⃣ Salon des transcripts (staff)", channel_types=[discord.ChannelType.text], row=3)
    async def sel_transcript(self, interaction: discord.Interaction, sel: discord.ui.ChannelSelect):
        self.sel_trans_id = sel.values[0].id
        _sessions[self.key]["transcript_channel_id"] = sel.values[0].id
        await interaction.response.edit_message(embed=self.make_embed(interaction.guild), view=self)

    @discord.ui.button(label="✅ Confirmer et continuer", style=discord.ButtonStyle.success, row=4)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        sess = _sessions[self.key]
        missing = [k for k in ("panel_channel_id", "category_id", "log_channel_id", "transcript_channel_id") if not sess.get(k)]
        if missing:
            return await interaction.response.send_message("❌ Veuillez sélectionner les 4 salons avant de continuer.", ephemeral=True)
        await interaction.response.send_modal(WizardAppearanceModal(self.key))


# ── Wizard Step 3 : apparence (modal) ─────────────────────────────────────────

class WizardAppearanceModal(discord.ui.Modal, title="🎨 Étape 2/4 — Apparence du panneau"):
    f_title = discord.ui.TextInput(
        label="Titre du panneau",
        placeholder="Ex : 🎫 Support — Ouvrir un ticket",
        max_length=256,
        required=True,
    )
    f_desc = discord.ui.TextInput(
        label="Description du panneau",
        style=discord.TextStyle.paragraph,
        max_length=4000,
        required=True,
    )
    f_footer = discord.ui.TextInput(label="Pied de page (optionnel)", max_length=256, required=False)
    f_color = discord.ui.TextInput(
        label="Couleur HEX (optionnel)",
        placeholder="Ex : 5865f2  ou  #FF5733",
        max_length=10,
        required=False,
    )

    def __init__(self, key: tuple):
        super().__init__()
        self.key = key

    async def on_submit(self, interaction: discord.Interaction):
        sess = _sessions[self.key]
        sess["panel_title"] = self.f_title.value
        sess["panel_description"] = self.f_desc.value
        sess["panel_footer"] = self.f_footer.value or None
        sess["panel_color"] = _parse_color(self.f_color.value) if self.f_color.value else 0x5865F2
        embed = discord.Embed(
            title="⚙️ Étape 3/4 — Types de tickets",
            description="Combien de **types de tickets** souhaitez-vous proposer ?\n\nChaque type a son propre formulaire et message d'accueil.",
            color=0x5865F2,
        )
        await interaction.response.send_message(embed=embed, view=WizardNumTypesView(self.key), ephemeral=True)


# ── Wizard Step 4 : nombre de types ───────────────────────────────────────────

class WizardNumTypesView(discord.ui.View):
    def __init__(self, key: tuple):
        super().__init__(timeout=300)
        self.key = key

    async def _pick(self, interaction: discord.Interaction, n: int):
        sess = _sessions[self.key]
        sess["num_types"] = n
        sess["types"] = [{} for _ in range(n)]
        embed = discord.Embed(
            title=f"⚙️ {n} type(s) — Configuration du type 1/{n}",
            description="Cliquez sur **Configurer** pour renseigner le nom, l'emoji, la description et le message d'accueil.",
            color=0x5865F2,
        )
        await interaction.response.edit_message(embed=embed, view=WizardTypeStepView(self.key, 0))

    @discord.ui.button(label="1 type", style=discord.ButtonStyle.secondary)
    async def b1(self, i, b): await self._pick(i, 1)

    @discord.ui.button(label="2 types", style=discord.ButtonStyle.secondary)
    async def b2(self, i, b): await self._pick(i, 2)

    @discord.ui.button(label="3 types", style=discord.ButtonStyle.secondary)
    async def b3(self, i, b): await self._pick(i, 3)

    @discord.ui.button(label="4 types", style=discord.ButtonStyle.secondary)
    async def b4(self, i, b): await self._pick(i, 4)


# ── Wizard Step 5a : config d'un type ─────────────────────────────────────────

class WizardTypeStepView(discord.ui.View):
    def __init__(self, key: tuple, idx: int):
        super().__init__(timeout=300)
        self.key = key
        self.idx = idx

    @discord.ui.button(label="⚙️ Configurer ce type", style=discord.ButtonStyle.primary)
    async def configure(self, interaction: discord.Interaction, button: discord.ui.Button):
        n = _sessions[self.key]["num_types"]
        await interaction.response.send_modal(WizardTypeConfigModal(self.key, self.idx, n))


class WizardTypeConfigModal(discord.ui.Modal):
    f_label = discord.ui.TextInput(label="Nom du type", placeholder="Ex : Support, Signalement, Recrutement…", max_length=80, required=True)
    f_emoji = discord.ui.TextInput(label="Emoji (optionnel)", placeholder="Ex : ❓  🚨  🤝", max_length=10, required=False)
    f_desc = discord.ui.TextInput(label="Description courte (dans le menu)", max_length=100, required=False)
    f_welcome = discord.ui.TextInput(
        label="Message d'accueil dans le ticket",
        placeholder="Ex : Bonjour ! Décrivez votre problème ci-dessous.",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )

    def __init__(self, key: tuple, idx: int, total: int):
        super().__init__(title=f"📋 Type {idx + 1}/{total}")
        self.key = key
        self.idx = idx

    async def on_submit(self, interaction: discord.Interaction):
        sess = _sessions[self.key]
        label = self.f_label.value
        sess["types"][self.idx] = {
            "label": label,
            "emoji": self.f_emoji.value.strip() or "📝",
            "description": self.f_desc.value or "",
            "welcome_message": self.f_welcome.value,
            "fields": [],
            "notification_channel_id": None,
        }
        n = sess["num_types"]
        embed = discord.Embed(
            title=f"📋 Type {self.idx + 1}/{n} : {label}",
            description=(
                "Souhaitez-vous ajouter un **formulaire** à ce type ?\n\n"
                "Vous pouvez définir jusqu'à **5 champs** personnalisés.\n"
                "Sans formulaire, le ticket s'ouvre directement."
            ),
            color=0x5865F2,
        )
        await interaction.response.send_message(embed=embed, view=WizardTypeFieldsStepView(self.key, self.idx), ephemeral=True)


# ── Wizard Step 5b : formulaire d'un type ─────────────────────────────────────

class WizardTypeFieldsStepView(discord.ui.View):
    def __init__(self, key: tuple, idx: int):
        super().__init__(timeout=300)
        self.key = key
        self.idx = idx

    @discord.ui.button(label="📝 Configurer le formulaire", style=discord.ButtonStyle.primary)
    async def configure(self, interaction: discord.Interaction, button: discord.ui.Button):
        label = _sessions[self.key]["types"][self.idx].get("label", "")
        await interaction.response.send_modal(WizardTypeFieldsModal(self.key, self.idx, label))

    @discord.ui.button(label="⏭️ Passer (pas de formulaire)", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _wizard_go_notif(interaction, self.key, self.idx)


class WizardTypeFieldsModal(discord.ui.Modal):
    f1 = discord.ui.TextInput(label="Champ 1 — Label (obligatoire)", max_length=80, required=True)
    f2 = discord.ui.TextInput(label="Champ 2 — Label (optionnel, vide = ignoré)", max_length=80, required=False)
    f3 = discord.ui.TextInput(label="Champ 3 — Label (optionnel)", max_length=80, required=False)
    f4 = discord.ui.TextInput(label="Champ 4 — Label (optionnel)", max_length=80, required=False)
    f5 = discord.ui.TextInput(label="Champ 5 — Label (optionnel)", max_length=80, required=False)

    def __init__(self, key: tuple, idx: int, type_label: str):
        super().__init__(title=f"📝 Formulaire — {type_label[:35]}")
        self.key = key
        self.idx = idx

    async def on_submit(self, interaction: discord.Interaction):
        fields = []
        for i, f in enumerate([self.f1, self.f2, self.f3, self.f4, self.f5]):
            if f.value.strip():
                fields.append({"label": f.value.strip(), "required": i == 0})
        _sessions[self.key]["types"][self.idx]["fields"] = fields
        await _wizard_go_notif(interaction, self.key, self.idx)


# ── Wizard Step 5c : canal de notification ────────────────────────────────────

async def _wizard_go_notif(interaction: discord.Interaction, key: tuple, idx: int):
    label = _sessions[key]["types"][idx].get("label", "")
    embed = discord.Embed(
        title=f"📣 Canal de notification — {label}",
        description=(
            "Souhaitez-vous qu'un **résumé du formulaire** soit envoyé dans un salon "
            "spécifique à chaque ouverture d'un ticket de ce type ?\n\n"
            "**Exemple :** type « Recrutement » → envoi automatique dans `#candidatures`."
        ),
        color=0x5865F2,
    )
    await interaction.response.send_message(embed=embed, view=WizardNotifChannelView(key, idx), ephemeral=True)


class WizardNotifChannelView(discord.ui.View):
    def __init__(self, key: tuple, idx: int):
        super().__init__(timeout=300)
        self.key = key
        self.idx = idx

    @discord.ui.select(cls=discord.ui.ChannelSelect, placeholder="Salon de notification (optionnel)…", channel_types=[discord.ChannelType.text], row=0)
    async def sel_notif(self, interaction: discord.Interaction, sel: discord.ui.ChannelSelect):
        _sessions[self.key]["types"][self.idx]["notification_channel_id"] = sel.values[0].id
        embed = discord.Embed(
            title="📣 Canal de notification sélectionné",
            description=f"Les résumés seront envoyés dans {sel.values[0].mention}.\nCliquez **Confirmer** pour continuer.",
            color=0x57F287,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="✅ Confirmer", style=discord.ButtonStyle.success, row=1)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _wizard_after_type(interaction, self.key, self.idx)

    @discord.ui.button(label="⏭️ Passer (sans notification)", style=discord.ButtonStyle.secondary, row=1)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _wizard_after_type(interaction, self.key, self.idx)


async def _wizard_after_type(interaction: discord.Interaction, key: tuple, idx: int):
    sess = _sessions[key]
    n = sess["num_types"]
    next_idx = idx + 1
    if next_idx < n:
        embed = discord.Embed(
            title=f"✅ Type {idx + 1}/{n} configuré",
            description=f"Passons à la configuration du **type {next_idx + 1}/{n}**.",
            color=0x57F287,
        )
        await interaction.response.send_message(embed=embed, view=WizardTypeStepView(key, next_idx), ephemeral=True)
    else:
        await _wizard_show_preview(interaction, key)


# ── Wizard Step 6 : aperçu + publication ──────────────────────────────────────

async def _wizard_show_preview(interaction: discord.Interaction, key: tuple):
    sess = _sessions[key]
    guild = interaction.guild
    panel_preview = discord.Embed(
        title=sess["panel_title"],
        description=sess["panel_description"],
        color=sess["panel_color"],
    )
    if sess["panel_footer"]:
        panel_preview.set_footer(text=sess["panel_footer"])
    types_lines = []
    for t in sess["types"]:
        fields_info = f"{len(t['fields'])} champ(s)" if t.get("fields") else "direct"
        notif = " 📣" if t.get("notification_channel_id") else ""
        types_lines.append(f"{t.get('emoji', '📝')} **{t.get('label', '?')}** — {fields_info}{notif}")
    summary = discord.Embed(title="📋 Récapitulatif de configuration", color=0x5865F2)
    summary.add_field(
        name="📁 Salons",
        value=(
            f"Panneau : {_ch_name(guild, sess['panel_channel_id'])}\n"
            f"Catégorie : {_ch_name(guild, sess['category_id'])}\n"
            f"Logs : {_ch_name(guild, sess['log_channel_id'])}\n"
            f"Transcripts : {_ch_name(guild, sess['transcript_channel_id'])}"
        ),
        inline=False,
    )
    summary.add_field(
        name=f"🎫 Types ({len(sess['types'])})",
        value="\n".join(types_lines) or "Aucun",
        inline=False,
    )
    summary.set_footer(text="Vérifiez les informations puis publiez le panneau.")
    await interaction.response.send_message(
        content="**Aperçu du panneau :**",
        embeds=[summary, panel_preview],
        view=WizardPublishView(key),
        ephemeral=True,
    )


class WizardPublishView(discord.ui.View):
    def __init__(self, key: tuple):
        super().__init__(timeout=300)
        self.key = key

    @discord.ui.button(label="✅ Publier le panneau", style=discord.ButtonStyle.success)
    async def publish(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        cog: Tickets = interaction.client.get_cog("Tickets")
        await cog._wizard_publish(interaction, self.key)

    @discord.ui.button(label="🔄 Recommencer", style=discord.ButtonStyle.danger)
    async def restart(self, interaction: discord.Interaction, button: discord.ui.Button):
        _sessions.pop(self.key, None)
        await interaction.response.send_message(
            "Configuration annulée. Relancez `/ticket setup` pour recommencer.", ephemeral=True
        )


# ── Runtime : panneau d'ouverture (persistant) ────────────────────────────────

class TicketOpenView(discord.ui.View):
    def __init__(self, options: list[discord.SelectOption] | None = None):
        super().__init__(timeout=None)
        if options:
            self.panel_select.options = options

    @discord.ui.select(
        placeholder="📋 Sélectionner le type de ticket…",
        custom_id="ticket_panel_select",
        options=[discord.SelectOption(label="Chargement…", value="0")],
    )
    async def panel_select(self, interaction: discord.Interaction, sel: discord.ui.Select):
        raw = sel.values[0] if sel.values else ""
        try:
            type_id = int(raw)
        except (ValueError, TypeError):
            return await interaction.response.send_message(
                "⚠️ Ce panneau est **obsolète**. Relancez `/ticket setup` pour le recréer.", ephemeral=True
            )
        cog: Tickets = interaction.client.get_cog("Tickets")
        t = await db_manager.fetchrow(
            "SELECT * FROM ticket_types WHERE id = $1 AND guild_id = $2",
            type_id, interaction.guild.id,
        )
        if not t:
            return await interaction.response.send_message(
                "❌ Type introuvable en base de données. Relancez `/ticket setup`.", ephemeral=True
            )
        has_form = any(t.get(f"field{i}_label") for i in range(1, 6))
        if has_form:
            await interaction.response.send_modal(TicketFormModal(t, cog))
        else:
            await interaction.response.defer(ephemeral=True)
            try:
                await cog.create_ticket(interaction, t, {})
            except Exception as exc:
                import traceback
                traceback.print_exc()
                await interaction.followup.send(f"❌ Erreur lors de la création du ticket : `{exc}`", ephemeral=True)


class TicketFormModal(discord.ui.Modal):
    def __init__(self, type_row: dict, cog: "Tickets"):
        super().__init__(title=f"📋 {type_row['label']}")
        self.type_row = type_row
        self.cog = cog
        self.field_inputs: list[discord.ui.TextInput] = []
        self.field_labels: list[str] = []
        for i in range(1, 6):
            label = type_row.get(f"field{i}_label")
            if not label:
                break
            required = bool(type_row.get(f"field{i}_required", False))
            fi = discord.ui.TextInput(
                label=label,
                required=required,
                style=discord.TextStyle.paragraph if i == 1 else discord.TextStyle.short,
                max_length=1024,
            )
            self.field_labels.append(label)
            self.field_inputs.append(fi)
            self.add_item(fi)

    async def on_submit(self, interaction: discord.Interaction):
        answers = {label: fi.value for label, fi in zip(self.field_labels, self.field_inputs) if fi.value}
        await interaction.response.defer(ephemeral=True)
        try:
            await self.cog.create_ticket(interaction, self.type_row, answers)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"❌ Erreur lors de la création du ticket : `{exc}`", ephemeral=True)


# ── Runtime : contrôle dans le ticket (persistant) ────────────────────────────

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Fermer le ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ticket_ctrl_close")
    async def btn_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog: Tickets = interaction.client.get_cog("Tickets")
        await cog.close_ticket(interaction)

    @discord.ui.button(label="Ajouter un membre", style=discord.ButtonStyle.primary, emoji="➕", custom_id="ticket_ctrl_add")
    async def btn_add(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Sélectionnez le membre à ajouter au ticket :",
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
        await self.channel.set_permissions(member, read_messages=True, send_messages=True, attach_files=True)
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

    @discord.ui.button(label="Confirmer la fermeture", style=discord.ButtonStyle.danger, emoji="✅")
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


class TicketListView(discord.ui.View):
    def __init__(self, tickets: list, guild: discord.Guild):
        super().__init__(timeout=120)
        self.tickets = tickets
        self.guild = guild
        self.page = 0
        self.total_pages = max(1, (len(tickets) + _TICKETS_PER_PAGE - 1) // _TICKETS_PER_PAGE)
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= self.total_pages - 1

    def make_embed(self) -> discord.Embed:
        start = self.page * _TICKETS_PER_PAGE
        page_tickets = self.tickets[start: start + _TICKETS_PER_PAGE]
        embed = discord.Embed(
            title="🎫 Tickets ouverts",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        for t in page_tickets:
            ch = self.guild.get_channel(t["channel_id"])
            member = self.guild.get_member(t["user_id"])
            embed.add_field(
                name=ch.name if ch else str(t["channel_id"]),
                value=f"👤 {member.mention if member else t['user_id']}\n📋 {t['subject']}\n📅 {str(t['created_at'])[:10]}",
                inline=True,
            )
        embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages} • Total : {len(self.tickets)} ticket(s)")
        return embed

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)


# ── Cog ───────────────────────────────────────────────────────────────────────

class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(TicketOpenView())
        bot.add_view(TicketControlView())

    # ── Wizard publish ────────────────────────────────────────────────────────

    async def _wizard_publish(self, interaction: discord.Interaction, key: tuple):
        sess = _sessions.get(key)
        if not sess:
            return await interaction.followup.send("❌ Session expirée.", ephemeral=True)

        guild = interaction.guild
        panel_ch = guild.get_channel(sess["panel_channel_id"])
        category = guild.get_channel(sess["category_id"])
        if not panel_ch or not category:
            return await interaction.followup.send("❌ Salon ou catégorie introuvable.", ephemeral=True)

        old_panel = await db_manager.fetchrow(
            "SELECT id, channel_id, message_id FROM ticket_panels WHERE guild_id = $1", guild.id
        )
        if old_panel and old_panel["message_id"]:
            try:
                old_ch = guild.get_channel(old_panel["channel_id"])
                if old_ch:
                    old_msg = await old_ch.fetch_message(old_panel["message_id"])
                    await old_msg.delete()
            except Exception:
                pass
            await db_manager.execute("DELETE FROM ticket_panels WHERE guild_id = $1", guild.id)

        panel_id = await db_manager.fetchval(
            """INSERT INTO ticket_panels
               (guild_id, channel_id, category_id, log_channel_id, transcript_channel_id,
                title, description, color, footer)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id""",
            guild.id, panel_ch.id, category.id,
            sess["log_channel_id"], sess["transcript_channel_id"],
            sess["panel_title"], sess["panel_description"],
            sess["panel_color"], sess["panel_footer"],
        )

        type_db_ids = []
        for t in sess["types"]:
            fields = t.get("fields", [])
            params = [
                panel_id, guild.id, t["label"], t["emoji"], t.get("description", ""),
                t["welcome_message"], t.get("notification_channel_id"),
            ]
            for i in range(5):
                if i < len(fields):
                    params += [fields[i]["label"], fields[i]["required"]]
                else:
                    params += [None, False]
            type_id = await db_manager.fetchval(
                """INSERT INTO ticket_types
                   (panel_id, guild_id, label, emoji, description, welcome_message,
                    notification_channel_id,
                    field1_label, field1_required,
                    field2_label, field2_required,
                    field3_label, field3_required,
                    field4_label, field4_required,
                    field5_label, field5_required)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17) RETURNING id""",
                *params,
            )
            type_db_ids.append(type_id)

        panel_embed = discord.Embed(
            title=sess["panel_title"],
            description=sess["panel_description"],
            color=sess["panel_color"],
        )
        if sess["panel_footer"]:
            panel_embed.set_footer(text=sess["panel_footer"])
        if guild.icon:
            panel_embed.set_thumbnail(url=guild.icon.url)

        options = [
            discord.SelectOption(
                label=t["label"],
                value=str(type_db_ids[i]),
                emoji=t["emoji"],
                description=t.get("description") or None,
            )
            for i, t in enumerate(sess["types"])
        ]
        view = TicketOpenView(options)
        panel_msg = await panel_ch.send(embed=panel_embed, view=view)
        await db_manager.execute(
            "UPDATE ticket_panels SET message_id = $1 WHERE id = $2", panel_msg.id, panel_id
        )

        _sessions.pop(key, None)
        await interaction.followup.send(f"✅ Panneau publié dans {panel_ch.mention} !", ephemeral=True)

    # ── Ticket creation ───────────────────────────────────────────────────────

    async def create_ticket(self, interaction: discord.Interaction, type_row: dict, answers: dict):
        guild = interaction.guild
        panel = await db_manager.fetchrow(
            "SELECT * FROM ticket_panels WHERE id = $1", type_row["panel_id"]
        )
        if not panel:
            return await interaction.followup.send("❌ Configuration du panneau introuvable.", ephemeral=True)

        category = guild.get_channel(panel["category_id"])
        if not category:
            return await interaction.followup.send("❌ Catégorie introuvable.", ephemeral=True)

        existing = await db_manager.fetchrow(
            "SELECT channel_id FROM tickets WHERE guild_id = $1 AND user_id = $2 AND type_id = $3 AND status = 'open'",
            guild.id, interaction.user.id, type_row["id"],
        )
        if existing:
            ch = guild.get_channel(existing["channel_id"])
            if ch:
                return await interaction.followup.send(
                    f"❌ Vous avez déjà un ticket **{type_row['label']}** ouvert : {ch.mention}", ephemeral=True
                )

        ticket_num = (await db_manager.fetchval(
            "SELECT COUNT(*) FROM tickets WHERE guild_id = $1", guild.id
        ) or 0) + 1

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(
                read_messages=True, send_messages=True, manage_channels=True, manage_messages=True
            ),
        }
        for role in guild.roles:
            if role.permissions.administrator or role.permissions.manage_channels:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        subject = next(iter(answers.values()), type_row["label"]) if answers else type_row["label"]
        channel_name = f"ticket-{ticket_num:04d}-{_slug(subject)}"
        try:
            channel = await category.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                topic=f"Ticket de {interaction.user} | {type_row['label']} | {subject[:80]}",
            )
        except discord.Forbidden:
            return await interaction.followup.send(
                "❌ Je n'ai pas la permission de créer des salons dans cette catégorie.", ephemeral=True
            )
        except discord.HTTPException as exc:
            return await interaction.followup.send(
                f"❌ Impossible de créer le salon (erreur Discord : `{exc.status} {exc.text}`).", ephemeral=True
            )

        await db_manager.execute(
            "INSERT INTO tickets (guild_id, channel_id, user_id, ticket_number, panel_id, type_id, subject) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7)",
            guild.id, channel.id, interaction.user.id, ticket_num,
            type_row["panel_id"], type_row["id"], subject[:200],
        )

        welcome = discord.Embed(
            title=f"🎫 Ticket #{ticket_num:04d} — {type_row['label']}",
            description=type_row["welcome_message"],
            color=panel["color"],
            timestamp=discord.utils.utcnow(),
        )
        welcome.set_thumbnail(url=interaction.user.display_avatar.url)
        welcome.add_field(name="👤 Ouvert par", value=f"{interaction.user.mention}\n`{interaction.user}`", inline=True)
        welcome.add_field(name="🏷️ Type", value=type_row["label"], inline=True)
        if answers:
            welcome.add_field(name="​", value="─" * 30, inline=False)
            for field_label, value in answers.items():
                welcome.add_field(name=f"📝 {field_label}", value=value or "—", inline=False)
        welcome.set_footer(text=f"Ticket #{ticket_num:04d} • Fermez avec le bouton ci-dessous")
        await channel.send(content=interaction.user.mention, embed=welcome, view=TicketControlView())

        if type_row.get("notification_channel_id"):
            notif_ch = guild.get_channel(type_row["notification_channel_id"])
            if notif_ch:
                notif_embed = discord.Embed(
                    title=f"📋 Nouveau ticket — {type_row['label']}",
                    color=panel["color"],
                    timestamp=discord.utils.utcnow(),
                )
                notif_embed.add_field(name="Ouvert par", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
                notif_embed.add_field(name="Salon", value=channel.mention, inline=True)
                for field_label, value in answers.items():
                    notif_embed.add_field(name=field_label, value=value or "—", inline=False)
                notif_embed.set_footer(text=f"Ticket #{ticket_num:04d}")
                await notif_ch.send(embed=notif_embed)

        if panel.get("log_channel_id"):
            log_ch = guild.get_channel(panel["log_channel_id"])
            if log_ch:
                log_e = discord.Embed(title="🎫 Nouveau ticket ouvert", color=discord.Color.green(), timestamp=discord.utils.utcnow())
                log_e.add_field(name="Utilisateur", value=f"{interaction.user.mention} (`{interaction.user.id}`)")
                log_e.add_field(name="Ticket", value=channel.mention)
                log_e.add_field(name="Type", value=type_row["label"])
                await log_ch.send(embed=log_e)

        await interaction.followup.send(f"✅ Votre ticket a été créé : {channel.mention}", ephemeral=True)

    # ── Ticket close ──────────────────────────────────────────────────────────

    async def close_ticket(self, interaction: discord.Interaction):
        ticket = await db_manager.fetchrow(
            "SELECT id, user_id, subject, ticket_number, panel_id FROM tickets "
            "WHERE channel_id = $1 AND status = 'open'",
            interaction.channel.id,
        )
        if not ticket:
            return await interaction.response.send_message("❌ Ce salon n'est pas un ticket actif.", ephemeral=True)

        view = CloseConfirmView()
        await interaction.response.send_message("⚠️ Confirmer la fermeture de ce ticket ?", view=view, ephemeral=True)
        await view.wait()
        if not view.confirmed:
            return

        panel = None
        if ticket["panel_id"]:
            panel = await db_manager.fetchrow(
                "SELECT log_channel_id, transcript_channel_id FROM ticket_panels WHERE id = $1",
                ticket["panel_id"],
            )

        transcript_bytes = await self._html_transcript(interaction.channel, ticket["ticket_number"])
        filename = f"ticket-{ticket['ticket_number']:04d}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.html"

        if panel and panel.get("transcript_channel_id"):
            trans_ch = interaction.guild.get_channel(panel["transcript_channel_id"])
            if trans_ch:
                user = interaction.guild.get_member(ticket["user_id"])
                t_embed = discord.Embed(
                    title=f"📄 Transcript — {ticket['subject']}",
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow(),
                )
                t_embed.add_field(name="Salon", value=interaction.channel.name)
                t_embed.add_field(name="Ouvert par", value=user.mention if user else f"`{ticket['user_id']}`")
                t_embed.add_field(name="Fermé par", value=interaction.user.mention)
                t_embed.set_footer(text=f"Ticket #{ticket['ticket_number']:04d} • Limité aux 500 derniers messages")
                await trans_ch.send(embed=t_embed, file=discord.File(io.BytesIO(transcript_bytes), filename=filename))

        if panel and panel.get("log_channel_id"):
            log_ch = interaction.guild.get_channel(panel["log_channel_id"])
            if log_ch:
                log_e = discord.Embed(title="🔒 Ticket fermé", color=discord.Color.red(), timestamp=discord.utils.utcnow())
                log_e.add_field(name="Ticket", value=interaction.channel.name)
                log_e.add_field(name="Fermé par", value=interaction.user.mention)
                log_e.add_field(name="Sujet", value=ticket["subject"] or "—")
                await log_ch.send(embed=log_e)

        await db_manager.execute("UPDATE tickets SET status = 'closed' WHERE id = $1", ticket["id"])

        close_e = discord.Embed(title="🔒 Ticket fermé", description="Suppression dans 5 secondes.", color=discord.Color.red())
        await interaction.channel.send(embed=close_e)
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason="Ticket fermé")
        except discord.NotFound:
            pass

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
            messages_html += (
                f'<div class="mg"><div class="av">{initials}</div><div class="mc">'
                f'<div class="mh"><span class="un">{html.escape(str(msg.author))}</span>'
                f'{bot_tag}<span class="ts">{ts}</span></div>'
                f'{"<div class=\'mt\'>" + content + "</div>" if content else ""}'
                f'{embed_html}{attach_html}</div></div>'
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

    # ── Slash commands ────────────────────────────────────────────────────────

    ticket_group = app_commands.Group(name="ticket", description="Gestion du système de tickets")

    @ticket_group.command(name="setup", description="Lancer le wizard de configuration du panneau de tickets")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_setup(self, interaction: discord.Interaction):
        key = (interaction.guild.id, interaction.user.id)
        _new_sess(*key)
        embed = discord.Embed(
            title="⚙️ Wizard de configuration — Panneau de tickets",
            description=(
                "Ce wizard va vous guider à travers **4 étapes** :\n\n"
                "**1.** Sélection des salons et catégorie\n"
                "**2.** Apparence du panneau (titre, description, couleur)\n"
                "**3.** Nombre de types de tickets\n"
                "**4.** Configuration de chaque type (formulaire, canal de notification)\n\n"
                "Cliquez **Commencer** pour démarrer."
            ),
            color=0x5865F2,
        )
        await interaction.response.send_message(embed=embed, view=WizardStartView(key), ephemeral=True)

    @ticket_group.command(name="close", description="Fermer le ticket dans ce salon")
    async def ticket_close(self, interaction: discord.Interaction):
        await self.close_ticket(interaction)

    @ticket_group.command(name="add", description="Ajouter un membre à ce ticket")
    @app_commands.describe(member="Le membre à ajouter")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_add(self, interaction: discord.Interaction, member: discord.Member):
        if not await db_manager.fetchrow(
            "SELECT id FROM tickets WHERE channel_id = $1 AND status = 'open'", interaction.channel.id
        ):
            return await interaction.response.send_message("❌ Ce salon n'est pas un ticket actif.", ephemeral=True)
        await interaction.channel.set_permissions(member, read_messages=True, send_messages=True)
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
            "SELECT id FROM tickets WHERE channel_id = $1 AND status = 'open'", interaction.channel.id
        ):
            return await interaction.response.send_message("❌ Ce salon n'est pas un ticket actif.", ephemeral=True)
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
        view = TicketListView(tickets, interaction.guild)
        await interaction.response.send_message(embed=view.make_embed(), view=view, ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        send = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message
        if isinstance(error, app_commands.MissingPermissions):
            await send("❌ Permissions insuffisantes.", ephemeral=True)
        else:
            await send(f"❌ Erreur : {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
