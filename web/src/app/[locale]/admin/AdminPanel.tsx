'use client'

import { useState, useRef, useTransition } from 'react'
import { useTranslations } from 'next-intl'
import {
  actionWarn, actionKick, actionBan, actionTimeout,
  actionToggleCommand,
  fetchUserProfile, fetchUserWarns, actionDeleteWarn,
  fetchAllWarns, fetchAdminLogs,
  fetchQuestTemplates, createQuestTemplate, updateQuestTemplate, deleteQuestTemplate,
  fetchActiveQuests, deployWeeklyQuests,
  fetchAnalytics,
  type UserResult, type UserProfile, type WarnEntry,
  type GlobalWarnEntry, type AdminLog,
  type QuestTemplate, type ActiveQuest,
  type AnalyticsData,
} from './actions'
import { UserSearchInput } from './UserSearchInput'
import { AnalyticsDashboard } from './AnalyticsDashboard'

interface Props { initialCommands: Record<string, boolean>; descriptions: Record<string, string>; locale: string }

// ── Action badge config ───────────────────────────────────────────────────────

const ACTION_META: Record<string, { label: string; cls: string; icon: string }> = {
  warn:           { label: 'WARN',    cls: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',  icon: '⚠️' },
  kick:           { label: 'KICK',    cls: 'bg-orange-500/15 text-orange-400 border-orange-500/30',  icon: '🚪' },
  ban:            { label: 'BAN',     cls: 'bg-red-500/15    text-red-400    border-red-500/30',      icon: '🔨' },
  timeout:        { label: 'MUTE',    cls: 'bg-purple-500/15 text-purple-400 border-purple-500/30',  icon: '🔇' },
  delete_warn:    { label: 'ANNULÉ',  cls: 'bg-zinc-500/15   text-zinc-400   border-zinc-500/30',    icon: '🗑️' },
  command_toggle: { label: 'CMD',     cls: 'bg-blue-500/15   text-blue-400   border-blue-500/30',    icon: '⚙️' },
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1)  return 'À l\'instant'
  if (m < 60) return `il y a ${m} min`
  const h = Math.floor(m / 60)
  if (h < 24) return `il y a ${h}h`
  const d = Math.floor(h / 24)
  return `il y a ${d}j`
}

function LogEntry({ log }: { log: AdminLog }) {
  const meta = ACTION_META[log.action_type] ?? { label: log.action_type.toUpperCase(), cls: 'bg-zinc-500/15 text-zinc-400 border-zinc-500/30', icon: '📋' }
  const d = log.details as any

  return (
    <div className="flex items-start gap-3 border border-border rounded-lg px-4 py-3 bg-background hover:border-border/80 transition-colors">
      <span className="text-lg shrink-0 mt-0.5">{meta.icon}</span>
      <div className="flex-1 min-w-0 space-y-0.5">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-xs font-bold px-2 py-0.5 rounded border ${meta.cls}`}>
            {log.action_type === 'command_toggle' && d?.enabled === false ? 'CMD OFF' : log.action_type === 'command_toggle' ? 'CMD ON' : meta.label}
          </span>
          <span className="text-sm font-semibold">{log.actor_name ?? log.actor_id ?? '?'}</span>
          {log.target_name && (
            <>
              <span className="text-xs text-muted-foreground">→</span>
              <span className="text-sm text-foreground/80">{log.target_name}</span>
            </>
          )}
          {log.action_type === 'command_toggle' && d?.command_name && (
            <span className="font-mono text-sm text-muted-foreground">/{d.command_name}</span>
          )}
        </div>
        {d?.reason && (
          <p className="text-xs text-muted-foreground truncate max-w-md">{d.reason}</p>
        )}
        {log.action_type === 'timeout' && d?.duration_minutes && (
          <p className="text-xs text-muted-foreground">{d.duration_minutes} min</p>
        )}
      </div>
      <span className="text-xs text-muted-foreground shrink-0 whitespace-nowrap mt-0.5">
        {timeAgo(log.created_at)}
      </span>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

const TABS = [
  { key: 'commands',   label: 'Commandes' },
  { key: 'moderation', label: 'Modération' },
  { key: 'sanctions',  label: 'Sanctions' },
  { key: 'logs',       label: 'Logs' },
  { key: 'quests',     label: 'Quêtes' },
  { key: 'analytics',  label: '📊 Analytiques' },
] as const
type TabKey = typeof TABS[number]['key']

const QUEST_TYPES = [
  { value: 'messages',        label: '💬 Messages' },
  { value: 'voice_minutes',   label: '🎤 Temps vocal' },
  { value: 'bumps',           label: '📣 Bumps' },
  { value: 'invites',         label: '🤝 Invitations' },
  { value: 'images_posted',   label: '📸 Images/Vidéos' },
  { value: 'reactions_given', label: '😄 Réactions données' },
]

const QUEST_TYPE_LABELS: Record<string, string> = Object.fromEntries(
  QUEST_TYPES.map(t => [t.value, t.label])
)

export function AdminPanel({ initialCommands, descriptions, locale }: Props) {
  const t = useTranslations('admin')
  const [isPending, startTransition] = useTransition()
  const [activeTab, setActiveTab] = useState<TabKey>('commands')

  // ── Commands ──────────────────────────────────────────────────────────────
  const [commands, setCommands] = useState(initialCommands)
  const [tooltipCmd, setTooltipCmd] = useState<string | null>(null)
  const tooltipTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleCmdMouseEnter = (name: string) => {
    tooltipTimer.current = setTimeout(() => setTooltipCmd(name), 700)
  }
  const handleCmdMouseLeave = () => {
    if (tooltipTimer.current) clearTimeout(tooltipTimer.current)
    setTooltipCmd(null)
  }

  const toggleCommand = (name: string, current: boolean) => {
    startTransition(async () => {
      try {
        await actionToggleCommand(name, !current)
        setCommands(prev => ({ ...prev, [name]: !current }))
      } catch {}
    })
  }

  // ── Moderation ────────────────────────────────────────────────────────────
  const [modUser, setModUser]   = useState<UserResult | null>(null)
  const [reason, setReason]     = useState('')
  const [duration, setDuration] = useState('60')
  const [feedback, setFeedback] = useState<{ ok: boolean; msg: string } | null>(null)

  const doAction = (action: 'warn' | 'kick' | 'ban' | 'timeout') => {
    if (!modUser) return
    setFeedback(null)
    startTransition(async () => {
      const fn = {
        warn:    () => actionWarn(modUser.user_id, reason || 'Action depuis le panel'),
        kick:    () => actionKick(modUser.user_id, reason || 'Action depuis le panel'),
        ban:     () => actionBan(modUser.user_id, reason || 'Action depuis le panel'),
        timeout: () => actionTimeout(modUser.user_id, reason || 'Action depuis le panel', parseInt(duration) || 60),
      }[action]
      const result = await fn()
      if (!result.ok) {
        setFeedback({ ok: false, msg: result.error })
      } else {
        setFeedback({ ok: true, msg: t('action_success') })
        setReason('')
        if (inspectSelected?.user_id === modUser.user_id) loadInspect(modUser.user_id)
      }
    })
  }

  // ── Inspect ───────────────────────────────────────────────────────────────
  const [inspectSelected, setInspectSelected] = useState<UserResult | null>(null)
  const [inspectUser, setInspectUser]         = useState<UserProfile | null>(null)
  const [inspectWarns, setInspectWarns]       = useState<WarnEntry[]>([])
  const [inspectLoading, setInspectLoading]   = useState(false)
  const [inspectError, setInspectError]       = useState<string | null>(null)
  const [deletingWarn, setDeletingWarn]       = useState<number | null>(null)

  const loadInspect = (userId: string) => {
    setInspectLoading(true)
    setInspectError(null)
    startTransition(async () => {
      const [profile, warns] = await Promise.all([fetchUserProfile(userId), fetchUserWarns(userId)])
      if (!profile.ok) {
        setInspectError(profile.error)
        setInspectUser(null)
        setInspectWarns([])
      } else {
        setInspectUser(profile.data)
        setInspectWarns(warns.ok ? warns.data : [])
      }
      setInspectLoading(false)
    })
  }

  const handleInspectSelect = (u: UserResult) => { setInspectSelected(u); loadInspect(u.user_id) }
  const handleInspectClear  = () => { setInspectSelected(null); setInspectUser(null); setInspectWarns([]); setInspectError(null) }

  const handleDeleteWarn = (warnId: number) => {
    setDeletingWarn(warnId)
    startTransition(async () => {
      const result = await actionDeleteWarn(warnId)
      if (result.ok) {
        setInspectWarns(prev => prev.filter(w => w.id !== warnId))
        setInspectUser(prev => prev ? { ...prev, stats: { ...prev.stats, warn_count: prev.stats.warn_count - 1 } } : null)
      }
      setDeletingWarn(null)
    })
  }

  // ── Global warns ──────────────────────────────────────────────────────────
  const [allWarns, setAllWarns]               = useState<GlobalWarnEntry[] | null>(null)
  const [allWarnsLoading, setAllWarnsLoading] = useState(false)
  const [allWarnsError, setAllWarnsError]     = useState<string | null>(null)
  const [warnSearch, setWarnSearch]           = useState('')

  const loadAllWarns = () => {
    setAllWarnsLoading(true)
    startTransition(async () => {
      const result = await fetchAllWarns()
      if (!result.ok) setAllWarnsError(result.error)
      else setAllWarns(result.data)
      setAllWarnsLoading(false)
    })
  }

  const handleDeleteGlobalWarn = (warnId: number) => {
    setDeletingWarn(warnId)
    startTransition(async () => {
      const result = await actionDeleteWarn(warnId)
      if (result.ok) setAllWarns(prev => prev ? prev.filter(w => w.id !== warnId) : prev)
      setDeletingWarn(null)
    })
  }

  const filteredWarns = allWarns?.filter(w =>
    !warnSearch ||
    w.username.toLowerCase().includes(warnSearch.toLowerCase()) ||
    w.reason.toLowerCase().includes(warnSearch.toLowerCase())
  ) ?? []

  // ── Logs ──────────────────────────────────────────────────────────────────
  const LOG_TABS = [
    { key: 'all',        label: 'Tout',        filter: undefined },
    { key: 'moderation', label: 'Modération',  filter: 'warn,kick,ban,timeout,delete_warn' },
    { key: 'commands',   label: 'Commandes',   filter: 'command_toggle' },
  ] as const

  const [logsTab, setLogsTab]       = useState<typeof LOG_TABS[number]['key']>('all')
  const [logsData, setLogsData]     = useState<{ logs: AdminLog[]; total: number; page: number; pages: number } | null>(null)
  const [logsLoading, setLogsLoading] = useState(false)
  const [logsError, setLogsError]   = useState<string | null>(null)
  const [logsPage, setLogsPage]     = useState(1)

  const loadLogs = (tab = logsTab, page = logsPage) => {
    setLogsLoading(true)
    setLogsError(null)
    const filter = LOG_TABS.find(t => t.key === tab)?.filter
    startTransition(async () => {
      const result = await fetchAdminLogs(filter, page)
      if (!result.ok) setLogsError(result.error)
      else setLogsData(result.data)
      setLogsLoading(false)
    })
  }

  const switchLogsTab = (key: typeof logsTab) => {
    setLogsTab(key)
    setLogsPage(1)
    loadLogs(key, 1)
  }

  const goLogsPage = (p: number) => {
    setLogsPage(p)
    loadLogs(logsTab, p)
  }

  const voiceH = inspectUser ? Math.floor(inspectUser.stats.voice_hours) : 0
  const voiceM = inspectUser ? Math.round((inspectUser.stats.voice_hours - voiceH) * 60) : 0

  // ── Quests ────────────────────────────────────────────────────────────────
  const EMPTY_FORM: Omit<QuestTemplate, 'id' | 'created_at'> = {
    title: '', description: '', quest_type: 'messages',
    target_value: 100, xp_reward: 50, icon: '📋', is_enabled: true,
  }
  const [templates, setTemplates]           = useState<QuestTemplate[] | null>(null)
  const [activeQuests, setActiveQuests]     = useState<ActiveQuest[] | null>(null)
  const [questsLoading, setQuestsLoading]   = useState(false)
  const [questsError, setQuestsError]       = useState<string | null>(null)
  const [questForm, setQuestForm]           = useState(EMPTY_FORM)
  const [editingId, setEditingId]           = useState<number | null>(null)
  const [showForm, setShowForm]             = useState(false)
  const [deployCount, setDeployCount]       = useState('8')
  const [deploying, setDeploying]           = useState(false)
  const [deployMsg, setDeployMsg]           = useState<string | null>(null)
  const [questTypeFilter, setQuestTypeFilter] = useState<string>('all')

  const loadQuests = () => {
    setQuestsLoading(true)
    setQuestsError(null)
    startTransition(async () => {
      const [tRes, aRes] = await Promise.all([fetchQuestTemplates(), fetchActiveQuests()])
      if (!tRes.ok) setQuestsError(tRes.error)
      else setTemplates(tRes.data)
      if (aRes.ok) setActiveQuests(aRes.data)
      setQuestsLoading(false)
    })
  }

  const startCreate = () => {
    setEditingId(null)
    setQuestForm(EMPTY_FORM)
    setShowForm(true)
  }

  const startEdit = (t: QuestTemplate) => {
    setEditingId(t.id)
    setQuestForm({ title: t.title, description: t.description ?? '', quest_type: t.quest_type,
      target_value: t.target_value, xp_reward: t.xp_reward, icon: t.icon, is_enabled: t.is_enabled })
    setShowForm(true)
  }

  const saveQuest = () => {
    startTransition(async () => {
      const r = editingId
        ? await updateQuestTemplate(editingId, questForm)
        : await createQuestTemplate(questForm)
      if (!r.ok) { setQuestsError(r.error); return }
      if (editingId) {
        setTemplates(prev => prev ? prev.map(t => t.id === editingId ? r.data : t) : prev)
      } else {
        setTemplates(prev => prev ? [...prev, r.data] : [r.data])
      }
      setShowForm(false)
      setEditingId(null)
      setQuestForm(EMPTY_FORM)
    })
  }

  const handleDeleteTemplate = (id: number) => {
    startTransition(async () => {
      const r = await deleteQuestTemplate(id)
      if (r.ok) setTemplates(prev => prev ? prev.filter(t => t.id !== id) : prev)
      else setQuestsError(r.error)
    })
  }

  const handleDeploy = () => {
    setDeploying(true)
    setDeployMsg(null)
    startTransition(async () => {
      const r = await deployWeeklyQuests(parseInt(deployCount) || 8)
      if (!r.ok) setDeployMsg(`Erreur : ${r.error}`)
      else setDeployMsg(`${r.data.deployed} quête(s) déployée(s) pour la semaine du ${r.data.week_start}`)
      setDeploying(false)
      loadQuests()
    })
  }

  const filteredTemplates = templates?.filter(
    t => questTypeFilter === 'all' || t.quest_type === questTypeFilter
  ) ?? []

  // ── Analytics ─────────────────────────────────────────────────────────────
  const [analyticsData, setAnalyticsData]       = useState<AnalyticsData | null>(null)
  const [analyticsLoading, setAnalyticsLoading] = useState(false)
  const [analyticsError, setAnalyticsError]     = useState<string | null>(null)

  const loadAnalytics = () => {
    setAnalyticsLoading(true)
    setAnalyticsError(null)
    startTransition(async () => {
      const result = await fetchAnalytics()
      if (!result.ok) setAnalyticsError(result.error)
      else setAnalyticsData(result.data)
      setAnalyticsLoading(false)
    })
  }

  return (
    <div>
      {/* ── Tab nav ────────────────────────────────────────────────────────── */}
      <div className="flex gap-0 border-b border-border mb-8 overflow-x-auto">
        {TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => {
              setActiveTab(tab.key)
              if (tab.key === 'analytics' && !analyticsData && !analyticsLoading) loadAnalytics()
            }}
            className={`px-5 py-3 text-sm font-medium whitespace-nowrap border-b-2 -mb-px transition-colors ${
              activeTab === tab.key
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Commands tab ───────────────────────────────────────────────────── */}
      <div className={activeTab === 'commands' ? '' : 'hidden'}>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {Object.entries(commands).map(([name, enabled]) => (
            <div
              key={name}
              className="relative flex items-center justify-between glass-card px-4 py-3"
              onMouseEnter={() => handleCmdMouseEnter(name)}
              onMouseLeave={handleCmdMouseLeave}
            >
              {tooltipCmd === name && (
                <div className="absolute bottom-full left-0 mb-2 z-20 w-64 rounded-lg border border-border/80 bg-[hsl(224_71%_8%)] shadow-xl shadow-black/40 px-3 py-2.5 pointer-events-none">
                  <p className="text-xs font-semibold text-foreground mb-1">/{name}</p>
                  <p className="text-xs text-muted-foreground">
                    {descriptions[name] || 'Aucune description disponible.'}
                  </p>
                </div>
              )}
              <span className="font-mono text-sm">/{name}</span>
              <button
                onClick={() => toggleCommand(name, enabled)}
                disabled={isPending}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${enabled ? 'bg-green-500' : 'bg-border'}`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${enabled ? 'translate-x-6' : 'translate-x-1'}`} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* ── Moderation tab ─────────────────────────────────────────────────── */}
      <div className={activeTab === 'moderation' ? 'space-y-8' : 'hidden'}>
        {/* Actions */}
        <div className="glass-card p-6 space-y-4">
          <h3 className="text-base font-semibold">{t('moderation')}</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <UserSearchInput
              selected={modUser}
              onSelect={setModUser}
              onClear={() => { setModUser(null); setFeedback(null) }}
            />
            <div>
              <label className="text-sm text-muted-foreground mb-1 block">{t('reason')}</label>
              <input
                value={reason}
                onChange={e => setReason(e.target.value)}
                placeholder={t('reason')}
                className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground mb-1 block">{t('duration')} (min)</label>
              <input
                type="number" value={duration}
                onChange={e => setDuration(e.target.value)}
                className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
          </div>
          {modUser && (
            <p className="text-xs text-muted-foreground">
              Cible : <span className="font-semibold text-foreground">{modUser.username}</span>
              <span className="ml-2 opacity-50 font-mono">#{modUser.user_id}</span>
            </p>
          )}
          <div className="flex flex-wrap gap-3">
            {(['warn', 'kick', 'ban', 'timeout'] as const).map(action => (
              <button
                key={action}
                onClick={() => doAction(action)}
                disabled={!modUser || isPending}
                className={`px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-opacity ${
                  action === 'ban'     ? 'bg-destructive text-destructive-foreground hover:opacity-90' :
                  action === 'kick'    ? 'bg-orange-600 text-white hover:opacity-90' :
                  action === 'timeout' ? 'bg-yellow-600 text-white hover:opacity-90' :
                  'bg-secondary text-secondary-foreground hover:opacity-90'
                }`}
              >
                {isPending ? '…' : t(`${action}_user`)}
              </button>
            ))}
          </div>
          {feedback && (
            <p className={`text-sm ${feedback.ok ? 'text-green-400' : 'text-destructive'}`}>{feedback.msg}</p>
          )}
        </div>

        {/* User profile */}
        <div className="glass-card p-6 space-y-6">
          <h3 className="text-base font-semibold">Profil & Sanctions</h3>
          <div className="max-w-sm">
            <UserSearchInput
              selected={inspectSelected}
              onSelect={handleInspectSelect}
              onClear={handleInspectClear}
              label="Rechercher un membre"
              placeholder="Pseudo Discord…"
            />
          </div>
          {inspectLoading && <div className="text-sm text-muted-foreground animate-pulse">Chargement…</div>}
          {inspectError  && <p className="text-sm text-destructive">{inspectError}</p>}
          {inspectUser && !inspectLoading && (
            <div className="space-y-6">
              <div className="flex items-center gap-4">
                {inspectUser.user.discord_avatar
                  ? <img src={inspectUser.user.discord_avatar} alt={inspectUser.user.username} className="w-14 h-14 rounded-full border border-border" />
                  : <div className="w-14 h-14 rounded-full bg-accent flex items-center justify-center text-2xl font-bold">{inspectUser.user.username[0]?.toUpperCase()}</div>
                }
                <div>
                  <p className="text-lg font-semibold">{inspectUser.user.nickname ?? inspectUser.user.username}</p>
                  {inspectUser.user.nickname && <p className="text-sm text-muted-foreground">@{inspectUser.user.username}</p>}
                  <p className="text-xs text-muted-foreground font-mono">ID {inspectSelected?.user_id}</p>
                </div>
                <button onClick={() => setModUser(inspectSelected)} className="ml-auto px-3 py-1.5 bg-secondary text-secondary-foreground rounded-lg text-xs hover:opacity-90">
                  Sanctionner
                </button>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { label: 'Messages',  value: inspectUser.stats.total_messages.toLocaleString(), icon: '💬', sub: `#${inspectUser.stats.msg_rank}` },
                  { label: 'Vocal',     value: `${voiceH}h ${voiceM}m`,                           icon: '🎤', sub: `#${inspectUser.stats.voice_rank}` },
                  { label: 'XP',        value: inspectUser.stats.xp_total.toLocaleString(),        icon: '⭐', sub: `Niv. ${inspectUser.stats.current_level}` },
                  { label: 'Sanctions', value: inspectWarns.length.toString(),                     icon: inspectWarns.length > 0 ? '⚠️' : '✅', sub: inspectWarns.length === 0 ? 'Aucune' : `${inspectWarns.length} active${inspectWarns.length > 1 ? 's' : ''}` },
                ].map(({ label, value, icon, sub }) => (
                  <div key={label} className="stat-card">
                    <div className="text-2xl mb-1">{icon}</div>
                    <div className="text-xl font-bold">{value}</div>
                    <div className="text-xs text-muted-foreground">{label}</div>
                    <div className="text-xs text-primary mt-0.5">{sub}</div>
                  </div>
                ))}
              </div>
              <div>
                <h4 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Sanctions ({inspectWarns.length})</h4>
                {inspectWarns.length === 0
                  ? <p className="text-sm text-muted-foreground">Aucune sanction enregistrée.</p>
                  : (
                    <div className="space-y-2">
                      {inspectWarns.map(w => (
                        <div key={w.id} className="flex items-start justify-between gap-3 border border-border rounded-lg px-4 py-3 bg-background">
                          <div className="min-w-0">
                            <p className="text-sm font-medium truncate">{w.reason}</p>
                            <p className="text-xs text-muted-foreground mt-0.5">
                              {new Date(w.create_time * 1000).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                              <span className="ml-2 opacity-60">par <span className="font-medium text-foreground/70">{w.moderator_username ?? `#${w.moderator_id}`}</span></span>
                            </p>
                          </div>
                          <button onClick={() => handleDeleteWarn(w.id)} disabled={deletingWarn === w.id || isPending}
                            className="shrink-0 px-2 py-1 text-xs text-destructive border border-destructive/30 rounded hover:bg-destructive hover:text-destructive-foreground transition-colors disabled:opacity-40">
                            {deletingWarn === w.id ? '…' : 'Supprimer'}
                          </button>
                        </div>
                      ))}
                    </div>
                  )
                }
              </div>
              {inspectUser.achievements.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Succès débloqués ({inspectUser.achievements.length})</h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {inspectUser.achievements.map(a => (
                      <div key={a.id} className="flex items-center gap-3 border border-border rounded-lg px-3 py-2 bg-background">
                        <span className="text-xl">{a.icon}</span>
                        <div className="min-w-0">
                          <p className="text-sm font-medium truncate">{a.name}</p>
                          <p className="text-xs text-muted-foreground truncate">{a.description}</p>
                        </div>
                        <span className="shrink-0 text-xs text-primary font-medium">+{a.points}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Sanctions tab ──────────────────────────────────────────────────── */}
      <div className={activeTab === 'sanctions' ? '' : 'hidden'}>
        <div className="flex items-center justify-between mb-4">
          <p className="text-sm text-muted-foreground">Toutes les sanctions actives du serveur</p>
          <button onClick={loadAllWarns} disabled={allWarnsLoading || isPending}
            className="px-4 py-2 text-sm rounded-lg border border-border text-muted-foreground hover:text-foreground hover:border-primary/30 transition-colors disabled:opacity-40">
            {allWarnsLoading ? 'Chargement…' : allWarns ? 'Actualiser' : 'Charger'}
          </button>
        </div>
        {allWarnsError && <p className="text-sm text-destructive mb-3">{allWarnsError}</p>}
        {allWarns !== null && (
          <div className="glass-card p-6 space-y-4">
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <span className="text-sm text-muted-foreground">
                {filteredWarns.length} sanction{filteredWarns.length !== 1 ? 's' : ''}
                {warnSearch ? ' filtrée' + (filteredWarns.length !== 1 ? 's' : '') : ' au total'}
              </span>
              <input value={warnSearch} onChange={e => setWarnSearch(e.target.value)}
                placeholder="Filtrer par pseudo ou raison…"
                className="w-64 bg-background border border-border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            {filteredWarns.length === 0
              ? <p className="text-sm text-muted-foreground">Aucune sanction trouvée.</p>
              : (
                <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
                  {filteredWarns.map(w => (
                    <div key={w.id} className="flex items-center gap-3 border border-border rounded-lg px-4 py-3 bg-background">
                      {w.discord_avatar
                        ? <img src={w.discord_avatar} alt={w.username} className="w-8 h-8 rounded-full shrink-0" />
                        : <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center text-sm font-bold shrink-0">{w.username[0]?.toUpperCase()}</div>
                      }
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-semibold">{w.username}</span>
                          <span className="text-xs text-muted-foreground font-mono">#{w.user_id}</span>
                        </div>
                        <p className="text-sm text-foreground/80 truncate">{w.reason}</p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {new Date(w.create_time * 1000).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                          {w.moderator_username && <span className="ml-2 opacity-60">par <span className="font-medium text-foreground/70">{w.moderator_username}</span></span>}
                        </p>
                      </div>
                      <button onClick={() => handleDeleteGlobalWarn(w.id)} disabled={deletingWarn === w.id || isPending}
                        className="shrink-0 px-2 py-1 text-xs text-destructive border border-destructive/30 rounded hover:bg-destructive hover:text-destructive-foreground transition-colors disabled:opacity-40">
                        {deletingWarn === w.id ? '…' : 'Supprimer'}
                      </button>
                    </div>
                  ))}
                </div>
              )
            }
          </div>
        )}
      </div>

      {/* ── Logs tab ───────────────────────────────────────────────────────── */}
      <div className={activeTab === 'logs' ? '' : 'hidden'}>
        {/* Sub-tab bar + load button */}
        <div className="flex items-center justify-between mb-4 gap-4 flex-wrap">
          <div className="flex gap-1 bg-background border border-border rounded-lg p-1">
            {LOG_TABS.map(lt => (
              <button key={lt.key} onClick={() => switchLogsTab(lt.key)}
                className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${
                  logsTab === lt.key ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'
                }`}>
                {lt.label}
                {logsData && logsTab === lt.key && (
                  <span className="ml-1.5 opacity-70">({logsData.total})</span>
                )}
              </button>
            ))}
          </div>
          <button onClick={() => loadLogs()} disabled={logsLoading || isPending}
            className="px-4 py-2 text-sm rounded-lg border border-border text-muted-foreground hover:text-foreground hover:border-primary/30 transition-colors disabled:opacity-40">
            {logsLoading ? 'Chargement…' : logsData ? 'Actualiser' : 'Charger les logs'}
          </button>
        </div>

        {logsError && <p className="text-sm text-destructive mb-4">{logsError}</p>}

        {logsData ? (
          <div className="space-y-4">
            {logsData.logs.length === 0 ? (
              <p className="text-sm text-muted-foreground py-8 text-center">Aucun log pour cette catégorie.</p>
            ) : (
              <div className="space-y-2">
                {logsData.logs.map(log => <LogEntry key={log.id} log={log} />)}
              </div>
            )}

            {/* Pagination */}
            {logsData.pages > 1 && (
              <div className="flex items-center justify-center gap-2 pt-2">
                <button onClick={() => goLogsPage(logsData.page - 1)} disabled={logsData.page <= 1 || isPending}
                  className="px-3 py-1.5 text-sm rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-40 transition-colors">
                  ‹
                </button>
                <span className="text-sm text-muted-foreground">
                  Page {logsData.page} / {logsData.pages}
                </span>
                <button onClick={() => goLogsPage(logsData.page + 1)} disabled={logsData.page >= logsData.pages || isPending}
                  className="px-3 py-1.5 text-sm rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-40 transition-colors">
                  ›
                </button>
              </div>
            )}
          </div>
        ) : !logsLoading && (
          <div className="text-center py-16 text-muted-foreground">
            <p className="text-4xl mb-3">📋</p>
            <p className="text-sm">Clique sur "Charger les logs" pour afficher l'historique des actions.</p>
          </div>
        )}
      </div>

      {/* ── Quests tab ─────────────────────────────────────────────────────── */}
      <div className={activeTab === 'quests' ? 'space-y-6' : 'hidden'}>

        {/* Active quests this week */}
        <div className="glass-card p-6 space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <h3 className="text-base font-semibold">Quêtes actives cette semaine</h3>
            <div className="flex items-center gap-2 flex-wrap">
              <div className="flex items-center gap-2">
                <label className="text-xs text-muted-foreground">Nombre :</label>
                <input type="number" min={1} max={20} value={deployCount}
                  onChange={e => setDeployCount(e.target.value)}
                  className="w-16 bg-background border border-border rounded px-2 py-1 text-sm text-center focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <button onClick={handleDeploy} disabled={deploying || isPending}
                className="px-4 py-2 text-sm rounded-lg bg-primary text-primary-foreground hover:opacity-90 transition-opacity disabled:opacity-40">
                {deploying ? 'Déploiement…' : 'Déployer de nouvelles quêtes'}
              </button>
              <button onClick={loadQuests} disabled={questsLoading || isPending}
                className="px-4 py-2 text-sm rounded-lg border border-border text-muted-foreground hover:text-foreground hover:border-primary/30 transition-colors disabled:opacity-40">
                {questsLoading ? 'Chargement…' : activeQuests ? 'Actualiser' : 'Charger'}
              </button>
            </div>
          </div>
          {deployMsg && (
            <p className={`text-sm ${deployMsg.startsWith('Erreur') ? 'text-destructive' : 'text-green-400'}`}>
              {deployMsg}
            </p>
          )}
          {questsError && <p className="text-sm text-destructive">{questsError}</p>}
          {activeQuests !== null && (
            activeQuests.length === 0
              ? <p className="text-sm text-muted-foreground">Aucune quête active cette semaine.</p>
              : (
                <div className="space-y-2">
                  {activeQuests.map(q => (
                    <div key={q.id} className="flex items-center gap-3 border border-border rounded-lg px-4 py-3 bg-background">
                      <span className="text-xl shrink-0">{q.icon}</span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{q.title}</p>
                        <p className="text-xs text-muted-foreground truncate">{q.description}</p>
                      </div>
                      <div className="shrink-0 text-right space-y-0.5">
                        <p className="text-xs font-mono text-muted-foreground">
                          {QUEST_TYPE_LABELS[q.quest_type] ?? q.quest_type}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          cible: <span className="text-foreground font-medium">{q.target_value}</span>
                          {' · '}
                          <span className="text-primary font-medium">+{q.xp_reward} XP</span>
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {Number(q.participant_count)} joueur{Number(q.participant_count) !== 1 ? 's' : ''}
                          {' · '}
                          {Number(q.completed_count)} terminé{Number(q.completed_count) !== 1 ? 's' : ''}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )
          )}
        </div>

        {/* Quest template library */}
        <div className="glass-card p-6 space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <h3 className="text-base font-semibold">
              Bibliothèque de quêtes
              {templates !== null && <span className="ml-2 text-sm text-muted-foreground">({templates.length})</span>}
            </h3>
            <button onClick={startCreate}
              className="px-4 py-2 text-sm rounded-lg bg-primary text-primary-foreground hover:opacity-90 transition-opacity">
              + Nouvelle quête
            </button>
          </div>

          {/* Filter */}
          <div className="flex gap-1 flex-wrap">
            {[{ value: 'all', label: 'Toutes' }, ...QUEST_TYPES].map(t => (
              <button key={t.value} onClick={() => setQuestTypeFilter(t.value)}
                className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                  questTypeFilter === t.value
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'border-border text-muted-foreground hover:text-foreground hover:border-primary/30'
                }`}>
                {t.label}
              </button>
            ))}
          </div>

          {/* Inline form */}
          {showForm && (
            <div className="border border-border rounded-xl p-4 bg-background space-y-3">
              <h4 className="text-sm font-semibold">{editingId ? 'Modifier la quête' : 'Nouvelle quête'}</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="flex gap-2">
                  <div className="w-16">
                    <label className="text-xs text-muted-foreground mb-1 block">Icône</label>
                    <input value={questForm.icon} onChange={e => setQuestForm(f => ({ ...f, icon: e.target.value }))}
                      maxLength={4}
                      className="w-full bg-background border border-border rounded-lg px-2 py-2 text-sm text-center focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  <div className="flex-1">
                    <label className="text-xs text-muted-foreground mb-1 block">Titre *</label>
                    <input value={questForm.title} onChange={e => setQuestForm(f => ({ ...f, title: e.target.value }))}
                      placeholder="Titre de la quête"
                      className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Type de condition *</label>
                  <select value={questForm.quest_type} onChange={e => setQuestForm(f => ({ ...f, quest_type: e.target.value }))}
                    className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary">
                    {QUEST_TYPES.map(t => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Description</label>
                  <input value={questForm.description ?? ''} onChange={e => setQuestForm(f => ({ ...f, description: e.target.value }))}
                    placeholder="Description visible par les joueurs"
                    className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs text-muted-foreground mb-1 block">Objectif *</label>
                    <input type="number" min={1} value={questForm.target_value}
                      onChange={e => setQuestForm(f => ({ ...f, target_value: parseInt(e.target.value) || 1 }))}
                      className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground mb-1 block">Récompense XP *</label>
                    <input type="number" min={1} value={questForm.xp_reward}
                      onChange={e => setQuestForm(f => ({ ...f, xp_reward: parseInt(e.target.value) || 1 }))}
                      className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-3 pt-1">
                <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
                  <button
                    type="button"
                    onClick={() => setQuestForm(f => ({ ...f, is_enabled: !f.is_enabled }))}
                    className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${questForm.is_enabled ? 'bg-green-500' : 'bg-border'}`}
                  >
                    <span className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${questForm.is_enabled ? 'translate-x-5' : 'translate-x-1'}`} />
                  </button>
                  Activée dans la rotation
                </label>
                <div className="flex gap-2 ml-auto">
                  <button onClick={() => { setShowForm(false); setEditingId(null) }}
                    className="px-3 py-1.5 text-sm rounded-lg border border-border text-muted-foreground hover:text-foreground transition-colors">
                    Annuler
                  </button>
                  <button onClick={saveQuest} disabled={!questForm.title || !questForm.quest_type || isPending}
                    className="px-4 py-1.5 text-sm rounded-lg bg-primary text-primary-foreground hover:opacity-90 transition-opacity disabled:opacity-40">
                    {isPending ? '…' : editingId ? 'Enregistrer' : 'Créer'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Template list */}
          {templates === null && !questsLoading && (
            <div className="text-center py-12 text-muted-foreground">
              <p className="text-4xl mb-3">🎯</p>
              <p className="text-sm">Clique sur "Charger" pour afficher la bibliothèque de quêtes.</p>
            </div>
          )}
          {questsLoading && <p className="text-sm text-muted-foreground animate-pulse">Chargement…</p>}
          {templates !== null && filteredTemplates.length === 0 && (
            <p className="text-sm text-muted-foreground">Aucune quête pour ce filtre.</p>
          )}
          {filteredTemplates.length > 0 && (
            <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
              {filteredTemplates.map(t => (
                <div key={t.id} className={`flex items-center gap-3 border rounded-lg px-4 py-3 bg-background transition-colors ${t.is_enabled ? 'border-border' : 'border-border/50 opacity-60'}`}>
                  <span className="text-xl shrink-0">{t.icon}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{t.title}</p>
                    <p className="text-xs text-muted-foreground truncate">{t.description}</p>
                  </div>
                  <div className="shrink-0 text-right space-y-0.5 hidden sm:block">
                    <p className="text-xs text-muted-foreground">{QUEST_TYPE_LABELS[t.quest_type] ?? t.quest_type}</p>
                    <p className="text-xs">
                      <span className="text-foreground font-medium">{t.target_value}</span>
                      <span className="text-muted-foreground"> · </span>
                      <span className="text-primary font-medium">+{t.xp_reward} XP</span>
                    </p>
                  </div>
                  <div className="shrink-0 flex gap-1">
                    <button onClick={() => startEdit(t)}
                      className="px-2 py-1 text-xs text-muted-foreground border border-border rounded hover:text-foreground hover:border-primary/30 transition-colors">
                      Éditer
                    </button>
                    <button onClick={() => handleDeleteTemplate(t.id)} disabled={isPending}
                      className="px-2 py-1 text-xs text-destructive border border-destructive/30 rounded hover:bg-destructive hover:text-destructive-foreground transition-colors disabled:opacity-40">
                      ×
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Analytics tab ──────────────────────────────────────────────────── */}
      <div className={activeTab === 'analytics' ? '' : 'hidden'}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold">Tableau de bord analytique</h2>
          <button
            onClick={loadAnalytics}
            disabled={analyticsLoading}
            className="px-4 py-2 text-sm rounded-lg border border-border hover:border-primary/40 hover:text-primary transition-colors disabled:opacity-40"
          >
            {analyticsLoading ? 'Chargement…' : '↻ Actualiser'}
          </button>
        </div>

        {analyticsError && (
          <p className="text-sm text-destructive mb-4">{analyticsError}</p>
        )}

        {!analyticsData && !analyticsLoading && !analyticsError && (
          <div className="text-center py-16 text-muted-foreground">
            <p className="text-4xl mb-3">📊</p>
            <p className="text-sm">Clique sur l&apos;onglet pour charger les analytiques.</p>
          </div>
        )}

        {analyticsLoading && (
          <div className="text-center py-16 text-muted-foreground">
            <p className="text-sm animate-pulse">Chargement des données…</p>
          </div>
        )}

        {analyticsData && !analyticsLoading && (
          <AnalyticsDashboard data={analyticsData} />
        )}
      </div>
    </div>
  )
}
