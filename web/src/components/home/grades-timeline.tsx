import type { CSSProperties } from "react"
import { Button } from "@/components/ui/button"
import { SectionHeading } from "@/components/ui/section-heading"
import type { Grade } from "@/lib/api/types"
import { formatNumber } from "@/lib/format"

/** Légendes des grades d'origine, par slug ; un grade ajouté depuis l'admin affiche son seuil. */
const CAPTIONS: Record<string, string> = {
  "recrue-cocktail": "dès ton arrivée",
  "caporal-chipolata": "quelques soirées",
  "sergent-merguez": "un habitué",
  "lieutenant-toulouse": "un pilier",
  "colonel-saucisson": "une légende locale",
  "general-saucisse": "on t’érige une statue",
}

const NUMBER_WORDS = ["Zéro", "Un", "Deux", "Trois", "Quatre", "Cinq", "Six", "Sept", "Huit", "Neuf", "Dix", "Onze", "Douze"]

function intro(n: number): string {
  const count = NUMBER_WORDS[n] ?? formatNumber(n)
  return `Chaque message et chaque minute en vocal te rapportent de l’XP. ${count} ${n > 1 ? "grades" : "grade"}, des quêtes chaque semaine, des succès à collectionner.`
}

/** Frise des grades (table `grades`), sans classement ; liste null ou vide → section masquée. */
export function GradesTimeline({ grades }: { grades: Grade[] | null }) {
  if (!grades || grades.length === 0) return null
  const sorted = [...grades].sort((a, b) => a.level_min - b.level_min)
  const rail = `linear-gradient(180deg, ${sorted.map(g => g.color).join(", ")})`

  return (
    <section className="relative pt-10 pb-24" aria-labelledby="grades-title">
      <div className="relative mx-auto grid max-w-[1440px] grid-cols-[minmax(0,1fr)_minmax(0,1fr)] items-center gap-10 px-6 max-[1000px]:grid-cols-[minmax(0,1fr)] min-[1100px]:px-20">
        <div>
          <SectionHeading id="grades-title" title="Monte en grade" sub={intro(sorted.length)} />
          <Button href="/progression" variant="ghost" className="mt-6 px-5 py-3 text-[15px]">
            Voir la progression
          </Button>
        </div>
        <ol className="relative m-0 grid list-none gap-2.5 p-0" aria-label={`Les ${sorted.length} grades`}>
          {sorted.length > 1 && (
            <span
              className="absolute top-[22px] bottom-[22px] left-[21px] w-0.5"
              style={{ background: rail }}
              aria-hidden="true"
            />
          )}
          {sorted.map(g => (
            <li
              key={g.slug}
              className="relative grid grid-cols-[44px_minmax(0,1fr)_auto] items-center gap-3.5"
              style={{ "--c": g.color } as CSSProperties}
              data-grade={g.slug}
            >
              <span
                className="grid size-11 place-items-center rounded-xl border-2 border-(--c) bg-bg font-display text-base font-extrabold text-[color-mix(in_oklab,var(--c)_60%,white)] shadow-[0_0_18px_color-mix(in_srgb,var(--c)_35%,transparent)]"
              >
                <span className="sr-only">Niveau </span>
                {g.level_min}
              </span>
              <b className="font-display text-lg text-[color-mix(in_oklab,var(--c)_60%,white)]">{g.name}</b>
              <small className="text-right text-[13px] text-muted">
                {CAPTIONS[g.slug] ?? `dès le niveau ${formatNumber(g.level_min)}`}
              </small>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}
