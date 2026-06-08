# UI/UX Mobile Responsiveness & Discord Conversion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corriger 6 problèmes critiques de responsive mobile et améliorer la conversion des visiteurs vers le serveur Discord.

**Architecture:** Modifications purement frontend dans `web/src/`. Aucun changement backend. La variable `NEXT_PUBLIC_DISCORD_INVITE_URL` contrôle le lien Discord — si absente, les boutons "Rejoindre" sont masqués gracieusement.

**Tech Stack:** Next.js 14 App Router, TypeScript, Tailwind CSS, next-intl

---

## Fichiers modifiés

| Fichier | Rôle du changement |
|---|---|
| `.env.example` | Ajouter `NEXT_PUBLIC_DISCORD_INVITE_URL` |
| `web/src/app/[locale]/articles/SearchBar.tsx` | `w-64` → `w-full max-w-xs` |
| `web/src/app/[locale]/leaderboard/LeaderboardSearch.tsx` | `w-56` → `w-full max-w-xs` |
| `web/src/components/NotificationBell.tsx` | dropdown `w-80` → `w-80 max-w-[calc(100vw-2rem)]` |
| `web/src/app/globals.css` | Ajouter `height: 8px` sur `::-webkit-scrollbar` pour scroll horizontal |
| `web/src/app/[locale]/leaderboard/page.tsx` | Podium responsive : `grid-cols-1 sm:grid-cols-3` avec ordre réorganisé sur mobile |
| `web/src/app/[locale]/page.tsx` | Hero : badges fonctionnalités + bouton Discord + lien login discret |
| `web/src/app/[locale]/layout.tsx` | Footer : bannière CTA Discord avant le copyright |

---

## Task 1 : Variable d'environnement Discord invite

**Files:**
- Modify: `.env.example`

- [ ] **Ajouter la variable dans `.env.example`**

Dans `.env.example`, à la section `# ─── Website ───`, ajouter après `NEXT_PUBLIC_API_URL` :

```env
NEXT_PUBLIC_DISCORD_INVITE_URL=https://discord.gg/VOTRE_CODE_ICI
```

- [ ] **Commit**

```bash
git add .env.example
git commit -m "chore: add NEXT_PUBLIC_DISCORD_INVITE_URL to env example"
```

---

## Task 2 : Fix SearchBar articles — width responsive

**Files:**
- Modify: `web/src/app/[locale]/articles/SearchBar.tsx:39`

- [ ] **Modifier la classe width de l'input**

Ligne 39, remplacer `w-64` par `w-full max-w-xs` :

```tsx
className="pl-9 pr-4 py-2 bg-card border border-border rounded-lg text-sm w-full max-w-xs focus:outline-none focus:ring-2 focus:ring-primary"
```

- [ ] **Vérifier visuellement**

Lancer `cd web && npm run dev` puis ouvrir http://localhost:3000/fr/articles dans DevTools à 390px de large. L'input doit occuper toute la largeur disponible sans débordement.

- [ ] **Commit**

```bash
git add web/src/app/\[locale\]/articles/SearchBar.tsx
git commit -m "fix(ui): searchbar articles responsive width mobile"
```

---

## Task 3 : Fix LeaderboardSearch — width responsive

**Files:**
- Modify: `web/src/app/[locale]/leaderboard/LeaderboardSearch.tsx:38`

- [ ] **Modifier la classe width de l'input**

Ligne 38, remplacer `w-56` par `w-full max-w-xs` :

```tsx
className="pl-9 pr-4 py-2 text-sm bg-card border border-border rounded-lg w-full max-w-xs focus:outline-none focus:ring-2 focus:ring-primary"
```

- [ ] **Vérifier visuellement**

Ouvrir http://localhost:3000/fr/leaderboard à 390px. L'input de recherche doit s'étendre sans débordement.

- [ ] **Commit**

```bash
git add web/src/app/\[locale\]/leaderboard/LeaderboardSearch.tsx
git commit -m "fix(ui): leaderboard search responsive width mobile"
```

---

## Task 4 : Fix NotificationBell dropdown — max-width mobile

**Files:**
- Modify: `web/src/components/NotificationBell.tsx:35`

- [ ] **Contraindre la largeur du dropdown sur mobile**

Ligne 35, remplacer `w-80` par `w-80 max-w-[calc(100vw-2rem)]` :

```tsx
<div className="absolute right-0 mt-2 w-80 max-w-[calc(100vw-2rem)] glass-card shadow-xl z-50">
```

- [ ] **Vérifier visuellement**

Ouvrir n'importe quelle page à 390px, cliquer sur la cloche 🔔. Le dropdown ne doit pas sortir de l'écran à gauche.

- [ ] **Commit**

```bash
git add web/src/components/NotificationBell.tsx
git commit -m "fix(ui): notification dropdown constrained on mobile"
```

---

## Task 5 : Fix scrollbar horizontal (admin tabs)

**Files:**
- Modify: `web/src/app/globals.css`

Les admin tabs ont déjà `overflow-x-auto` et `whitespace-nowrap`. Le scrollbar horizontal n'est pas stylisé (height manquant). 

- [ ] **Ajouter height au scrollbar global**

Dans `web/src/app/globals.css`, section `/* ── Scrollbar ── */`, modifier :

```css
::-webkit-scrollbar { width: 8px; height: 8px; }
```

(Ajouter uniquement `height: 8px` sur la ligne existante.)

- [ ] **Vérifier visuellement**

Ouvrir http://localhost:3000/fr/admin à 390px (en tant qu'admin). Les tabs doivent être scrollables horizontalement avec un scrollbar visible.

- [ ] **Commit**

```bash
git add web/src/app/globals.css
git commit -m "fix(ui): horizontal scrollbar height for admin tabs mobile"
```

---

## Task 6 : Podium leaderboard responsive mobile

**Files:**
- Modify: `web/src/app/[locale]/leaderboard/page.tsx:183-218`

Le podium actuel force `grid-cols-3` sans breakpoint. Sur mobile, on veut : #1 en pleine largeur en haut, #2 et #3 côte à côte en dessous.

- [ ] **Remplacer le bloc podium entier (lignes 182–219)**

```tsx
{/* Top 3 Podium */}
{top3.length >= 3 && (
  <>
    {/* Mobile : #1 en haut pleine largeur, #2/#3 côte à côte */}
    <div className="sm:hidden mb-8 space-y-3">
      {/* #1 */}
      {(() => {
        const entry = top3[0]
        return (
          <div className="flex flex-col items-center text-center p-5 rounded-2xl border border-gold/40 bg-gold/5 medal-glow">
            <span className="text-3xl font-bold mb-2">🥇</span>
            <Avatar src={entry.discord_avatar} name={entry.username} size="lg" />
            <p className="font-semibold mt-2 text-base">{entry.username}</p>
            {tab === 'levels' && (
              <p className="font-bold mt-1 text-base text-primary">Niv.&nbsp;{entry.current_level}</p>
            )}
            {tab === 'streaks' && (
              <p className="font-bold mt-1 text-base text-primary">Record&nbsp;{entry.max_streak}j</p>
            )}
            <p className="text-xs text-muted-foreground mt-0.5 tabular-nums">{scoreLabel(tab, entry)}</p>
          </div>
        )
      })()}
      {/* #2 et #3 */}
      <div className="grid grid-cols-2 gap-3">
        {[top3[1], top3[2]].map((entry, i) => (
          <div key={entry.user_id}
               className="flex flex-col items-center text-center p-4 rounded-2xl border border-border bg-card">
            <span className="text-2xl font-bold mb-2">{i === 0 ? '🥈' : '🥉'}</span>
            <Avatar src={entry.discord_avatar} name={entry.username} size="md" />
            <p className="font-semibold truncate w-full mt-2 text-sm">{entry.username}</p>
            {tab === 'levels' && (
              <p className="font-bold mt-1 text-sm text-primary/80">Niv.&nbsp;{entry.current_level}</p>
            )}
            {tab === 'streaks' && (
              <p className="font-bold mt-1 text-sm text-primary/80">Record&nbsp;{entry.max_streak}j</p>
            )}
            <p className="text-xs text-muted-foreground mt-0.5 tabular-nums">{scoreLabel(tab, entry)}</p>
          </div>
        ))}
      </div>
    </div>

    {/* Desktop sm+ : 3 colonnes avec décalage (comportement actuel) */}
    <div className="hidden sm:grid grid-cols-3 gap-3 mb-8">
      {[top3[1], top3[0], top3[2]].map((entry, i) => {
        const actualRank = [2, 1, 3][i]
        const isCenter = i === 1
        return (
          <div key={entry.user_id}
               className={`flex flex-col items-center text-center p-4 rounded-2xl border transition-all ${
                 isCenter
                   ? 'border-gold/40 bg-gold/5 -mt-4 pb-6 medal-glow'
                   : 'border-border bg-card mt-2'
               }`}
          >
            <span className={`font-bold mb-2 ${isCenter ? 'text-3xl' : 'text-2xl'}`}>
              {medal(actualRank)}
            </span>
            <Avatar src={entry.discord_avatar} name={entry.username} size={isCenter ? 'lg' : 'md'} />
            <p className={`font-semibold truncate w-full mt-2 ${isCenter ? 'text-base' : 'text-sm'}`}>
              {entry.username}
            </p>
            {tab === 'levels' && (
              <p className={`font-bold mt-1 ${isCenter ? 'text-base text-primary' : 'text-sm text-primary/80'}`}>
                Niv.&nbsp;{entry.current_level}
              </p>
            )}
            {tab === 'streaks' && (
              <p className={`font-bold mt-1 ${isCenter ? 'text-base text-primary' : 'text-sm text-primary/80'}`}>
                Record&nbsp;{entry.max_streak}j
              </p>
            )}
            <p className="text-xs text-muted-foreground mt-0.5 tabular-nums">
              {scoreLabel(tab, entry)}
            </p>
          </div>
        )
      })}
    </div>
  </>
)}
```

- [ ] **Vérifier visuellement**

Ouvrir http://localhost:3000/fr/leaderboard à 390px. Le #1 doit être en grand en haut, #2 et #3 côte à côte en dessous. À 640px+ le podium classique 3 colonnes réapparaît.

- [ ] **Commit**

```bash
git add web/src/app/\[locale\]/leaderboard/page.tsx
git commit -m "fix(ui): leaderboard podium responsive mobile layout"
```

---

## Task 7 : Hero Section — badges + CTA Discord

**Files:**
- Modify: `web/src/app/[locale]/page.tsx:28-46`

Actuellement : un seul bouton `<LoginButton>`. Après : badges + bouton Discord (primaire) + lien login (discret). Le bouton Discord lit `NEXT_PUBLIC_DISCORD_INVITE_URL` — si vide, le bouton n'est pas rendu.

- [ ] **Remplacer le bloc hero (lignes 28–47) par le nouveau**

```tsx
<section className="text-center mb-24 relative">
  <div className="absolute inset-0 -z-10 overflow-hidden">
    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] bg-primary/5 rounded-full blur-[120px]" />
  </div>

  {/* Badges */}
  {!isLoggedIn && (
    <div className="flex flex-wrap justify-center gap-2 mb-6 animate-fade-up">
      {(['🎮 Serveur gaming', '🏆 Classements live', '🔥 Quêtes hebdo'] as const).map(label => (
        <span key={label} className="bg-card border border-border text-muted-foreground text-xs px-3 py-1.5 rounded-full">
          {label}
        </span>
      ))}
    </div>
  )}

  <h1 className="text-5xl sm:text-6xl font-extrabold mb-6 gradient-hero glow-text animate-fade-up tracking-tight">
    {t('hero_title')}
  </h1>
  <p className="text-lg text-muted-foreground mb-10 max-w-2xl mx-auto animate-fade-up" style={{ animationDelay: '0.1s' }}>
    {t('hero_subtitle')}
  </p>

  {!isLoggedIn && (
    <div className="flex flex-col items-center gap-3 animate-fade-up" style={{ animationDelay: '0.2s' }}>
      {process.env.NEXT_PUBLIC_DISCORD_INVITE_URL && (
        <a
          href={process.env.NEXT_PUBLIC_DISCORD_INVITE_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2.5 bg-discord text-white font-bold px-8 py-3.5 rounded-xl hover:opacity-90 transition-all text-lg shadow-lg shadow-discord/20 hover:shadow-xl hover:shadow-discord/30"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057.102 18.08.116 18.1.133 18.113a19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03z"/>
          </svg>
          {t('join_discord')}
        </a>
      )}
      <LoginButton
        callbackURL={`/${locale}`}
        label={t('login_with_discord')}
        className="text-sm text-muted-foreground hover:text-foreground transition-colors"
      />
    </div>
  )}
</section>
```

- [ ] **Ajouter la clé de traduction `join_discord`**

Dans `web/messages/fr.json`, section `"home"`, ajouter :
```json
"join_discord": "Rejoindre SaucisseLand"
```

Dans `web/messages/en.json`, section `"home"`, ajouter :
```json
"join_discord": "Join SaucisseLand"
```

- [ ] **Vérifier visuellement (non connecté)**

Ouvrir http://localhost:3000/fr en navigation privée. Les badges doivent apparaître, le bouton Discord en grand, le lien "Se connecter" en petit dessous. Si `NEXT_PUBLIC_DISCORD_INVITE_URL` n'est pas défini dans `.env.local`, seul le lien login apparaît — c'est attendu.

- [ ] **Commit**

```bash
git add web/src/app/\[locale\]/page.tsx web/messages/fr.json web/messages/en.json
git commit -m "feat(ui): hero section badges + discord CTA + discrete login link"
```

---

## Task 8 : Footer — bannière Discord CTA

**Files:**
- Modify: `web/src/app/[locale]/layout.tsx:55-60`

- [ ] **Remplacer le footer entier**

```tsx
<footer className="border-t border-border/40 mt-16 py-8">
  <div className="container mx-auto px-4">
    {process.env.NEXT_PUBLIC_DISCORD_INVITE_URL && (
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-primary/5 border border-primary/20 rounded-xl px-6 py-4 mb-6">
        <div>
          <p className="font-semibold text-sm text-foreground">🎮 Rejoins SaucisseLand</p>
          <p className="text-xs text-muted-foreground mt-0.5">Une communauté active · XP · Quêtes · Classements</p>
        </div>
        <a
          href={process.env.NEXT_PUBLIC_DISCORD_INVITE_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-shrink-0 inline-flex items-center gap-2 bg-discord text-white font-semibold text-sm px-5 py-2.5 rounded-lg hover:opacity-90 transition-opacity"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057.102 18.08.116 18.1.133 18.113a19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03z"/>
          </svg>
          Rejoindre
        </a>
      </div>
    )}
    <div className="flex flex-col sm:flex-row items-center justify-between gap-2 text-sm text-muted-foreground">
      <span>© {new Date().getFullYear()} Hermes · SaucisseLand</span>
      <span className="text-xs opacity-60">Développé avec ❤️ pour la communauté</span>
    </div>
  </div>
</footer>
```

- [ ] **Vérifier visuellement**

Scroller en bas de n'importe quelle page. La bannière Discord doit apparaître si `NEXT_PUBLIC_DISCORD_INVITE_URL` est défini. Sur mobile (390px) les éléments de la bannière doivent s'empiler verticalement (`flex-col sm:flex-row`).

- [ ] **Commit**

```bash
git add web/src/app/\[locale\]/layout.tsx
git commit -m "feat(ui): footer discord CTA banner"
```

---

## Vérification finale

- [ ] Tester toutes les pages à 390px (iPhone) dans DevTools : aucun scroll horizontal parasite
- [ ] Tester le podium leaderboard à 390px et à 640px (transition correcte)
- [ ] Tester le footer avec et sans `NEXT_PUBLIC_DISCORD_INVITE_URL` dans `.env.local`
- [ ] Vérifier que le hero affiche les badges uniquement pour les non-connectés
- [ ] Vérifier la navbar hamburger sur mobile (déjà fonctionnelle, juste confirmer)
