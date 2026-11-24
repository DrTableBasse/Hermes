"""Catalogue des permissions Discord et règle anti-escalade, côté web-api.

Copie de ``bot/utils/permission_catalog.py`` (web-api n'embarque pas discord.py) : mêmes
familles, clés, libellés et bits, même règle ``escalation_error`` — vérifié par
``tests/test_permissions_admin.py``. Le contrôle est fait ici (403 clair avant d'appeler le
bot) et refait par le bot (défense en profondeur) : les deux doivent rester identiques.
"""
from collections.abc import Iterable

FAMILIES: list[tuple[str, list[tuple[str, str, int]]]] = [
    ("Général", [
        ("view_channel", "Voir les salons", 1 << 10),
        ("manage_channels", "Gérer les salons", 1 << 4),
        ("manage_roles", "Gérer les rôles", 1 << 28),
        ("create_expressions", "Créer des expressions", 1 << 43),
        ("manage_expressions", "Gérer les expressions", 1 << 30),
        ("view_audit_log", "Voir les logs du serveur", 1 << 7),
        ("view_guild_insights", "Voir les analyses du serveur", 1 << 19),
        ("view_creator_monetization_analytics", "Voir les analyses de monétisation", 1 << 41),
        ("manage_webhooks", "Gérer les webhooks", 1 << 29),
        ("manage_guild", "Gérer le serveur", 1 << 5),
        ("create_instant_invite", "Créer une invitation", 1 << 0),
        ("change_nickname", "Changer de pseudo", 1 << 26),
        ("manage_nicknames", "Gérer les pseudos", 1 << 27),
    ]),
    ("Membres", [
        ("kick_members", "Expulser des membres", 1 << 1),
        ("ban_members", "Bannir des membres", 1 << 2),
        ("moderate_members", "Exclure temporairement des membres", 1 << 40),
    ]),
    ("Messages", [
        ("send_messages", "Envoyer des messages", 1 << 11),
        ("send_messages_in_threads", "Envoyer des messages dans les fils", 1 << 38),
        ("create_public_threads", "Créer des fils publics", 1 << 35),
        ("create_private_threads", "Créer des fils privés", 1 << 36),
        ("embed_links", "Intégrer des liens", 1 << 14),
        ("attach_files", "Joindre des fichiers", 1 << 15),
        ("add_reactions", "Ajouter des réactions", 1 << 6),
        ("use_external_emojis", "Utiliser des émojis externes", 1 << 18),
        ("use_external_stickers", "Utiliser des autocollants externes", 1 << 37),
        ("mention_everyone", "Mentionner @everyone, @here et tous les rôles", 1 << 17),
        ("manage_messages", "Gérer les messages", 1 << 13),
        ("pin_messages", "Épingler des messages", 1 << 51),
        ("bypass_slowmode", "Ignorer le mode lent", 1 << 52),
        ("manage_threads", "Gérer les fils", 1 << 34),
        ("read_message_history", "Voir les anciens messages", 1 << 16),
        ("send_tts_messages", "Envoyer des messages de synthèse vocale", 1 << 12),
        ("send_voice_messages", "Envoyer des messages vocaux", 1 << 46),
        ("send_polls", "Créer des sondages", 1 << 49),
        ("use_application_commands", "Utiliser les commandes d'application", 1 << 31),
        ("use_external_apps", "Utiliser des applications externes", 1 << 50),
    ]),
    ("Vocal", [
        ("connect", "Se connecter", 1 << 20),
        ("speak", "Parler", 1 << 21),
        ("stream", "Vidéo", 1 << 9),
        ("use_embedded_activities", "Utiliser les activités", 1 << 39),
        ("use_soundboard", "Utiliser la table de mixage", 1 << 42),
        ("use_external_sounds", "Utiliser des sons externes", 1 << 45),
        ("use_voice_activation", "Utiliser la détection de la voix", 1 << 25),
        ("priority_speaker", "Voix prioritaire", 1 << 8),
        ("mute_members", "Rendre muet des membres", 1 << 22),
        ("deafen_members", "Mettre en sourdine des membres", 1 << 23),
        ("move_members", "Déplacer des membres", 1 << 24),
        ("set_voice_channel_status", "Définir le statut du salon vocal", 1 << 48),
        ("request_to_speak", "Demander à parler", 1 << 32),
    ]),
    ("Événements", [
        ("create_events", "Créer des événements", 1 << 44),
        ("manage_events", "Gérer les événements", 1 << 33),
    ]),
    ("Avancé", [
        ("administrator", "Administrateur", 1 << 3),
    ]),
]

LABELS: dict[str, str] = {flag: label for _, items in FAMILIES for flag, label, _ in items}
BITS: dict[str, int] = {flag: bit for _, items in FAMILIES for flag, _, bit in items}
CATALOG_MASK = sum(BITS.values())
ADMINISTRATOR = BITS["administrator"]


def flags_to_value(flags: Iterable[str]) -> int:
    """Masque de bits des drapeaux donnés ; un drapeau inconnu lève ``ValueError``."""
    value = 0
    for flag in flags:
        if flag not in BITS:
            raise ValueError(f"Permission inconnue : {flag}")
        value |= BITS[flag]
    return value


def value_to_flags(value: int) -> set[str]:
    """Drapeaux du catalogue présents dans le masque (bits hors catalogue ignorés)."""
    return {flag for flag, bit in BITS.items() if value & bit}


def escalation_error(actor_perms: int, is_owner: bool, before: int, after: int) -> str | None:
    """Message d'erreur si l'acteur n'a pas le droit de passer de ``before`` à ``after``.

    Le propriétaire peut tout. Sinon : activer « Administrateur » lui est réservé, et
    chaque permission modifiée (activée ou retirée) doit être détenue par l'acteur
    (un administrateur les détient toutes).
    """
    if is_owner:
        return None
    if after & ADMINISTRATOR and not before & ADMINISTRATOR:
        return "Seul le propriétaire du serveur peut accorder la permission « Administrateur »."
    if actor_perms & ADMINISTRATOR:
        return None
    for flag in sorted(value_to_flags((before ^ after) & ~actor_perms)):
        verbe = "accorder" if after & BITS[flag] else "retirer"
        return f"Vous ne pouvez pas {verbe} la permission « {LABELS[flag]} » : vous ne la possédez pas."
    return None
