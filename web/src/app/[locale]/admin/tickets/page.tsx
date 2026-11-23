import Link from "next/link"
import { AdminDenied, AdminNote } from "@/components/admin/admin-denied"
import { RankPagination } from "@/components/members/rank-pagination"
import { Chip } from "@/components/ui/chip"
import { SectionHeading } from "@/components/ui/section-heading"
import { adminGate } from "@/lib/admin-gate"
import { seg } from "@/lib/api/query"
import { getTickets } from "@/lib/api/server"
import type { TicketStatus } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { formatDate, formatNumber } from "@/lib/format"
import { firstParam, parsePage } from "@/lib/members"

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

const href = (status: Filter, page: number) => `/admin/tickets?status=${status}&page=${page}`
const TH = "px-4 py-3 font-semibold"

/** Historique global des tickets (`GET /tickets`, administrateurs) et transcriptions. */
export default async function AdminTicketsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}) {
  const gate = await adminGate()
  if (gate.kind !== "ok") return <AdminDenied gate={gate} />
  const sp = await searchParams
  const status: Filter = FILTERS.find(f => f.key === firstParam(sp.status))?.key ?? "all"
  const page = parsePage(firstParam(sp.page))
  const data = await getTickets(gate.token, status, page, LIMIT)

  return (
    <div className="grid gap-6">
      <SectionHeading
        as="h1"
        title="Tickets"
        sub={data ? `${formatNumber(data.total)} ticket${data.total > 1 ? "s" : ""}` : undefined}
      />
      <nav aria-label="Filtrer par statut" className="flex gap-2">
        {FILTERS.map(f => (
          <Link
            key={f.key}
            href={href(f.key, 1)}
            prefetch={false}
            aria-current={status === f.key ? "page" : undefined}
            className={cn(
              "rounded-full border px-4 py-1.5 text-sm font-semibold",
              status === f.key ? "border-violet bg-violet/10 text-violet" : "border-line text-muted hover:border-violet/40 hover:text-fg",
            )}
          >
            {f.label}
          </Link>
        ))}
      </nav>
      {!data ? (
        <AdminNote tone="error">L’historique des tickets est injoignable pour l’instant.</AdminNote>
      ) : data.tickets.length === 0 ? (
        <AdminNote>Aucun ticket trouvé.</AdminNote>
      ) : (
        <div className="overflow-x-auto rounded-[20px] border border-line bg-[rgb(19_22_42/0.92)]">
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
      {data && (
        <RankPagination
          page={data.page}
          totalPages={Math.ceil(data.total / data.limit)}
          hrefFor={p => href(status, p)}
          label="Pagination des tickets"
        />
      )}
    </div>
  )
}
