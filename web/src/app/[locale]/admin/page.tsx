import { headers } from 'next/headers'
import { getTranslations } from 'next-intl/server'
import { redirect } from 'next/navigation'
import { auth } from '@/lib/auth'
import { AdminPanel } from './AdminPanel'

const WEB_API = process.env.WEB_API_INTERNAL_URL ?? 'http://web-api:8000'

async function serverFetch(path: string, token: string) {
  const r = await fetch(`${WEB_API}${path}`, {
    headers: { Cookie: `better-auth.session_token=${token}` },
    cache: 'no-store',
  })
  if (!r.ok) throw new Error(`${r.status}`)
  return r.json()
}

export default async function AdminPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params
  const t = await getTranslations('admin')

  const session = await auth.api.getSession({ headers: await headers() })
  type UserWithExtras = NonNullable<typeof session>['user'] & { isAdmin?: boolean }
  const u = session?.user as UserWithExtras | undefined
  if (!u?.isAdmin) redirect(`/${locale}`)

  const token = (session!.session as any).token as string

  let stats: any = null
  let commands: Record<string, boolean> = {}
  let commandDescriptions: Record<string, string> = {}
  try {
    stats = await serverFetch('/admin/stats', token)
    const cmdsData = await serverFetch('/admin/commands', token)
    commands = cmdsData.commands ?? {}
    commandDescriptions = cmdsData.descriptions ?? {}
  } catch {}

  const statIcons = ['👥', '💬', '⚠️', '📝']

  return (
    <div className="container mx-auto px-4 py-12">
      <h1 className="text-3xl font-extrabold tracking-tight mb-10">
        <span className="gradient-hero">⚙️ {t('title')}</span>
      </h1>

      {stats && (
        <section className="mb-12">
          <h2 className="text-xl font-bold mb-5">{t('server_stats')}</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: t('members'),        value: stats.members },
              { label: t('total_messages'), value: stats.total_messages },
              { label: t('total_warns'),    value: stats.total_warns },
              { label: t('total_articles'), value: stats.total_articles },
            ].map(({ label, value }, i) => (
              <div key={label} className="stat-card">
                <div className="text-3xl mb-2">{statIcons[i]}</div>
                <div className="text-3xl font-extrabold tabular-nums">{value.toLocaleString()}</div>
                <div className="text-sm text-muted-foreground mt-1.5">{label}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="mb-8">
        <h2 className="text-xl font-bold mb-4">Outils</h2>
        <div className="flex flex-wrap gap-3">
          <a
            href={`/${locale}/admin/tickets`}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-muted hover:bg-accent/50 border border-border transition-colors text-sm font-medium"
          >
            🎫 Historique tickets
          </a>
        </div>
      </section>

      <AdminPanel initialCommands={commands} descriptions={commandDescriptions} locale={locale} />
    </div>
  )
}
