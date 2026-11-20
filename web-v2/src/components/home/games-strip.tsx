import Image from "next/image"
import type { CSSProperties } from "react"
import { Button } from "@/components/ui/button"
import { Chip } from "@/components/ui/chip"
import { Marquee } from "@/components/ui/marquee"
import { SectionHeading } from "@/components/ui/section-heading"
import type { Game } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { formatNumber } from "@/lib/format"
import { gameOfTheWeek } from "@/lib/games"

/** Texte de repli d'un jeu sans accroche saisie dans l'admin : aucune affirmation vérifiable. */
const DEFAULT_TAGLINE = "Des coéquipiers à trouver sur le Discord."

/** Accroche éditable (`site_games.tagline`), sinon le texte générique. */
const tagline = (g: Game) => g.tagline ?? DEFAULT_TAGLINE

const NUMBER_WORDS = ["Zéro", "Un", "Deux", "Trois", "Quatre", "Cinq", "Six", "Sept", "Huit", "Neuf", "Dix", "Onze", "Douze"]

function gamesIntro(n: number): string {
  const count = NUMBER_WORDS[n] ?? formatNumber(n)
  return `${count} ${n > 1 ? "jeux" : "jeu"}, un seul Discord. Chaque jeu a son salon, ses habitués et sa recherche de coéquipiers.`
}

/** Joueurs portant le rôle du jeu ; `null` quand le bot ne le sait pas (rien n'est affiché). */
function playersText(players: number | null, long: boolean): string | null {
  if (players === null) return null
  if (players === 0) return long ? "Personne pour l’instant : la place est libre" : "Place libre"
  const n = formatNumber(players)
  if (long) return players > 1 ? `${n} Généraux y jouent` : `${n} Général y joue`
  return players > 1 ? `${n} Généraux` : `${n} Général`
}

/** Visuel du jeu ; sans image, emplacement stylé à la couleur du jeu (jamais de logo inventé). */
function GameVisual({ game, className, sizes }: { game: Game; className?: string; sizes: string }) {
  return (
    <div
      className={cn(
        "relative overflow-hidden bg-linear-to-b from-(--g1) to-(--g2)",
        "after:absolute after:inset-x-0 after:top-[45%] after:bottom-0 after:bg-linear-to-b after:from-transparent after:to-[rgb(12_14_26/0.95)]",
        className,
      )}
      style={{ "--g1": game.color, "--g2": `color-mix(in srgb, ${game.color} 18%, #0C0E1A)` } as CSSProperties}
      data-game-visual={game.image ? "image" : "placeholder"}
    >
      {game.image ? (
        <Image src={game.image} alt="" fill sizes={sizes} unoptimized className="object-cover" />
      ) : (
        <>
          <span
            className="absolute inset-0 bg-[repeating-linear-gradient(135deg,rgb(255_255_255/0.05)_0_10px,transparent_10px_36px)]"
            aria-hidden="true"
          />
          <span className="absolute top-3.5 left-3.5 z-1 rounded-lg bg-black/35 px-2.5 py-1 text-[11px] font-medium text-white/85">
            Visuel à venir
          </span>
        </>
      )}
    </div>
  )
}

/** Lien « Trouver des joueurs » : forum du jeu, sinon l'invitation du serveur, sinon rien. */
const findPlayersHref = (g: Game, inviteUrl: string | null) => g.forum_url ?? inviteUrl

function FeaturedGame({ game, inviteUrl }: { game: Game; inviteUrl: string | null }) {
  const href = findPlayersHref(game, inviteUrl)
  const players = playersText(game.players, true)
  return (
    <article
      className="relative mt-12 min-h-[460px] overflow-hidden rounded-3xl shadow-[0_30px_60px_rgb(0_0_0/0.5)]"
      aria-labelledby="game-of-the-week"
      data-testid="featured-game"
    >
      <GameVisual game={game} className="absolute inset-0" sizes="(max-width: 1440px) 100vw, 1280px" />
      <div className="relative z-2 grid max-w-[680px] gap-3.5 px-12 pt-[190px] pb-11 max-[640px]:px-6 max-[640px]:pt-[150px]">
        <Chip color="var(--color-orange)" className="text-[13px]">
          Jeu de la semaine
        </Chip>
        <h3
          id="game-of-the-week"
          className="m-0 font-display text-[clamp(40px,5vw,60px)] leading-none font-extrabold tracking-[-0.03em] text-white"
        >
          {game.name}
        </h3>
        <p className="m-0 text-[17px] text-[#E6E2F5]">{tagline(game)}</p>
        <div className="flex flex-wrap items-center gap-3.5 text-sm font-medium text-[#E6E2F5]">
          {href && (
            <Button href={href} className="px-[22px] py-3.5 text-[15px]">
              Trouver des joueurs
            </Button>
          )}
          {players && <span>{players}</span>}
        </div>
      </div>
    </article>
  )
}

function GameCard({ game, inviteUrl }: { game: Game; inviteUrl: string | null }) {
  const href = findPlayersHref(game, inviteUrl)
  const players = playersText(game.players, false)
  return (
    <article
      className="grid w-[250px] flex-none grid-rows-[150px_auto] overflow-hidden rounded-[18px] border border-line bg-panel transition-[transform,border-color,box-shadow] duration-250 hover:-translate-y-1 hover:border-[color-mix(in_srgb,var(--g1)_60%,transparent)] hover:shadow-[0_18px_40px_color-mix(in_srgb,var(--g1)_25%,transparent)]"
      style={{ "--g1": game.color } as CSSProperties}
    >
      <GameVisual game={game} sizes="250px" />
      <div className="grid content-start gap-2 px-[18px] pt-3.5 pb-[18px]">
        <h4 className="m-0 font-display text-[19px] font-bold">{game.name}</h4>
        <p className="m-0 text-[13px] leading-[1.4] text-muted">{tagline(game)}</p>
        {players && <span className="text-xs font-semibold text-cyan">{players}</span>}
        {href && (
          <Button href={href} variant="ghost" size="sm" className="justify-self-start">
            Trouver des joueurs
          </Button>
        )}
      </div>
    </article>
  )
}

type GamesStripProps = {
  /** Liste éditable (`/games`) ; `null` ou vide → section masquée. */
  games: Game[] | null
  now: Date
  /** Repli du bouton « Trouver des joueurs » pour un jeu sans forum. */
  inviteUrl: string | null
}

export function GamesStrip({ games, now, inviteUrl }: GamesStripProps) {
  if (!games || games.length === 0) return null
  const featured = gameOfTheWeek(games, now)

  return (
    <section className="relative scroll-mt-[70px] pt-10 pb-24" id="jeux" aria-labelledby="jeux-title">
      <div className="pointer-events-none absolute inset-0 overflow-x-clip" aria-hidden="true">
        <div className="halo" style={{ left: "62%", top: 80, width: 600, height: 420, background: "rgb(63 224 240 / 0.10)" }} />
      </div>
      <div className="relative mx-auto max-w-[1440px] px-6 min-[1100px]:px-20">
        <SectionHeading id="jeux-title" title="Sur quoi on se retrouve" sub={gamesIntro(games.length)} />
        <FeaturedGame game={featured} inviteUrl={inviteUrl} />
        <Marquee
          className="mt-7"
          aria-label="Tous nos jeux"
          items={games.map(g => (
            <GameCard key={g.key} game={g} inviteUrl={inviteUrl} />
          ))}
        />
      </div>
    </section>
  )
}
