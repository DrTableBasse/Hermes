import type { Metadata } from "next"
import Link from "next/link"
import { RankPagination } from "@/components/members/rank-pagination"
import { Chip } from "@/components/ui/chip"
import { SectionHeading } from "@/components/ui/section-heading"
import { getSessionUser, getTickets } from "@/lib/api/server"
import { seg } from "@/lib/api/query"
import type { TicketStatus } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { formatDate, formatNumber } from "@/lib/format"
import { firstParam, parsePage } from "@/lib/members"
import { sessionToken } from "@/lib/session"

export const metadata: Metadata = {
  title: "Tickets · SaucisseLand",
}

const LIMIT = 20
const FILTERS = [
  { key: "all", label: "Tous" },
  { key: "open", label: "Ouverts" },
  { key: "closed", label: "Fermés" },
] as const
type Filter = (typeof FILTERS)[number]["key"]

const STATUS: Record<TicketStatus, { label: string; color: string }> = {
  open: { label: "Ouvert", color: "var(--color-green)" },
  closed: { label: "Fermé", color: "var(--color-muted)" },
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <p className="mt-10 mb-0 rounded-2xl border border-line bg-[rgb(19_22_42/0.6)] px-6 py-5 text-muted" role="status">
      {children}
    </p>
  )
}

const href = (status: Filter, page: number) => `/tickets?status=${status}&page=${page}`

const TH = "px-4 py-3 font-semibold"

/**
 * Historique des tickets. `GET /tickets` et les transcriptions sont réservés aux administrateurs
 * (web-api répond 403 aux autres) : on ne l'appelle donc que pour eux.
 */
export default async function TicketsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}) {
  const sp = await searchParams
  const status: Filter = FILTERS.find(f => f.key === firstParam(sp.status))?.key ?? "all"
  const page = parsePage(firstParam(sp.page))

  const token = await sessionToken()
  const me = token ? await getSessionUser(token) : null
  const data = token && me?.is_admin ? await getTickets(token, status, page, LIMIT) : null

  return (
    <main className="relative pt-10 pb-24">
      <div className="relative mx-auto max-w-[1100px] px-6">
        <SectionHeading
          as="h1"
          title="Historique des tickets"
          sub={data ? `${formatNumber(data.total)} ticket${data.total > 1 ? "s" : ""}` : undefined}
        />
        {!me ? (
          <Note>Ton espace est injoignable pour l’instant. Reviens dans un moment.</Note>
        ) : !me.is_admin ? (
          <Note>L’historique des tickets est réservé à l’équipe de modération.</Note>
        ) : !data ? (
          <Note>L’historique est injoignable pour l’instant. Hermes recompte, reviens dans un moment.</Note>
        ) : (
          <>
            <nav aria-label="Filtrer par statut" className="mt-8 flex gap-2">
              {FILTERS.map(f => (
                <Link
                  key={f.key}
                  href={href(f.key, 1)}
                  prefetch={false}
                  aria-current={status === f.key ? "page" : undefined}
                  className={cn(
                    "rounded-full border px-4 py-1.5 text-sm font-semibold",
                    status === f.key
                      ? "border-violet bg-violet/10 text-violet"
                      : "border-line text-muted hover:border-violet/40 hover:text-fg",
                  )}
                >
                  {f.label}
                </Link>
              ))}
            </nav>
            {data.tickets.length === 0 ? (
              <Note>Aucun ticket trouvé.</Note>
            ) : (
              <div className="mt-6 overflow-x-auto rounded-[20px] border border-line bg-[rgb(19_22_42/0.92)]">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Tickets</caption>
                  <thead className="text-muted">
                    <tr className="border-b border-line">
                      <th scope="col" className={TH}>N°</th>
                      <th scope="col" className={TH}>Membre</th>
                      <th scope="col" className={TH}>Sujet</th>
                      <th scope="col" className={TH}>Statut</th>
                      <th scope="col" className={TH}>Ouvert le</th>
                      <th scope="col" className={TH}>Fermé le</th>
                      <th scope="col" className={TH}>Transcription</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.tickets.map(t => (
                      <tr key={t.id} className="border-b border-line/60 last:border-b-0">
                        <td className="px-4 py-3 font-mono text-muted">#{String(t.ticket_number).padStart(4, "0")}</td>
                        <td className="px-4 py-3 font-medium">{t.username}</td>
                        <td className="max-w-[260px] truncate px-4 py-3 text-muted">{t.subject || "—"}</td>
                        <td className="px-4 py-3">
                          <Chip color={STATUS[t.status]?.color}>{STATUS[t.status]?.label ?? t.status}</Chip>
                        </td>
                        <td className="px-4 py-3 text-muted">{t.created_at ? formatDate(t.created_at) : "—"}</td>
                        <td className="px-4 py-3 text-muted">{t.closed_at ? formatDate(t.closed_at) : "—"}</td>
                        <td className="px-4 py-3">
                          {t.has_transcript ? (
                            // Document HTML complet servi par web-api : ouvert tel quel dans un nouvel onglet.
                            <a
                              href={`/api/proxy/tickets/${seg(t.id)}/transcript`}
                              target="_blank"
                              rel="noopener noreferrer"
                              aria-label={`Transcription du ticket ${t.ticket_number} (nouvel onglet)`}
                              className="font-semibold text-cyan hover:underline"
                            >
                              Voir
                            </a>
                          ) : (
                            <span className="text-muted">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <RankPagination
              page={data.page}
              totalPages={Math.ceil(data.total / data.limit)}
              hrefFor={p => href(status, p)}
            />
          </>
        )}
      </div>
    </main>
  )
}
