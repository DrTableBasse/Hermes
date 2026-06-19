import { headers } from 'next/headers'
import Link from 'next/link'
import { redirect } from 'next/navigation'
import { auth } from '@/lib/auth'
import { serverListAllTickets } from '@/lib/server-api'
import type { Ticket } from '@/lib/api'

const STATUS_LABEL: Record<string, string> = {
  open:     '🟢 Ouvert',
  resolved: '🟡 Résolu',
  closed:   '⚪ Fermé',
}
const STATUS_CLASS: Record<string, string> = {
  open:     'text-green-400',
  resolved: 'text-yellow-400',
  closed:   'text-muted-foreground',
}

export default async function TicketsAdminPage({
  params,
}: {
  params: Promise<{ locale: string }>
}) {
  const { locale } = await params
  const session = await auth.api.getSession({ headers: await headers() })
  const u = session?.user as any
  if (!u) redirect(`/${locale}/login`)
  if (!u.isAdmin) redirect(`/${locale}`)

  const token = (session!.session as any).token as string
  let tickets: Ticket[] = []
  try { tickets = await serverListAllTickets(token) } catch {}

  return (
    <div className="container mx-auto px-4 py-12 max-w-4xl">
      <h1 className="text-3xl font-extrabold tracking-tight mb-8">🎫 Tickets</h1>

      {tickets.length === 0 ? (
        <p className="text-muted-foreground text-center py-12">Aucun ticket.</p>
      ) : (
        <div className="space-y-3">
          {tickets.map((t) => (
            <Link
              key={t.id}
              href={`/${locale}/tickets/${t.id}`}
              className="glass-card p-4 flex items-center gap-4 hover:bg-accent/40 transition-colors block"
            >
              <span className="text-lg font-bold text-muted-foreground w-10 shrink-0">
                #{t.id}
              </span>
              <div className="flex-1 min-w-0">
                <p className="font-semibold truncate">{t.title}</p>
                <p className="text-xs text-muted-foreground">
                  {t.username ?? t.user_id} · {new Date(t.created_at).toLocaleDateString('fr-FR')}
                </p>
              </div>
              <span className={`text-sm font-medium shrink-0 ${STATUS_CLASS[t.status]}`}>
                {STATUS_LABEL[t.status]}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
