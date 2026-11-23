// Catalogue fermé des droits d'accès au site (clé → libellé).
// Doit rester identique, clés et ordre, à web-api/permissions.py
// (vérifié par web-api/tests/test_permissions_catalog.py).

export const PERMISSIONS = {
  'admin.view': "Voir l'administration",
  'moderation.view': 'Voir la modération et le journal',
  'moderation.act': 'Sanctionner (avertir, exclure, bannir)',
  'moderation.content': 'Lire le contenu des messages du journal',
  'tickets.manage': 'Gérer les tickets',
  'articles.write': 'Écrire des articles',
  'articles.publish': 'Publier et gérer les étiquettes',
  'gallery.manage': 'Gérer la galerie',
  'content.edit': 'Modifier les contenus (pages, grades, état-major)',
  'quests.manage': 'Gérer les quêtes',
  'games.manage': 'Gérer les jeux',
  'roles.manage': 'Gérer les rôles',
  'members.roles': 'Donner ou retirer des rôles',
  'channels.manage': 'Gérer les salons',
  'permissions.manage': 'Gérer les accès',
  'settings.manage': 'Modifier les réglages et les commandes',
  'analytics.view': "Voir l'analytique",
} as const satisfies Record<string, string>

export type SitePermission = keyof typeof PERMISSIONS

const ALL_PERMISSIONS = Object.keys(PERMISSIONS).sort() as SitePermission[]

function isSitePermission(key: string): key is SitePermission {
  return Object.hasOwn(PERMISSIONS, key)
}

/**
 * Droits d'un membre. Propriétaire du serveur ou rôle admin : tous les droits (calculés, jamais
 * stockés dans `site_permissions`). Sinon, union des droits accordés à ses rôles Discord ; un
 * droit inconnu du catalogue ou accordé à un rôle qu'il n'a pas (rôle disparu) est ignoré.
 * Résultat trié, sans doublon.
 */
export function computePermissions(input: {
  isOwner: boolean
  isAdminRole: boolean
  roleIds: string[]
  grants: Array<{ roleId: string; permission: string }>
}): SitePermission[] {
  if (input.isOwner || input.isAdminRole) return [...ALL_PERMISSIONS]
  const roles = new Set(input.roleIds)
  const granted = new Set<SitePermission>()
  for (const { roleId, permission } of input.grants) {
    if (roles.has(roleId) && isSitePermission(permission)) granted.add(permission)
  }
  return [...granted].sort()
}
