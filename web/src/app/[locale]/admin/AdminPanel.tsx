'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { api } from '@/lib/api'

interface Props { initialCommands: Record<string, boolean>; locale: string }

export function AdminPanel({ initialCommands, locale }: Props) {
  const t = useTranslations('admin')
  const tc = useTranslations('common')
  const [commands, setCommands] = useState(initialCommands)
  const [mod, setMod] = useState({ user_id: '', reason: '', duration: '60' })
  const [modFeedback, setModFeedback] = useState('')

  const toggleCommand = async (name: string, current: boolean) => {
    try {
      await api.admin.toggleCommand({ command_name: name, enabled: !current })
      setCommands(prev => ({ ...prev, [name]: !current }))
    } catch {}
  }

  const doAction = async (action: 'kick' | 'ban' | 'timeout' | 'warn') => {
    if (!mod.user_id) return
    setModFeedback('')
    try {
      const payload = {
        user_id:  parseInt(mod.user_id),
        reason:   mod.reason || 'Action depuis le panel',
        duration: action === 'timeout' ? parseInt(mod.duration) : undefined,
      }
      await api.admin[action](payload)
      setModFeedback(t('action_success'))
    } catch (e: any) {
      setModFeedback(`${t('action_error')} — ${e.message}`)
    }
  }

  return (
    <div className="space-y-10">
      {/* Commands */}
      <section>
        <h2 className="text-xl font-semibold mb-4">{t('commands')}</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {Object.entries(commands).map(([name, enabled]) => (
            <div key={name}
                 className="flex items-center justify-between border border-border rounded-lg px-4 py-3 bg-card">
              <span className="font-mono text-sm">/{name}</span>
              <button
                onClick={() => toggleCommand(name, enabled)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${enabled ? 'bg-green-500' : 'bg-border'}`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${enabled ? 'translate-x-6' : 'translate-x-1'}`} />
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* Moderation */}
      <section>
        <h2 className="text-xl font-semibold mb-4">{t('moderation')}</h2>
        <div className="border border-border rounded-xl p-6 bg-card space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="text-sm text-muted-foreground mb-1 block">{t('user_id')}</label>
              <input
                value={mod.user_id}
                onChange={e => setMod(m => ({ ...m, user_id: e.target.value }))}
                placeholder="123456789..."
                className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground mb-1 block">{t('reason')}</label>
              <input
                value={mod.reason}
                onChange={e => setMod(m => ({ ...m, reason: e.target.value }))}
                placeholder={t('reason')}
                className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground mb-1 block">{t('duration')}</label>
              <input
                type="number" value={mod.duration}
                onChange={e => setMod(m => ({ ...m, duration: e.target.value }))}
                className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            {(['warn', 'kick', 'ban', 'timeout'] as const).map(action => (
              <button key={action} onClick={() => doAction(action)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium ${
                        action === 'ban' ? 'bg-destructive text-destructive-foreground hover:opacity-90' :
                        action === 'kick' ? 'bg-orange-600 text-white hover:opacity-90' :
                        'bg-secondary text-secondary-foreground hover:opacity-90'
                      }`}>
                {t(`${action}_user`)}
              </button>
            ))}
          </div>

          {modFeedback && (
            <p className={`text-sm ${modFeedback.includes(t('action_error').split('—')[0].trim()) ? 'text-destructive' : 'text-green-400'}`}>
              {modFeedback}
            </p>
          )}
        </div>
      </section>
    </div>
  )
}
