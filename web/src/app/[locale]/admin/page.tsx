import { getTranslations } from 'next-intl/server'
import { redirect } from 'next/navigation'
import { api } from '@/lib/api'
import { AdminPanel } from './AdminPanel'

export default async function AdminPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params
  const t = await getTranslations('admin')

  let user = null
  try { user = await api.auth.me() } catch {}
  if (!user?.is_admin) redirect(`/${locale}`)

  let stats: any = null
  let commands: any = {}
  try {
    stats    = await api.admin.stats()
    commands = (await api.admin.commands()).commands
  } catch {}

  return (
    <div className="container mx-auto px-4 py-12">
      <h1 className="text-3xl font-bold mb-10">⚙️ {t('title')}</h1>

      {/* Server stats */}
      {stats && (
        <section className="mb-10">
          <h2 className="text-xl font-semibold mb-4">{t('server_stats')}</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: t('members'),        value: stats.members },
              { label: t('total_messages'), value: stats.total_messages },
              { label: t('total_warns'),    value: stats.total_warns },
              { label: t('total_articles'), value: stats.total_articles },
            ].map(({ label, value }) => (
              <div key={label} className="border border-border rounded-xl p-4 bg-card text-center">
                <div className="text-3xl font-bold">{value.toLocaleString()}</div>
                <div className="text-sm text-muted-foreground mt-1">{label}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      <AdminPanel initialCommands={commands} locale={locale} />
    </div>
  )
}
