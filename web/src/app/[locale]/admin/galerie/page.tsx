import { AdminDenied, AdminNote } from "@/components/admin/admin-denied"
import { GalleryModeration } from "@/components/admin/gallery-moderation"
import { SectionHeading } from "@/components/ui/section-heading"
import { adminGate } from "@/lib/admin-gate"
import { getAdminGallery } from "@/lib/api/server"

export default async function AdminGalleryPage() {
  const gate = await adminGate()
  if (gate.kind !== "ok") return <AdminDenied gate={gate} />
  const items = await getAdminGallery(gate.token)

  return (
    <div className="grid gap-8">
      <SectionHeading
        as="h1"
        title="Galerie"
        sub="Un élément masqué disparaît du site sans être effacé ; une suppression efface aussi le fichier."
      />
      {items ? <GalleryModeration items={items} /> : <AdminNote tone="error">Galerie illisible pour l’instant.</AdminNote>}
    </div>
  )
}
