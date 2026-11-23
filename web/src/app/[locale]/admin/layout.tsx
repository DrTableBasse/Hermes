import type { Metadata } from "next"
import { AdminDenied } from "@/components/admin/admin-denied"
import { AdminNav } from "@/components/admin/admin-nav"
import { adminGate } from "@/lib/admin-gate"

export const metadata: Metadata = {
  title: "Administration · SaucisseLand",
  robots: { index: false, follow: false },
}

/**
 * Cadre de l'administration. `src/proxy.ts` renvoie déjà l'absence de session à l'accueil ; ici, un
 * membre connecté sans `isAdmin` reçoit une page 403. Chaque page refait la vérification (navigation
 * entre sous-pages : le layout n'est pas rejoué), et web-api refuse de toute façon les routes admin.
 */
export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const gate = await adminGate()
  if (gate.kind !== "ok") {
    return (
      <main className="relative px-6 pt-10">
        <AdminDenied gate={gate} />
      </main>
    )
  }
  return (
    <main className="relative pt-10 pb-24">
      <div className="relative mx-auto grid max-w-[1200px] gap-8 px-6">
        <AdminNav />
        {children}
      </div>
    </main>
  )
}
