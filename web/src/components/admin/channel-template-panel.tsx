"use client"

import { useId, useState } from "react"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api/client"
import type {
  ChannelRole,
  ChannelTemplateName,
  ManagedChannel,
  OverwriteBits,
  OverwriteChange,
  TemplateApplyResult,
  TemplatePreviewResult,
} from "@/lib/api/types"
import { plural } from "@/lib/jobs"
import { channelActionErrorText } from "./form"

export const TEMPLATE_LABELS: Record<ChannelTemplateName, string> = {
  public: "Public",
  role_required: "Rôle requis",
  announcements: "Annonces",
  staff: "Staff",
}

const TEMPLATE_HINTS: Record<ChannelTemplateName, string> = {
  public: "visible et ouvert à tous",
  role_required: "caché, sauf pour les rôles choisis",
  announcements: "lecture pour tous, écriture pour les rôles choisis",
  staff: "réservé aux rôles Staff (administrateurs)",
}

/** Modèles qui demandent des rôles R. */
const WITH_ROLES: ReadonlySet<ChannelTemplateName> = new Set(["role_required", "announcements"])

/** Permissions Discord (noms de discord.py) en français ; un nom inconnu est affiché tel quel. */
const PERMISSION_LABELS: Record<string, string> = {
  view_channel: "voir",
  send_messages: "écrire",
  send_messages_in_threads: "écrire dans les fils",
  create_public_threads: "créer des fils publics",
  create_private_threads: "créer des fils privés",
  connect: "se connecter",
  speak: "parler",
  manage_messages: "gérer les messages",
  manage_channels: "gérer le salon",
  manage_permissions: "gérer les permissions",
  manage_roles: "gérer les permissions",
  manage_threads: "gérer les fils",
  read_message_history: "lire l’historique",
  add_reactions: "réagir",
  attach_files: "joindre des fichiers",
  embed_links: "intégrer des liens",
  mention_everyone: "mentionner tout le monde",
}
const permLabel = (name: string) => PERMISSION_LABELS[name] ?? name

/** État d'une permission dans une surcharge : oui (autorisée), non (refusée), — (héritée). */
function state(bits: OverwriteBits | null, perm: string): string {
  if (bits?.allow.includes(perm)) return "oui"
  if (bits?.deny.includes(perm)) return "non"
  return "—"
}

/** « voir oui, écrire non » pour un ajout ; « voir oui → non » pour une modification. */
export function describeChange(change: OverwriteChange): string {
  if (change.action === "remove") return "surcharge retirée"
  const perms = [
    ...new Set([
      ...(change.before?.allow ?? []),
      ...(change.before?.deny ?? []),
      ...(change.after?.allow ?? []),
      ...(change.after?.deny ?? []),
    ]),
  ]
  if (change.action === "add") return perms.map(p => `${permLabel(p)} ${state(change.after, p)}`).join(", ")
  return perms
    .filter(p => state(change.before, p) !== state(change.after, p))
    .map(p => `${permLabel(p)} ${state(change.before, p)} → ${state(change.after, p)}`)
    .join(", ")
}

const SIGN: Record<OverwriteChange["action"], string> = { add: "+", update: "~", remove: "−" }
const ACTION_TEXT: Record<OverwriteChange["action"], string> = { add: "ajout", update: "modification", remove: "retrait" }

/** Préfixe des salons dans l'interface. */
export const channelPrefix = (type: ManagedChannel["type"]) =>
  type === "category" ? "" : type === "voice" ? "🔊 " : type === "forum" ? "💬 " : type === "announcement" ? "📢 " : "# "

/** Surcharges ajoutées, modifiées ou retirées par salon (avant → après). */
export function PreviewChanges({ preview }: { preview: TemplatePreviewResult }) {
  const touched = preview.channels.filter(c => c.changes.length > 0)
  if (touched.length === 0) {
    return <p className="m-0 text-sm text-muted">Aucune surcharge à changer : les salons ont déjà ces accès.</p>
  }
  return (
    <ul className="m-0 grid list-none gap-3 p-0" aria-label="Aperçu des changements">
      {touched.map(c => (
        <li key={c.id} className="grid gap-1">
          <span className="text-sm font-semibold">
            {channelPrefix(c.type)}
            {c.name}
          </span>
          <ul className="m-0 grid list-none gap-0.5 p-0 font-mono text-[13px]">
            {c.changes.map(ch => (
              <li key={`${ch.target_type}-${ch.target_id}`}>
                <span aria-hidden="true" className={ch.action === "remove" ? "text-orange" : ch.action === "add" ? "text-green" : "text-violet"}>
                  {SIGN[ch.action]}{" "}
                </span>
                <span className="sr-only">{ACTION_TEXT[ch.action]} : </span>
                {ch.target_name} : {describeChange(ch)}
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ul>
  )
}

/** Résultat d'une application : réussite, échecs par salon, mémorisation manquée (avertissement). */
export function applyOutcome(result: TemplateApplyResult): { ok: string; problems: string[] } {
  const problems = result.failed.map(f => `« ${f.name} » : ${f.error}`)
  if (result.memo_failed.length > 0) {
    problems.push(
      `${plural(result.memo_failed.length, "salon")} appliqué(s) sur Discord, mais non mémorisé(s) pour la resynchronisation Staff.`,
    )
  }
  return { ok: `Accès appliqué à ${plural(result.applied, "salon")}.`, problems }
}

type Props = {
  channel: ManagedChannel
  /** Salons de la catégorie (0 pour un salon). */
  childCount: number
  templates: ChannelTemplateName[]
  roles: ChannelRole[]
  /** Appelé après une application (même partielle) : message, avertissements ; relire l'arbre. */
  onApplied: (message: string, problems: string[]) => void | Promise<void>
}

/** Choix d'un modèle d'accès, aperçu des surcharges puis application confirmée par le jeton d'aperçu. */
export function ChannelTemplatePanel({ channel, childCount, templates, roles, onApplied }: Props) {
  const ids = useId()
  const current = channel.template
  const [template, setTemplate] = useState<ChannelTemplateName | null>(
    current && templates.includes(current.template) ? current.template : null,
  )
  const [chosen, setChosen] = useState<string[]>(current?.roles.filter(r => roles.some(x => x.id === r && x.assignable)) ?? [])
  const [sync, setSync] = useState(false)
  const [preview, setPreview] = useState<TemplatePreviewResult | null>(null)
  const [busy, setBusy] = useState<"preview" | "apply" | null>(null)
  const [error, setError] = useState<string | null>(null)

  const choices = roles.filter(r => r.assignable && !r.managed && r.name !== "@everyone")
  const needsRoles = template !== null && WITH_ROLES.has(template)
  const isCategory = channel.type === "category"

  /** Tout changement de choix invalide l'aperçu (son jeton ne vaut que pour ces paramètres). */
  function reset() {
    setPreview(null)
    setError(null)
  }

  const input = () => ({ template: template!, roles: needsRoles ? chosen : [], sync_children: isCategory && sync })

  async function runPreview() {
    if (!template) return setError("Choisissez un modèle.")
    if (needsRoles && chosen.length === 0) return setError("Choisissez au moins un rôle.")
    setError(null)
    setBusy("preview")
    try {
      setPreview(await api.admin.previewChannelTemplate(channel.id, input()))
    } catch (e) {
      setError(channelActionErrorText(e))
    } finally {
      setBusy(null)
    }
  }

  async function apply() {
    if (!preview) return
    setError(null)
    setBusy("apply")
    try {
      const result = await api.admin.applyChannelTemplate(channel.id, { ...input(), token: preview.token })
      const { ok, problems } = applyOutcome(result)
      setPreview(null)
      await onApplied(ok, problems)
    } catch (e) {
      // 409 : l'état a changé depuis l'aperçu ; il faut le refaire.
      setPreview(null)
      setError(channelActionErrorText(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <section aria-labelledby={`${ids}-title`} className="grid gap-4 rounded-[20px] border border-line bg-[rgb(19_22_42/0.92)] px-5 py-4">
      <h3 id={`${ids}-title`} className="m-0 font-display text-base font-bold">
        Accès à « {channelPrefix(channel.type)}
        {channel.name} »
      </h3>
      <fieldset className="m-0 grid gap-2 border-0 p-0">
        <legend className="mb-1 text-sm font-semibold">Modèle</legend>
        {templates.map(t => (
          <label key={t} className="flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="radio"
              name={`${ids}-template`}
              value={t}
              checked={template === t}
              onChange={() => {
                setTemplate(t)
                reset()
              }}
              className="size-4 accent-violet"
            />
            <span>
              <span className="font-semibold">{TEMPLATE_LABELS[t]}</span> <span className="text-muted">— {TEMPLATE_HINTS[t]}</span>
            </span>
          </label>
        ))}
      </fieldset>

      {needsRoles && (
        <div className="grid gap-1.5">
          <span id={`${ids}-roles`} className="text-sm font-semibold">
            Rôles ({template === "announcements" ? "peuvent écrire" : "voient le salon"})
          </span>
          {choices.length === 0 ? (
            <p className="m-0 text-sm text-muted">Aucun rôle sous le vôtre à choisir.</p>
          ) : (
            <div
              role="group"
              aria-labelledby={`${ids}-roles`}
              className="grid max-h-56 w-full max-w-md gap-1 overflow-y-auto rounded-xl border border-white/14 bg-[rgb(12_14_26/0.6)] p-2"
            >
              {choices.map(r => (
                <label key={r.id} className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-white/6">
                  <input
                    type="checkbox"
                    checked={chosen.includes(r.id)}
                    onChange={e => {
                      setChosen(c => (e.target.checked ? [...c, r.id] : c.filter(x => x !== r.id)))
                      reset()
                    }}
                    className="size-4 accent-violet"
                  />
                  @{r.name}
                </label>
              ))}
            </div>
          )}
          <p className="m-0 text-xs text-muted">Seuls les rôles sous le vôtre sont proposés.</p>
        </div>
      )}

      {isCategory && (
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={sync}
            onChange={e => {
              setSync(e.target.checked)
              reset()
            }}
            className="size-4 accent-violet"
          />
          Appliquer aussi aux salons de la catégorie ({childCount})
        </label>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button size="sm" variant="ghost" disabled={busy !== null} onClick={() => void runPreview()}>
          {busy === "preview" ? "Aperçu en cours…" : "Voir l’aperçu"}
        </Button>
      </div>

      {preview && (
        <div className="grid gap-3 rounded-xl border border-white/10 px-4 py-3">
          <h4 className="m-0 text-sm font-semibold">Aperçu ({plural(preview.count, "salon")})</h4>
          <PreviewChanges preview={preview} />
          <p className="m-0 text-xs text-muted">
            Les surcharges des membres et des autres rôles ne sont pas touchées.
          </p>
          <div>
            <Button size="sm" disabled={busy !== null} onClick={() => void apply()}>
              {preview.count > 1 ? `Appliquer aux ${preview.count} salons` : "Appliquer"}
            </Button>
          </div>
        </div>
      )}

      <p role="status" className="m-0 text-sm text-muted">
        {busy === "apply" ? "Application en cours… (jusqu’à une minute pour une grande catégorie)" : ""}
      </p>
      {error && (
        <p role="alert" className="m-0 text-sm text-orange">
          {error}
        </p>
      )}
    </section>
  )
}
