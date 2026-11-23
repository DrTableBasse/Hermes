import Link from "next/link"
import { AdminDenied, AdminNote } from "@/components/admin/admin-denied"
import { ADMIN_SECTIONS } from "@/components/admin/admin-nav"
import { KEY_SETTINGS, settingState } from "@/components/admin/key-settings"
import { Chip } from "@/components/ui/chip"
import { Panel } from "@/components/ui/panel"
import { SectionHeading } from "@/components/ui/section-heading"
import { adminGate } from "@/lib/admin-gate"
import { getAdminSettings, getAdminStats } from "@/lib/api/server"
import { formatNumber } from "@/lib/format"

const SECTION_HINTS: Record<string, string> = {
  "/admin/reglages": "Salons, rôles, lien d’invitation : tout ce que Hermes lit au démarrage.",
  "/admin/moderation": "Avertir, exclure, bannir ; sanctions et journal des actions.",
  "/admin/commandes": "Activer ou couper une commande slash.",
  "/admin/quetes": "Bibliothèque de quêtes et quêtes de la semaine.",
  "/admin/tickets": "Historique de tous les tickets et transcriptions.",
  "/admin/galerie": "Masquer ou supprimer une image, un clip.",
  "/admin/etat-major": "Phrase et jeux des cartes du staff.",
  "/admin/jeux": "Jeux de la communauté : ordre, couleur, visuel, rôle.",
  "/admin/contenus": "Règlement, mentions légales, grades.",
  "/admin/analytique": "Sanctions, niveaux, quêtes et XP en un coup d’œil.",
}

export default async function AdminHome() {
  const gate = await adminGate()
  if (gate.kind !== "ok") return <AdminDenied gate={gate} />
  const [stats, settings] = await Promise.all([getAdminStats(gate.token), getAdminSettings(gate.token)])
  const items = settings?.groups.flatMap(g => g.items) ?? []

  return (
    <div className="grid gap-10">
      <SectionHeading as="h1" title="Administration" sub="Réglages du serveur et du site, modération, contenus." />

      {stats ? (
        <dl className="m-0 grid grid-cols-2 gap-4 md:grid-cols-4">
          {[
            ["Membres", stats.members],
            ["Messages", stats.total_messages],
            ["Sanctions", stats.total_warns],
            ["Articles", stats.total_articles],
          ].map(([label, value]) => (
            <Panel key={label} className="grid gap-1 p-5">
              <dt className="text-sm text-muted">{label}</dt>
              <dd className="m-0 font-display text-3xl font-extrabold tabular-nums">{formatNumber(Number(value))}</dd>
            </Panel>
          ))}
        </dl>
      ) : (
        <AdminNote tone="error">Statistiques du serveur indisponibles pour l’instant.</AdminNote>
      )}

      <section aria-labelledby="key-settings" className="grid gap-4">
        <h2 id="key-settings" className="m-0 font-display text-2xl font-extrabold">
          Réglages à vérifier
        </h2>
        {!settings ? (
          <AdminNote tone="error">Réglages illisibles pour l’instant.</AdminNote>
        ) : (
          <ul className="m-0 grid list-none gap-3 p-0 md:grid-cols-3">
            {KEY_SETTINGS.map(k => {
              const item = items.find(i => i.key === k.key)
              const state = settingState(item)
              return (
                <li key={k.key}>
                  <Panel className="grid h-full gap-2 p-5">
                    <Chip color={state.ok ? "var(--color-green)" : "var(--color-orange)"}>{state.label}</Chip>
                    <Link href={`/admin/reglages#setting-${k.key}`} prefetch={false} className="font-semibold text-fg hover:text-cyan">
                      {item?.label ?? k.key}
                    </Link>
                    <p className="m-0 text-sm text-muted">{k.why}</p>
                  </Panel>
                </li>
              )
            })}
          </ul>
        )}
      </section>

      <section aria-labelledby="sections" className="grid gap-4">
        <h2 id="sections" className="m-0 font-display text-2xl font-extrabold">
          Outils
        </h2>
        <ul className="m-0 grid list-none gap-3 p-0 sm:grid-cols-2 lg:grid-cols-3">
          {ADMIN_SECTIONS.filter(s => s.href !== "/admin").map(s => (
            <li key={s.href}>
              <Link href={s.href} prefetch={false} className="block h-full">
                <Panel className="grid h-full gap-1.5 p-5">
                  <span className="font-display text-lg font-bold">{s.label}</span>
                  <span className="text-sm text-muted">{SECTION_HINTS[s.href]}</span>
                </Panel>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
