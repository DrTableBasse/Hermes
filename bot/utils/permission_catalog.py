"""Catalogue des permissions Discord (familles, libellés français) et règle anti-escalade.

Fonctions pures (ni Discord réel ni base). Les clés sont les noms canoniques de
discord.py ; les alias (``read_messages``…) partagent le même bit et ne figurent pas ici.
"""
from collections.abc import Iterable

import discord

FAMILIES: list[tuple[str, list[tuple[str, str]]]] = [
    ("Général", [
        ("view_channel", "Voir les salons"),
        ("manage_channels", "Gérer les salons"),
        ("manage_roles", "Gérer les rôles"),
        ("create_expressions", "Créer des expressions"),
        ("manage_expressions", "Gérer les expressions"),
        ("view_audit_log", "Voir les logs du serveur"),
        ("view_guild_insights", "Voir les analyses du serveur"),
        ("view_creator_monetization_analytics", "Voir les analyses de monétisation"),
        ("manage_webhooks", "Gérer les webhooks"),
        ("manage_guild", "Gérer le serveur"),
        ("create_instant_invite", "Créer une invitation"),
        ("change_nickname", "Changer de pseudo"),
        ("manage_nicknames", "Gérer les pseudos"),
    ]),
    ("Membres", [
        ("kick_members", "Expulser des membres"),
        ("ban_members", "Bannir des membres"),
        ("moderate_members", "Exclure temporairement des membres"),
    ]),
    ("Messages", [
        ("send_messages", "Envoyer des messages"),
        ("send_messages_in_threads", "Envoyer des messages dans les fils"),
        ("create_public_threads", "Créer des fils publics"),
        ("create_private_threads", "Créer des fils privés"),
        ("embed_links", "Intégrer des liens"),
        ("attach_files", "Joindre des fichiers"),
        ("add_reactions", "Ajouter des réactions"),
        ("use_external_emojis", "Utiliser des émojis externes"),
        ("use_external_stickers", "Utiliser des autocollants externes"),
        ("mention_everyone", "Mentionner @everyone, @here et tous les rôles"),
        ("manage_messages", "Gérer les messages"),
        ("pin_messages", "Épingler des messages"),
        ("bypass_slowmode", "Ignorer le mode lent"),
        ("manage_threads", "Gérer les fils"),
        ("read_message_history", "Voir les anciens messages"),
        ("send_tts_messages", "Envoyer des messages de synthèse vocale"),
        ("send_voice_messages", "Envoyer des messages vocaux"),
        ("send_polls", "Créer des sondages"),
        ("use_application_commands", "Utiliser les commandes d'application"),
        ("use_external_apps", "Utiliser des applications externes"),
    ]),
    ("Vocal", [
        ("connect", "Se connecter"),
        ("speak", "Parler"),
        ("stream", "Vidéo"),
        ("use_embedded_activities", "Utiliser les activités"),
        ("use_soundboard", "Utiliser la table de mixage"),
        ("use_external_sounds", "Utiliser des sons externes"),
        ("use_voice_activation", "Utiliser la détection de la voix"),
        ("priority_speaker", "Voix prioritaire"),
        ("mute_members", "Rendre muet des membres"),
        ("deafen_members", "Mettre en sourdine des membres"),
        ("move_members", "Déplacer des membres"),
        ("set_voice_channel_status", "Définir le statut du salon vocal"),
        ("request_to_speak", "Demander à parler"),
    ]),
    ("Événements", [
        ("create_events", "Créer des événements"),
        ("manage_events", "Gérer les événements"),
    ]),
    ("Avancé", [
        ("administrator", "Administrateur"),
    ]),
]

_LABELS = {flag: label for _, items in FAMILIES for flag, label in items}
_BITS = {flag: discord.Permissions.VALID_FLAGS[flag] for flag in _LABELS}
_ADMINISTRATOR = _BITS["administrator"]


def flags_to_value(flags: Iterable[str]) -> int:
    """Masque de bits des drapeaux donnés ; un drapeau inconnu lève ``ValueError``."""
    value = 0
    for flag in flags:
        if flag not in _BITS:
            raise ValueError(f"Permission inconnue : {flag}")
        value |= _BITS[flag]
    return value


def value_to_flags(value: int) -> set[str]:
    """Drapeaux du catalogue présents dans le masque (bits hors catalogue ignorés)."""
    return {flag for flag, bit in _BITS.items() if value & bit}


def escalation_error(actor_perms: int, is_owner: bool, before: int, after: int) -> str | None:
    """Message d'erreur si l'acteur n'a pas le droit de passer de ``before`` à ``after``.

    Le propriétaire peut tout. Sinon : activer « Administrateur » lui est réservé, et
    chaque permission modifiée (activée ou retirée) doit être détenue par l'acteur
    (un administrateur les détient toutes).
    """
    if is_owner:
        return None
    if after & _ADMINISTRATOR and not before & _ADMINISTRATOR:
        return "Seul le propriétaire du serveur peut accorder la permission « Administrateur »."
    if actor_perms & _ADMINISTRATOR:
        return None
    for flag in sorted(value_to_flags((before ^ after) & ~actor_perms)):
        verbe = "accorder" if after & _BITS[flag] else "retirer"
        return f"Tu ne peux pas {verbe} la permission « {_LABELS[flag]} » : tu ne la possèdes pas."
    return None
