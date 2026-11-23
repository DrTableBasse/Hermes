import type { CSSProperties, ReactNode } from "react"
import { Hash, Volume2 } from "lucide-react"
import { Avatar } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Chip } from "@/components/ui/chip"
import { DiscordEmbed, DiscordMessage, DiscordWindow } from "@/components/ui/discord-window"
import { GradeBadge } from "@/components/ui/grade-badge"
import { XpBar } from "@/components/ui/xp-bar"
import type { Grade, LiveState } from "@/lib/api/types"
import { cn } from "@/lib/cn"
import { formatClock, formatNumber, xpProgress } from "@/lib/format"

type HeroProps = {
  /** `null` : API muette, compteurs affichés « — ». */
  live: LiveState | null
  /** `null` : grades illisibles, chips et grades de la scène masqués. */
  grades: Grade[] | null
  /** Nombre de jeux de la liste éditable ; `null` si elle est indisponible. */
  gamesCount: number | null
  /** `invite_url` des réglages publics ; `null` : bouton désactivé avec un texte explicite. */
  inviteUrl: string | null
}

/** Grade d'un niveau d'après la table `grades` (seuils `level_min`), `null` sans grade applicable. */
export function gradeForLevel(grades: Grade[] | null, level: number): Grade | null {
  if (!grades) return null
  let found: Grade | null = null
  for (const g of [...grades].sort((a, b) => a.level_min - b.level_min)) {
    if (g.level_min <= level) found = g
  }
  return found
}

function nextGrade(grades: Grade[] | null, level: number): Grade | null {
  return grades?.filter(g => g.level_min > level).sort((a, b) => a.level_min - b.level_min)[0] ?? null
}

// ── Décor : sol en grille, particules, liens de la constellation (coordonnées du cadre 1440 × 900) ──

/** Générateur pseudo-aléatoire à graine fixe : mêmes particules au serveur et à chaque rendu. */
function seeded(seed: number) {
  let s = seed
  return () => (s = (s * 16807) % 2147483647) / 2147483647
}

const DOTS = (() => {
  const r = seeded(11)
  return Array.from({ length: 46 }, () => {
    const size = 1.5 + r() * 3
    return { left: r() * 100, top: r() * 900, size, cyan: r() > 0.5, opacity: 0.2 + r() * 0.5 }
  })
})()

function Horizon() {
  const radials = Array.from({ length: 25 }, (_, k) => k - 12)
  const rows = Array.from({ length: 8 }, (_, j) => j)
  return (
    <svg
      className="absolute inset-x-0 bottom-0 h-[340px] w-full [mask-image:linear-gradient(transparent,#000_30%,#000_60%,transparent)] max-[1099px]:h-[200px]"
      viewBox="0 0 1440 340"
      preserveAspectRatio="none"
      data-testid="hero-horizon"
    >
      {radials.map(i => (
        <line key={`r${i}`} x1={720 + i * 60} y1="0" x2={720 + i * 260} y2="340" stroke="#9B6BFF" strokeOpacity=".2" />
      ))}
      {rows.map(j => {
        const y = Math.round(Math.pow(j / 7, 1.8) * 340)
        return <line key={`h${j}`} x1="0" y1={y} x2="1440" y2={y} stroke="#9B6BFF" strokeOpacity={0.06 + j * 0.022} />
      })}
    </svg>
  )
}

const LINK_CENTER = [1080, 460] as const
const LINK_POINTS = [
  [760, 140],
  [1290, 486],
  [1390, 116],
  [880, 716],
  [925, 842],
  [1350, 852],
] as const

function ConstellationLinks() {
  return (
    <svg
      className="pointer-events-none absolute inset-0 z-1 size-full max-[1099px]:hidden"
      viewBox="0 0 1440 900"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      {LINK_POINTS.map(([x, y]) => (
        <g key={`${x}-${y}`}>
          <line
            x1={LINK_CENTER[0]}
            y1={LINK_CENTER[1]}
            x2={x}
            y2={y}
            stroke="#3FE0F0"
            strokeOpacity=".22"
            strokeWidth="1.2"
            strokeDasharray="4 6"
          />
          <circle cx={x} cy={y} r="2.5" fill="#3FE0F0" fillOpacity=".7" />
        </g>
      ))}
    </svg>
  )
}

// ── Scène : éléments posés en absolu sur grand écran, empilés en dessous de 1100 px ──

type Placed = { x: number; y: number; rotate?: number; duration?: number; delay?: number }

function placed({ x, y, rotate, duration, delay }: Placed): CSSProperties {
  return {
    left: `${(x / 1440) * 100}%`,
    top: y,
    rotate: rotate ? `${rotate}deg` : undefined,
    animationDuration: duration ? `${duration}s` : undefined,
    animationDelay: delay ? `${delay}s` : undefined,
  }
}

const onStage = "min-[1100px]:absolute max-[1099px]:relative max-[1099px]:left-auto! max-[1099px]:top-auto! max-[1099px]:rotate-0!"
/** Éléments réservés au grand écran (satellites, fenêtre vocale). */
const desktopOnly = "max-[1099px]:hidden"

function Satellite({ at, className, style, children }: { at: Placed; className?: string; style?: CSSProperties; children: ReactNode }) {
  return (
    <span
      className={cn(
        onStage,
        desktopOnly,
        "inline-flex items-center gap-2 rounded-xl border border-white/10 bg-[rgb(23_26_46/0.88)] py-2 pr-3.5 pl-3 text-[13px] font-medium whitespace-nowrap shadow-[0_14px_30px_rgb(0_0_0/0.45)]",
        className,
      )}
      style={{ ...placed(at), ...style }}
    >
      {children}
    </span>
  )
}

function VoiceMember({ name, color, grade, speaking }: { name: string; color: string; grade: Grade | null; speaking?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <Avatar name={name} color={color} size={32} ring={speaking ? "var(--color-green)" : undefined} />
      <div>
        <b className="block text-sm font-semibold">{name}</b>
        {grade && <small className="block text-xs text-muted">{grade.name}</small>}
      </div>
    </div>
  )
}

function Scene({ grades }: { grades: Grade[] | null }) {
  // Scène d'illustration : personnages, messages et niveaux inventés. Une pastille « Exemple » posée sur le
  // cadre couvre toute la scène (et reste visible en mobile, où elle ouvre la pile).
  const profileLevel = 12
  const profileXp = 15_950
  const profileGrade = gradeForLevel(grades, profileLevel)
  const profileNext = nextGrade(grades, profileLevel)
  const promoted = gradeForLevel(grades, 5)

  return (
    <div
      className="pointer-events-auto relative z-2 min-[1100px]:absolute min-[1100px]:inset-0 max-[1099px]:mt-12 max-[1099px]:grid max-[1099px]:max-w-[520px] max-[1099px]:gap-[18px]"
      data-testid="hero-scene"
    >
      <span className={cn(onStage, "z-3 justify-self-start")} style={placed({ x: 1180, y: 96 })}>
        <Chip example className="bg-bg/80">
          Exemple
        </Chip>
      </span>
      <DiscordWindow
        title="Cantine des Généraux, vocal"
        icon={<Volume2 />}
        className={cn(onStage, desktopOnly, "w-[330px] animate-float")}
        style={placed({ x: 1050, y: 140, rotate: 4, duration: 8 })}
      >
        <VoiceMember name="Merguez_Royale" color="#C2553A" grade={gradeForLevel(grades, 30)} speaking />
        <VoiceMember name="Chipolata" color="#4F6FB8" grade={gradeForLevel(grades, 18)} speaking />
        <VoiceMember name="Kéfir" color="#3E8A5C" grade={gradeForLevel(grades, profileLevel)} />
        <VoiceMember name="Boudin_Blanc" color="#9A6B2F" grade={gradeForLevel(grades, 9)} />
        <small className="text-xs font-medium text-cyan">en jeu : Dead by Daylight, moral au beau fixe</small>
      </DiscordWindow>

      <DiscordWindow
        title="général"
        icon={<Hash />}
        className={cn(onStage, "w-[470px] max-w-full animate-float")}
        style={placed({ x: 760, y: 260, rotate: -3, duration: 9, delay: -2 })}
      >
        <DiscordMessage author="Chipolata" avatarColor="#4F6FB8" nameColor="#8FB1FF" time="21:02">
          qui pour une DBD ce soir ? il nous manque un survivant
        </DiscordMessage>
        <DiscordMessage author="Merguez_Royale" avatarColor="#C2553A" nameColor="#FF9A7A" time="21:03">
          j&apos;arrive, je ramène la moutarde et le killer
        </DiscordMessage>
        <DiscordMessage author="Hermes" avatarColor="var(--color-violet)" nameColor="#C9B5FF" time="21:04" bot>
          <DiscordEmbed title="Promotion !">
            <p className="m-0">
              Andouillette passe {promoted ? `${promoted.name} ` : ""}(niveau 5). Médaille en papier alu envoyée en MP.
              Repos, soldat.
            </p>
            <XpBar ratio={0.62} label="Progression d'Andouillette vers le niveau 6" />
          </DiscordEmbed>
        </DiscordMessage>
        <DiscordMessage author="Boudin_Blanc" avatarColor="#9A6B2F" nameColor="#E6B877" time="21:04">
          GG mon caporal, je vous salue de la fourchette
        </DiscordMessage>
      </DiscordWindow>

      <div
        className={cn(
          onStage,
          "grid w-[370px] max-w-full animate-float gap-3.5 rounded-[18px] border border-violet/35 bg-[rgb(23_26_46/0.92)] px-[22px] py-5 shadow-[0_24px_50px_rgb(0_0_0/0.5),0_0_40px_rgb(155_107_255/0.25)]",
        )}
        style={placed({ x: 1010, y: 620, rotate: 2, duration: 7.5, delay: -4 })}
      >
        <div className="flex items-center gap-3.5">
          <Avatar name="Kéfir" color="#3E8A5C" size={56} ring="var(--color-violet)" />
          <div className="grid gap-1">
            <b className="font-display text-xl">Kéfir</b>
            {profileGrade && <GradeBadge grade={profileGrade} />}
          </div>
        </div>
        <XpBar ratio={xpProgress(profileXp).ratio} height={10} sausage label="Progression de Kéfir vers le niveau 13" />
        <p className="m-0 text-[13px] text-muted">
          Niveau {profileLevel}, {formatNumber(profileXp)} XP.
          {profileNext && ` Prochain grade : ${profileNext.name}`}
        </p>
        <div className="flex flex-wrap gap-2">
          <Chip color="var(--color-muted)">Commun</Chip>
          <Chip color="var(--color-blue)">Rare</Chip>
          <Chip color="var(--color-violet)">Épique</Chip>
          <Chip color="var(--color-orange)">Légendaire</Chip>
        </div>
      </div>

      <Satellite at={{ x: 700, y: 128 }} className="font-semibold text-orange">
        Série de 9 jours, cuisson parfaite
      </Satellite>
      <Satellite at={{ x: 1250, y: 470 }} className="font-display text-sm font-bold text-cyan">
        +150 XP
      </Satellite>
      {/* L'Avatar fixe déjà sa taille en style : la position passe par une enveloppe. */}
      <span className={cn(onStage, desktopOnly)} style={placed({ x: 1370, y: 96 })}>
        <Avatar name="Andouillette" color="#8E4FA8" size={40} ring="var(--color-green)" />
      </span>
      <Satellite at={{ x: 760, y: 700 }}>
        <Avatar name="Chipolata" color="#4F6FB8" size={22} />
        Chipolata a rejoint la cantine
      </Satellite>
      <span className={cn(onStage, desktopOnly)} style={placed({ x: 900, y: 830 })}>
        <Chip color="var(--color-blue)">Rare</Chip>
      </span>
      <span className={cn(onStage, desktopOnly)} style={placed({ x: 1320, y: 840 })}>
        <Chip color="var(--color-violet)">Épique</Chip>
      </span>
    </div>
  )
}

// ── Texte du hero ──

function Stat({ value, label }: { value: number | null; label: string }) {
  return (
    <div>
      <b className="block font-display text-[28px] leading-[1.1] tabular-nums">{value === null ? "—" : formatNumber(value)}</b>
      <span className="text-[13px] text-muted">{label}</span>
    </div>
  )
}

function StatusPill({ live }: { live: LiveState | null }) {
  if (!live) return null
  const stale = live.stale
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 justify-self-start rounded-full border py-1.5 pr-3.5 pl-3 text-sm font-medium",
        stale ? "border-orange/30 bg-orange/8 text-orange" : "border-cyan/25 bg-cyan/8 text-cyan",
      )}
    >
      <i className="size-2 rounded-full bg-current shadow-[0_0_8px_currentColor]" aria-hidden="true" />
      {stale
        ? `Dernier relevé à ${formatClock(live.updated_at)}, ${formatNumber(live.online)} Généraux en ligne`
        : `Le QG est ouvert, ${formatNumber(live.online)} Généraux en ligne`}
    </span>
  )
}

export function Hero({ live, grades, gamesCount, inviteUrl }: HeroProps) {
  return (
    <section className="relative -mt-[92px] pt-[92px] min-[1100px]:min-h-[900px] max-[1099px]:pb-10" aria-labelledby="hero-title">
      {/* Le décor s'efface vers le bas : pas de coupure nette avec la section suivante. */}
      <div
        className="pointer-events-none absolute inset-0 overflow-hidden [mask-image:linear-gradient(#000_55%,transparent)]"
        aria-hidden="true"
      >
        <div className="halo" style={{ left: "39%", top: -260, width: 980, height: 720, background: "rgb(155 107 255 / 0.30)" }} />
        <div className="halo" style={{ left: "74%", top: 320, width: 620, height: 520, background: "rgb(63 224 240 / 0.15)" }} />
        <div className="halo" style={{ left: "-8%", top: 640, width: 420, height: 300, background: "rgb(255 138 61 / 0.10)" }} />
        <div className="bg-grid" />
        <Horizon />
        {DOTS.map((d, i) => (
          <span
            key={i}
            className="absolute rounded-full"
            style={{
              left: `${d.left}%`,
              top: d.top,
              width: d.size,
              height: d.size,
              background: d.cyan ? "#3FE0F0" : "#fff",
              opacity: d.opacity,
            }}
          />
        ))}
      </div>

      <div className="relative z-3 mx-auto max-w-[1440px] px-6 min-[1100px]:px-20">
        <div className="relative grid max-w-[620px] gap-[26px] pt-[60px] min-[1100px]:pt-[98px]">
          <StatusPill live={live} />
          <h1
            id="hero-title"
            className="m-0 bg-linear-to-b from-white to-[#CBBEFF] bg-clip-text font-display text-[clamp(52px,7vw,92px)] leading-[0.92] font-extrabold tracking-[-0.04em] text-balance text-transparent"
          >
            Bienvenue à SaucisseLand
          </h1>
          <p className="m-0 max-w-[56ch] text-xl leading-normal text-muted">
            Garde-à-vous, recrue. Ici on joue à tout, on monte en grade à chaque partie, et personne ne laisse un
            soldat seul en vocal.
          </p>
          <div className="flex flex-wrap items-center gap-3.5">
            {inviteUrl ? (
              <Button href={inviteUrl} size="lg" sausage>
                Rejoindre le Discord
              </Button>
            ) : (
              <Button size="lg" disabled>
                Invitation indisponible pour le moment
              </Button>
            )}
            <Button href="/progression" variant="ghost" size="lg">
              Voir la progression
            </Button>
          </div>
          {grades && grades.length > 0 && (
            <ul className="m-0 flex list-none flex-wrap gap-2 p-0" aria-label="Les grades de la caserne">
              {[...grades]
                .sort((a, b) => a.level_min - b.level_min)
                .map(g => (
                  <li key={g.slug}>
                    <GradeBadge grade={g} />
                  </li>
                ))}
            </ul>
          )}
          <div className="flex items-center gap-7 pt-1.5" data-testid="hero-stats">
            <Stat value={live?.members ?? null} label="membres" />
            <hr className="m-0 h-[34px] w-px border-0 bg-white/12" />
            <Stat value={live?.online ?? null} label="en ligne" />
            {gamesCount !== null && gamesCount > 0 && (
              <>
                <hr className="m-0 h-[34px] w-px border-0 bg-white/12" />
                <Stat value={gamesCount} label={gamesCount > 1 ? "jeux" : "jeu"} />
              </>
            )}
          </div>
        </div>
      </div>

      <div className="pointer-events-none relative z-2 mx-auto max-w-[1440px] min-[1100px]:absolute min-[1100px]:inset-0 max-[1099px]:px-6">
        <ConstellationLinks />
        <Scene grades={grades} />
      </div>
    </section>
  )
}
