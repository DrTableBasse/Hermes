'use client'
import { useState, useEffect } from 'react'
import { api, Quest } from '@/lib/api'
import QuestCard from '@/components/QuestCard'

export default function QuestsPage() {
  const [quests, setQuests] = useState<Quest[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.quests.list()
      .then(r => setQuests(r.quests))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const handleClaim = async (questId: number) => {
    try {
      await api.quests.claim(questId)
      setQuests(prev => prev.map(q => q.id === questId ? { ...q, status: 'claimed' } : q))
    } catch {}
  }

  return (
    <main className="max-w-2xl mx-auto px-4 py-12">
      <h1 className="text-2xl font-extrabold tracking-tight mb-2">📋 Défis hebdomadaires</h1>
      <p className="text-muted-foreground text-sm mb-8">Les défis se réinitialisent chaque lundi.</p>

      {loading ? (
        <div className="text-center text-muted-foreground py-12 animate-pulse">Chargement...</div>
      ) : quests.length === 0 ? (
        <div className="glass-card text-center text-muted-foreground py-12 px-4">
          Aucun défi actif cette semaine.
        </div>
      ) : (
        <div className="grid gap-4">
          {quests.map(q => (
            <QuestCard key={q.id} quest={q} onClaim={handleClaim} />
          ))}
        </div>
      )}
    </main>
  )
}
