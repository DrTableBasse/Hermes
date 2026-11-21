"""Transcriptions HTML des tickets : rendu d'un message (module pur, sans discord).

Tout texte venu de Discord (pseudo, contenu, embed, nom et URL de pièce jointe) est
échappé ici. La transcription est servie sur l'origine du site : un caractère non
échappé y serait une XSS stockée, visée en priorité vers les admins qui la lisent.
"""
import html
from typing import Iterable, Optional, Tuple

Embed = Tuple[Optional[str], Optional[str], Iterable[Tuple[str, str]]]  # titre, description, champs


def _e(text) -> str:
    return html.escape(str(text), quote=True)


def message_block(
    author: str,
    display_name: str,
    is_bot: bool,
    timestamp: str,
    content: str,
    embeds: Iterable[Embed] = (),
    attachments: Iterable[Tuple[str, str]] = (),
) -> str:
    """``attachments`` : couples ``(url, nom)`` ; une URL hors ``http(s)`` n'est pas un lien."""
    embed_html = ""
    for title, description, fields in embeds:
        embed_html += '<div class="emb">'
        if title:
            embed_html += f"<b>{_e(title)}</b><br>"
        if description:
            embed_html += f"<span>{_e(description)}</span>"
        for name, value in fields:
            embed_html += f"<div><b>{_e(name)}</b>: {_e(value)}</div>"
        embed_html += "</div>"
    attach_html = ""
    for url, filename in attachments:
        if str(url).lower().startswith(("https://", "http://")):
            attach_html += f'<div class="att">📎 <a href="{_e(url)}">{_e(filename)}</a></div>'
        else:
            attach_html += f'<div class="att">📎 {_e(filename)}</div>'
    bot_tag = '<span class="bt">BOT</span>' if is_bot else ""
    content_div = f'<div class="mt">{_e(content)}</div>' if content else ""
    return (
        f'<div class="mg"><div class="av">{_e(display_name[:2].upper())}</div><div class="mc">'
        f'<div class="mh"><span class="un">{_e(author)}</span>'
        f'{bot_tag}<span class="ts">{_e(timestamp)}</span></div>'
        f"{content_div}{embed_html}{attach_html}</div></div>"
    )
