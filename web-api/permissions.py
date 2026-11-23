"""Catalogue fermé des droits d'accès au site (clé → libellé).

Doit rester identique, clés et ordre, à web/src/lib/permissions.ts
(vérifié par tests/test_permissions_catalog.py).
"""

PERMISSIONS: dict[str, str] = {
    "admin.view": "Voir l'administration",
    "moderation.view": "Voir la modération et le journal",
    "moderation.act": "Sanctionner (avertir, exclure, bannir)",
    "moderation.content": "Lire le contenu des messages du journal",
    "tickets.manage": "Gérer les tickets",
    "articles.write": "Écrire des articles",
    "articles.publish": "Publier et gérer les étiquettes",
    "gallery.manage": "Gérer la galerie",
    "content.edit": "Modifier les contenus (pages, grades, état-major)",
    "quests.manage": "Gérer les quêtes",
    "games.manage": "Gérer les jeux",
    "roles.manage": "Gérer les rôles",
    "members.roles": "Donner ou retirer des rôles",
    "channels.manage": "Gérer les salons",
    "permissions.manage": "Gérer les accès",
    "settings.manage": "Modifier les réglages et les commandes",
    "analytics.view": "Voir l'analytique",
}
