import { AdminDenied, AdminNote } from "@/components/admin/admin-denied"
import { GradesEditor } from "@/components/admin/grades-editor"
import { PageEditor } from "@/components/admin/page-editor"
import { SectionHeading } from "@/components/ui/section-heading"
import { adminGate } from "@/lib/admin-gate"
import { getGradesFresh, getPageFresh } from "@/lib/api/server"

/** Pages Markdown éditables (`site_pages`, migration 018). */
const PAGES = [
  { slug: "reglement", label: "Règlement" },
  { slug: "mentions-legales", label: "Mentions légales" },
] as const

export default async function AdminContentPage() {
  const gate = await adminGate("content.edit")
  if (gate.kind !== "ok") return <AdminDenied gate={gate} />
  const [pages, grades] = await Promise.all([
    Promise.all(PAGES.map(p => getPageFresh(p.slug, gate.token))),
    getGradesFresh(gate.token),
  ])

  return (
    <div className="grid gap-8">
      <SectionHeading as="h1" title="Contenus" sub="Textes du site en Markdown (le HTML n’est pas interprété) et grades de progression." />
      {PAGES.map((p, i) => {
        const page = pages[i]
        return page ? (
          <PageEditor key={p.slug} page={page} />
        ) : (
          <AdminNote key={p.slug} tone="error">
            {p.label} illisible pour l’instant.
          </AdminNote>
        )
      })}
      {grades ? <GradesEditor grades={grades} /> : <AdminNote tone="error">Grades illisibles pour l’instant.</AdminNote>}
    </div>
  )
}
