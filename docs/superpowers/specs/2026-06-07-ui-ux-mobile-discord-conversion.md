# UI/UX — Mobile responsiveness & Discord conversion

**Date:** 2026-06-07  
**Statut:** Approuvé  
**Scope:** Frontend Next.js uniquement (`web/`)

---

## Objectifs

1. Corriger 6 problèmes critiques de responsive mobile
2. Améliorer la conversion des visiteurs vers le serveur Discord
3. Rendre le site pleinement utilisable sur téléphone

---

## Décisions de design

### 1. Hero Section (`web/src/app/[locale]/page.tsx`)

**Avant :** Un bouton "Se connecter avec Discord" centré.

**Après :**
- 3 badges fonctionnalités au-dessus du titre : `🎮 Serveur gaming` · `🏆 Classements live` · `🔥 Quêtes hebdo`
- Un seul grand bouton primaire : **"Rejoindre SaucisseLand"** (couleur discord `#5865F2`, font-weight 700)
- Un lien secondaire discret en dessous : `Déjà membre ? Se connecter →` (texte, pas un bouton)
- Comportement : le bouton "Rejoindre" pointe vers l'invite Discord (URL à configurer via env `NEXT_PUBLIC_DISCORD_INVITE_URL`). Le lien "Se connecter" déclenche le flow OAuth2 BetterAuth existant.
- Affiché seulement si l'utilisateur n'est **pas** connecté (condition `!isLoggedIn` déjà en place)

### 2. Footer (`web/src/app/[locale]/layout.tsx`)

**Avant :** `<footer>© 2026 Hermes</footer>` minimaliste sans lien Discord.

**Après :** Bannière CTA avant le copyright :
```
┌─────────────────────────────────────────────────────┐
│  🎮 Rejoins SaucisseLand                            │
│  Une communauté active · XP · Quêtes · Classements  │  [Rejoindre]
└─────────────────────────────────────────────────────┘
             © 2026 Hermes · SaucisseLand
```
- Background `bg-primary/5`, bordure `border border-primary/20`, `rounded-xl`
- Bouton Discord identique au hero (même couleur, même style)
- URL : `NEXT_PUBLIC_DISCORD_INVITE_URL`
- Le footer s'affiche sur **toutes** les pages (il est dans le layout)

### 3. Podium Leaderboard mobile (`web/src/app/[locale]/leaderboard/page.tsx`)

**Avant :** `grid grid-cols-3` sans breakpoint — illisible sur <640px.

**Après :**
- Mobile (`< sm`) : `#1` en pleine largeur centré en haut (grand avatar, nom complet), `#2` et `#3` en `grid-cols-2` en dessous
- Desktop (`sm:`) : grille 3 colonnes avec décalage vertical habituel (comportement actuel)
- Implémentation : conditionner le layout avec des classes Tailwind `grid grid-cols-1 sm:grid-cols-3`

---

## Fixes techniques (responsive CSS)

Aucun changement fonctionnel — uniquement des corrections de classes Tailwind.

### 4. SearchBar articles (`web/src/app/[locale]/articles/SearchBar.tsx:39`)
- `w-64` → `w-full max-w-xs`
- Sur mobile l'input prend toute la largeur disponible, plafonné à 256px sur grands écrans

### 5. LeaderboardSearch (`web/src/app/[locale]/leaderboard/LeaderboardSearch.tsx:38`)
- `w-56` → `w-full max-w-xs`
- Même logique que SearchBar

### 6. NotificationBell dropdown (`web/src/components/NotificationBell.tsx:35`)
- `w-80` → `w-80 max-w-[calc(100vw-2rem)]`
- Empêche le dropdown de sortir de l'écran sur mobile (reste dans les marges)

### 7. Admin tabs (`web/src/app/[locale]/admin/AdminPanel.tsx:373`)
- Ajouter `overflow-x-auto` déjà en place mais compléter avec `scrollbar-thin scrollbar-thumb-border scrollbar-track-transparent`
- Ajouter `flex-shrink-0` sur chaque tab pour éviter la compression
- Résultat : scroll horizontal propre sur mobile, tabs complètes non tronquées

---

## Variable d'environnement requise

```env
# À ajouter dans .env et .env.example
NEXT_PUBLIC_DISCORD_INVITE_URL=https://discord.gg/XXXXXXX
```

Si non définie, les boutons "Rejoindre" sont masqués (fallback gracieux).

---

## Fichiers modifiés

| Fichier | Changement |
|---|---|
| `web/src/app/[locale]/page.tsx` | Hero : badges + double CTA |
| `web/src/app/[locale]/layout.tsx` | Footer : bannière Discord |
| `web/src/app/[locale]/leaderboard/page.tsx` | Podium : responsive mobile |
| `web/src/app/[locale]/articles/SearchBar.tsx` | `w-64` → `w-full max-w-xs` |
| `web/src/app/[locale]/leaderboard/LeaderboardSearch.tsx` | `w-56` → `w-full max-w-xs` |
| `web/src/components/NotificationBell.tsx` | dropdown max-width mobile |
| `web/src/app/[locale]/admin/AdminPanel.tsx` | tabs scroll horizontal |
| `.env.example` | Ajouter `NEXT_PUBLIC_DISCORD_INVITE_URL` |

---

## Critères de succès

- [ ] Sur un viewport 390px (iPhone 14), aucun scroll horizontal parasite
- [ ] Le podium leaderboard est lisible avec les noms complets visibles
- [ ] Les boutons "Rejoindre SaucisseLand" pointent vers le bon lien Discord
- [ ] Le footer s'affiche sur toutes les pages
- [ ] L'admin panel est utilisable (scroll horizontal sur les tabs)
- [ ] Les searchbars s'étendent correctement en mobile
