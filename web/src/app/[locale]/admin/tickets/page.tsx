import { headers } from 'next/headers'
import { redirect } from 'next/navigation'
import Link from 'next/link'
import { auth } from '@/lib/auth'

const WEB_API = process.env.WEB_API_INTERNAL_URL ?? 'http://web-api:8000'

async function fetchTickets(token: string, status: string, page: number) {
  const r = await fetch(
    `${WEB_API}/tickets?status=${status}&page=${page}&limit=20`,
    {
      headers: { Cookie: `better-auth.session_token=${token}` },
      cache: 'no-store',
    }
  )
  if (!r.ok) throw new Error(`${r.status}`)
  return r.json() as Promise<{
    tickets: {
      id: number
      ticket_number: number
      user_id: string
      username: string
      subject: string
      status: string
      created_at: string | null
      closed_at: string | null
    }[]
    total: number
    page: number
    limit: number
  }>
}

function fmt(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

const STATUS_LABELS: Record<string, string> = {
  all: 'Tous',
  open: 'Ouverts',
  closed: 'Fermés',
}

const STATUS_BADGE: Record<string, string> = {
  open:   'bg-green-500/20 text-green-400 border border-green-500/30',
  closed: 'bg-zinc-500/20 text-zinc-400 border border-zinc-500/30',
}

export default async function AdminTicketsPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>
  searchParams: Promise<{ status?: string; page?: string }>
}) {
  const { locale } = await params
  const sp = await searchParams
  const status = ['all', 'open', 'closed'].includes(sp.status ?? '') ? (sp.status ?? 'all') : 'all'
  const page = Math.max(1, parseInt(sp.page ?? '1', 10))

  const session = await auth.api.getSession({ headers: await headers() })
  type UserWithExtras = NonNullable<typeof session>['user'] & { isAdmin?: boolean }
  const u = session?.user as UserWithExtras | undefined
  if (!u?.isAdmin) redirect(`/${locale}`)

  const token = (session!.session as any).token as string

  let data: Awaited<ReturnType<typeof fetchTickets>> | null = null
  try {
    data = await fetchTickets(token, status, page)
  } catch {}

  const totalPages = data ? Math.ceil(data.total / data.limit) : 1

  const buildUrl = (s: string, p: number) =>
    `/${locale}/admin/tickets?status=${s}&page=${p}`

  return (
    <div className="container mx-auto px-4 py-12 max-w-6xl">
      <div className="flex items-center gap-3 mb-8">
        <Link
          href={`/${locale}/admin`}
          className="text-muted-foreground hover:text-foreground transition-colors text-sm"
        >
          ← Admin
        </Link>
        <span className="text-muted-foreground">/</span>
        <h1 className="text-2xl font-extrabold tracking-tight">
          🎫 Historique des tickets
        </h1>
        {data && (
          <span className="ml-auto text-sm text-muted-foreground">
            {data.total} ticket{data.total !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Filtres */}
      <div className="flex gap-2 mb-6">
        {(['all', 'open', 'closed'] as const).map((s) => (
          <Link
            key={s}
            href={buildUrl(s, 1)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
              status === s
                ? 'bg-accent text-accent-foreground'
                : 'bg-muted text-muted-foreground hover:bg-accent/50'
            }`}
          >
            {STATUS_LABELS[s]}
          </Link>
        ))}
      </div>

      {/* Tableau */}
      <div className="rounded-xl border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left px-4 py-3 text-muted-foreground font-medium w-16">#</th>
              <th className="text-left px-4 py-3 text-muted-foreground font-medium">Utilisateur</th>
              <th className="text-left px-4 py-3 text-muted-foreground font-medium">Sujet</th>
              <th className="text-left px-4 py-3 text-muted-foreground font-medium w-24">Statut</th>
              <th className="text-left px-4 py-3 text-muted-foreground font-medium w-40">Ouvert le</th>
              <th className="text-left px-4 py-3 text-muted-foreground font-medium w-40">Fermé le</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {!data || data.tickets.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-muted-foreground">
                  Aucun ticket trouvé.
                </td>
              </tr>
            ) : (
              data.tickets.map((t) => (
                <tr key={t.id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 text-muted-foreground font-mono">
                    #{t.ticket_number.toString().padStart(4, '0')}
                  </td>
                  <td className="px-4 py-3 font-medium">{t.username}</td>
                  <td className="px-4 py-3 text-muted-foreground truncate max-w-[260px]">
                    {t.subject || '—'}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        STATUS_BADGE[t.status] ?? 'bg-muted text-muted-foreground'
                      }`}
                    >
                      {t.status === 'open' ? 'Ouvert' : 'Fermé'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground text-xs">{fmt(t.created_at)}</td>
                  <td className="px-4 py-3 text-muted-foreground text-xs">{fmt(t.closed_at)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-6">
          {page > 1 && (
            <Link
              href={buildUrl(status, page - 1)}
              className="px-3 py-1.5 rounded-lg bg-muted text-sm hover:bg-accent/50 transition-colors"
            >
              ← Précédent
            </Link>
          )}
          <span className="text-sm text-muted-foreground">
            Page {page} / {totalPages}
          </span>
          {page < totalPages && (
            <Link
              href={buildUrl(status, page + 1)}
              className="px-3 py-1.5 rounded-lg bg-muted text-sm hover:bg-accent/50 transition-colors"
            >
              Suivant →
            </Link>
          )}
        </div>
      )}
    </div>
  )
}
