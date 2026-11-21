import Link from "next/link"
import { cn } from "@/lib/cn"
import { pageWindow } from "@/lib/members"

type RankPaginationProps = {
  page: number
  totalPages: number
  /** URL de la page `p` (onglet et recherche conservés par l'appelant). */
  hrefFor: (p: number) => string
}

const base = "flex h-9 min-w-9 items-center justify-center rounded-lg border px-2 text-sm tabular-nums"

export function RankPagination({ page, totalPages, hrefFor }: RankPaginationProps) {
  if (totalPages <= 1) return null
  const step = (label: string, aria: string, target: number, disabled: boolean) =>
    disabled ? (
      <span aria-hidden="true" className={cn(base, "border-line text-muted/40")}>
        {label}
      </span>
    ) : (
      <Link href={hrefFor(target)} prefetch={false} aria-label={aria} className={cn(base, "border-line text-muted hover:border-violet/40 hover:text-fg")}>
        {label}
      </Link>
    )
  return (
    <nav aria-label="Pagination du classement" className="mt-6 flex flex-wrap items-center justify-center gap-1">
      {step("‹", "Page précédente", page - 1, page <= 1)}
      {pageWindow(page, totalPages).map((p, i) =>
        p === "gap" ? (
          <span key={`gap-${i}`} className="px-1 text-muted" aria-hidden="true">
            …
          </span>
        ) : (
          <Link
            key={p}
            href={hrefFor(p)}
            prefetch={false}
            aria-current={p === page ? "page" : undefined}
            className={cn(
              base,
              p === page
                ? "border-violet bg-violet/10 text-violet"
                : "border-line text-muted hover:border-violet/40 hover:text-fg",
            )}
          >
            {p}
          </Link>
        ),
      )}
      {step("›", "Page suivante", page + 1, page >= totalPages)}
    </nav>
  )
}
