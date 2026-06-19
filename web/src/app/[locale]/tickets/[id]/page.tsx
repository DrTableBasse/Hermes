import { headers } from 'next/headers'
import Link from 'next/link'
import { notFound, redirect } from 'next/navigation'
import { auth } from '@/lib/auth'
import { serverGetTicket } from '@/lib/server-api'
import TicketChat from './TicketChat'

const STATUS_LABEL: Record<string, string> = {
  open:     '🟢 Ouvert',
  resolved: '🟡 Résolu',
  closed:   '⚪ Fermé',
}

export default async function TicketDetailPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>
}) {
  const { locale, id } = await params
  const ticketId = Number(id)
  if (isNaN(ticketId)) notFound()

  const session = await auth.api.getSession({ headers: await headers() })
  const u = session?.user as any
  if (!u) redirect(`/${locale}/login`)

  const token = (session!.session as any).token as string
  let ticket
  try {
    ticket = await serverGetTicket(ticketId, token)
  } catch {
    notFound()
  }

  const isAdmin = !!u.isAdmin

  return (
    <div className="container mx-auto px-4 py-12 max-w-3xl">
      <Link
        href={`/${locale}/tickets`}
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-8 transition-colors"
      >
        ← Retour aux tickets
      </Link>

      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-2xl font-extrabold tracking-tight">
            🎫 Ticket #{ticket.id}
          </h1>
          <span className="text-sm font-medium text-muted-foreground">
            {STATUS_LABEL[ticket.status]}
          </span>
        </div>
        <p className="text-lg text-muted-foreground">{ticket.title}</p>
        <p className="text-xs text-muted-foreground mt-1">
          Ouvert le {new Date(ticket.created_at).toLocaleDateString('fr-FR')}
          {ticket.created_by_admin && ' · créé par un admin'}
        </p>
      </div>

      <TicketChat ticket={ticket} isAdmin={isAdmin} locale={locale} />
    </div>
  )
}
