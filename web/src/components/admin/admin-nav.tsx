"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/cn"
import { allowedSections } from "@/lib/admin-sections"

/**
 * Sous-navigation de l'administration : seules les sections que `permissions` (droits effectifs de la
 * session) ouvrent ; la page courante est marquée `aria-current`.
 */
export function AdminNav({ permissions }: { permissions: readonly string[] }) {
  const pathname = (usePathname() ?? "").replace(/^\/fr(?=\/|$)/, "") || "/"
  return (
    <nav aria-label="Administration" className="-mx-1 flex gap-1.5 overflow-x-auto pb-2">
      {allowedSections(permissions).map(s => {
        const current = s.href === "/admin" ? pathname === "/admin" : pathname.startsWith(s.href)
        return (
          <Link
            key={s.href}
            href={s.href}
            prefetch={false}
            aria-current={current ? "page" : undefined}
            className={cn(
              "shrink-0 rounded-full border px-3.5 py-1.5 text-sm font-semibold whitespace-nowrap",
              current
                ? "border-violet bg-violet/10 text-violet"
                : "border-line text-muted hover:border-violet/40 hover:text-fg",
            )}
          >
            {s.label}
          </Link>
        )
      })}
    </nav>
  )
}
