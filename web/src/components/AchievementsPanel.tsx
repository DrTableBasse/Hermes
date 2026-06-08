'use client'

import { useState, useMemo } from 'react'
import type { AchievementWithStatus } from '@/lib/api'

const ITEMS_PER_PAGE = 12

const CATEGORY_MAP: Record<string, string> = {
  messages:                'Messages',
  voice_hours:             'Vocal',
  voice_night_minutes:     'Vocal',
  voice_morning_minutes:   'Vocal',
  longest_session_minutes: 'Vocal',
  unique_voice_channels:   'Vocal',
  total_voice_sessions:    'Vocal',
  consecutive_voice_days:  'Vocal',
  level:                   'XP & Niveaux',
  xp_total:                'XP & Niveaux',
  bump_count:              'Bumps',
  invites:                 'Invitations',
  warn_free:               'Modération',
  streaks:                 'Streaks',
}

function getCategory(conditionType: string): string {
  return CATEGORY_MAP[conditionType] ?? 'Divers'
}

function tierBadge(points: number): { label: string; icon: string; cls: string } {
  if (points >= 100) return { label: 'Légendaire', icon: '⭐', cls: 'bg-yellow-500/20 text-yellow-300 ring-yellow-500/40' }
  if (points >= 50)  return { label: 'Épique',     icon: '💎', cls: 'bg-indigo-500/20 text-indigo-300 ring-indigo-500/40' }
  if (points >= 25)  return { label: 'Rare',       icon: '🔶', cls: 'bg-orange-500/20 text-orange-300 ring-orange-500/40' }
  return               { label: 'Commun',     icon: '⚪', cls: 'bg-neutral-500/20 text-neutral-300 ring-neutral-500/40' }
}

interface Props {
  achievements: AchievementWithStatus[]
}

export default function AchievementsPanel({ achievements }: Props) {
  const [category, setCategory] = useState('Tous')
  const [page, setPage]         = useState(1)

  const categories = useMemo(() => {
    const cats = new Set(achievements.map(a => getCategory(a.condition_type)))
    return ['Tous', ...Array.from(cats).sort()]
  }, [achievements])

  const filtered = useMemo(
    () =>
      category === 'Tous'
        ? achievements
        : achievements.filter(a => getCategory(a.condition_type) === category),
    [achievements, category]
  )

  const totalPages = Math.max(1, Math.ceil(filtered.length / ITEMS_PER_PAGE))
  const currentPage = Math.min(page, totalPages)
  const pageItems = filtered.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE)

  const unlockedCount = achievements.filter(a => a.unlocked).length

  const handleCategory = (cat: string) => {
    setCategory(cat)
    setPage(1)
  }

  return (
    <div>
      {/* Summary */}
      <p className="text-sm text-muted-foreground mb-4">
        {unlockedCount} / {achievements.length} débloqués
      </p>

      {/* Category filter */}
      <div className="flex flex-wrap gap-2 mb-6">
        {categories.map(cat => (
          <button
            key={cat}
            onClick={() => handleCategory(cat)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              category === cat
                ? 'bg-primary text-primary-foreground'
                : 'bg-accent text-muted-foreground hover:text-foreground'
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Grid */}
      {pageItems.length === 0 ? (
        <div className="glass-card p-8 text-center">
          <p className="text-muted-foreground">Aucun achievement dans cette catégorie.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
          {pageItems.map(a => {
            const tier = tierBadge(a.points)
            return (
              <div
                key={a.id}
                className={`glass-card flex items-start gap-3 p-4 transition-all duration-200 ${
                  a.unlocked
                    ? 'glass-card-hover'
                    : 'opacity-50 grayscale cursor-default'
                }`}
              >
                <span className="text-3xl relative shrink-0">
                  {a.icon}
                  {!a.unlocked && (
                    <span className="absolute -bottom-1 -right-1 text-sm">🔒</span>
                  )}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">{a.name}</p>
                  <p className="text-sm text-muted-foreground">{a.description}</p>
                  <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                    <span className={`text-xs px-2 py-0.5 rounded-full ring-1 font-medium ${tier.cls}`}>
                      {tier.icon} {tier.label}
                    </span>
                    <span className="text-xs text-primary font-medium">+{a.points} pts</span>
                    {a.unlocked && a.unlocked_at && (
                      <span className="text-xs text-muted-foreground">
                        {new Date(a.unlocked_at).toLocaleDateString('fr-FR')}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            className="px-3 py-1.5 rounded-lg text-sm bg-accent hover:bg-accent/80 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            ←
          </button>
          <span className="text-sm text-muted-foreground">
            {currentPage} / {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
            className="px-3 py-1.5 rounded-lg text-sm bg-accent hover:bg-accent/80 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            →
          </button>
        </div>
      )}
    </div>
  )
}
