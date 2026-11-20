import type { Metadata } from "next"
import { connection } from "next/server"
import { Gamepad2, Hash, Volume2 } from "lucide-react"
import { Footer } from "@/components/layout/footer"
import { Navbar } from "@/components/layout/navbar"
import { Avatar } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Chip } from "@/components/ui/chip"
import { Countdown } from "@/components/ui/countdown"
import { DiscordEmbed, DiscordMessage, DiscordWindow } from "@/components/ui/discord-window"
import { GradeBadge, type Grade } from "@/components/ui/grade-badge"
import { Marquee } from "@/components/ui/marquee"
import { Panel } from "@/components/ui/panel"
import { LiveDot, SectionHeading } from "@/components/ui/section-heading"
import { XpBar } from "@/components/ui/xp-bar"
import { formatNumber, xpProgress } from "@/lib/format"

// Page de relecture visuelle du design system : non liée, jamais indexée.
export const metadata: Metadata = {
  title: "Kit — SaucisseLand",
  robots: { index: false, follow: false },
}

// Toutes les données ci-dessous sont des exemples, marqués comme tels à l'écran.
const GRADES: Grade[] = [
  { name: "Recrue Cocktail", slug: "recrue-cocktail", color: "var(--color-muted)" },
  { name: "Caporal Chipolata", slug: "caporal-chipolata", color: "var(--color-blue)" },
  { name: "Sergent Merguez", slug: "sergent-merguez", color: "var(--color-violet)" },
  { name: "Lieutenant Toulouse", slug: "lieutenant-toulouse", color: "var(--color-cyan)" },
  { name: "Colonel Saucisson", slug: "colonel-saucisson", color: "var(--color-gold)" },
  { name: "Général Saucisse", slug: "general-saucisse", color: "var(--color-orange)" },
]

const GAMES: Array<[string, string, string]> = [
  ["Dead by Daylight", "#B3202D", "#2A0B10"],
  ["War Dogs", "#7A8A3A", "#1E2410"],
  ["League of Legends", "#0AC8B9", "#0A1A2A"],
  ["Warframe", "#3FA9C9", "#0B1C26"],
  ["Overwatch", "#F99E1A", "#2A1A08"],
  ["Fortnite", "#9D4DFF", "#1A0B2E"],
  ["Minecraft", "#5DAA3A", "#10200C"],
]

function KitSection({ title, children, bleed }: { title: string; children: React.ReactNode; bleed?: boolean }) {
  return (
    <section className="grid grid-cols-[minmax(0,1fr)] gap-6 border-t border-line py-14">
      <h2 className={`font-display text-2xl font-bold ${bleed ? "mx-auto w-full max-w-[1440px] px-6 min-[1100px]:px-20" : ""}`}>{title}</h2>
      {children}
    </section>
  )
}

function GameCard({ name, from, to }: { name: string; from: string; to: string }) {
  return (
    <article className="grid w-[250px] flex-none grid-rows-[150px_auto] overflow-hidden rounded-[18px] border border-line bg-panel">
      <div className="relative" style={{ background: `linear-gradient(180deg, ${from}, ${to})` }}>
        <span className="absolute top-3.5 left-3.5 rounded-lg bg-black/35 px-2.5 py-1 text-[11px] font-medium text-white/85">
          Visuel officiel à intégrer
        </span>
      </div>
      <div className="grid gap-2 px-[18px] pt-3.5 pb-[18px]">
        <h3 className="font-display text-[19px] font-bold">{name}</h3>
        <Button href="/#jeux" variant="ghost" size="sm" className="justify-self-start">
          Trouver des joueurs
        </Button>
      </div>
    </article>
  )
}

// Exemple de la maquette : départ dans 2 h 14 min 37 s, recalculé à chaque requête.
function exampleEventStart() {
  return new Date(Date.now() + ((2 * 60 + 14) * 60 + 37) * 1000).toISOString()
}

export default async function KitPage() {
  await connection()
  const eventStart = exampleEventStart()
  const progress = xpProgress(8902)

  return (
    <>
      <Navbar inviteUrl="https://discord.gg/exemple" />

      <main className="relative">
        <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
          <div className="halo" style={{ left: "39%", top: -260, width: 980, height: 720, background: "rgb(155 107 255 / .30)" }} />
          <div className="halo" style={{ left: "74%", top: 320, width: 620, height: 520, background: "rgb(63 224 240 / .15)" }} />
          <div className="halo" style={{ left: "-8%", top: 640, width: 420, height: 300, background: "rgb(255 138 61 / .10)" }} />
          <div className="bg-grid h-[900px]" />
        </div>

        <div className="relative mx-auto max-w-[1440px] px-6 pt-16 min-[1100px]:px-20">
          <SectionHeading
            as="h1"
            lead={<Chip example>Kit de relecture, données d&apos;exemple</Chip>}
            title="Design system SaucisseLand"
            sub="Chaque composant du site, isolé. À comparer à la maquette validée."
          />

          <KitSection title="Couleurs">
            <div className="flex flex-wrap gap-3">
              {[
                "bg", "panel", "panel-2", "violet", "violet-2", "cyan", "blue", "orange", "green", "gold", "fg", "muted",
              ].map(c => (
                <div key={c} className="grid gap-1.5 text-xs text-muted">
                  <span className="size-14 rounded-xl border border-white/10" style={{ background: `var(--color-${c})` }} />
                  {c}
                </div>
              ))}
            </div>
          </KitSection>

          <KitSection title="Typographie">
            <p className="bg-linear-to-b from-white to-[#CBBEFF] bg-clip-text font-display text-[clamp(52px,7vw,92px)] leading-[.92] font-extrabold tracking-[-0.04em] text-transparent">
              Bienvenue à SaucisseLand
            </p>
            <SectionHeading
              lead={<LiveDot>En direct, chiffres fournis par Hermes</LiveDot>}
              title="La caserne en direct"
              sub="Pas de chiffres gonflés : Hermes compte les troupes en temps réel. Même ceux qui dorment en vocal."
            />
            <p className="max-w-[56ch] text-xl text-muted">
              Garde-à-vous, recrue. Ici on joue à tout, on monte en grade à chaque partie, et personne ne laisse un
              soldat seul en vocal.
            </p>
          </KitSection>

          <KitSection title="Boutons">
            <div className="flex flex-wrap items-center gap-4">
              <Button href="/" size="lg" sausage>
                Rejoindre les Généraux Saucisses
              </Button>
              <Button href="/" variant="ghost" size="lg">
                Découvrir la communauté
              </Button>
              <Button variant="discord">Se connecter avec Discord</Button>
              <Button>Je viens</Button>
              <Button variant="ghost" size="sm">
                Trouver des joueurs
              </Button>
              <Button disabled>Désactivé</Button>
            </div>
          </KitSection>

          <KitSection title="Chips et grades">
            <div className="flex flex-wrap gap-2">
              {GRADES.map(g => (
                <GradeBadge key={g.slug} grade={g} />
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <Chip color="var(--color-muted)">Commun</Chip>
              <Chip color="var(--color-blue)">Rare</Chip>
              <Chip color="var(--color-violet)">Épique</Chip>
              <Chip color="var(--color-orange)">Légendaire</Chip>
              <Chip color="#B3202D">
                <Gamepad2 className="size-3.5" aria-hidden="true" />
                Dead by Daylight
              </Chip>
              <Chip example>Exemple</Chip>
            </div>
          </KitSection>

          <KitSection title="Avatars">
            <div className="flex flex-wrap items-center gap-4">
              <Avatar name="Merguez_Royale" color="#C2553A" ring="var(--color-green)" />
              <Avatar name="Chipolata" color="#4F6FB8" size={40} />
              <Avatar name="Kéfir" color="#3E8A5C" size={56} ring="var(--color-violet)" />
              <Avatar name="Hermes" size={76} ring="var(--color-cyan)" labelled />
            </div>
          </KitSection>

          <KitSection title="Panneaux">
            <div className="grid grid-cols-4 gap-5 max-[1000px]:grid-cols-2 max-[560px]:grid-cols-1">
              <Panel className="grid gap-2.5">
                <span className="text-[15px] font-medium text-muted">Membres</span>
                <span className="font-display text-[52px] leading-none font-extrabold tracking-[-0.03em] tabular-nums">
                  {formatNumber(1240)}
                </span>
                <Chip example>Exemple</Chip>
              </Panel>
              <Panel highlight className="grid gap-2.5">
                <span className="text-[15px] font-medium text-muted">En ligne maintenant</span>
                <span className="font-display text-[52px] leading-none font-extrabold tracking-[-0.03em] tabular-nums">
                  312
                </span>
                <small className="text-xs text-muted">Carte mise en avant</small>
              </Panel>
              <Panel className="grid gap-2.5">
                <span className="text-[15px] font-medium text-muted">En vocal</span>
                <div className="flex">
                  {[
                    ["Merguez_Royale", "#C2553A"],
                    ["Chipolata", "#4F6FB8"],
                    ["Kéfir", "#3E8A5C"],
                    ["Boudin_Blanc", "#9A6B2F"],
                  ].map(([n, c]) => (
                    <Avatar key={n} name={n} color={c} size={30} className="-mr-2 shadow-[0_0_0_2px_var(--color-panel)]" />
                  ))}
                </div>
              </Panel>
              <Panel className="grid gap-2.5">
                <span className="text-[15px] font-medium text-muted">Messages aujourd&apos;hui</span>
                <span className="font-display text-[52px] leading-none font-extrabold tracking-[-0.03em] tabular-nums">
                  {formatNumber(4812)}
                </span>
              </Panel>
            </div>
          </KitSection>

          <KitSection title="Fenêtres Discord (verre)">
            <div className="flex flex-wrap items-start gap-8">
              <DiscordWindow title="Cantine des Généraux, vocal" icon={<Volume2 />} className="w-[330px] rotate-[4deg]">
                {[
                  ["Merguez_Royale", "#C2553A", 4, true],
                  ["Chipolata", "#4F6FB8", 3, true],
                  ["Kéfir", "#3E8A5C", 2, false],
                ].map(([n, c, g, speaking]) => (
                  <div key={n as string} className="flex items-center gap-2.5">
                    <Avatar
                      name={n as string}
                      color={c as string}
                      size={32}
                      ring={speaking ? "var(--color-green)" : undefined}
                    />
                    <div>
                      <b className="block text-sm font-semibold">{n as string}</b>
                      <small className="block text-xs text-muted">{GRADES[g as number].name}</small>
                    </div>
                  </div>
                ))}
              </DiscordWindow>

              <DiscordWindow title="général" icon={<Hash />} className="w-[470px] max-w-full -rotate-3 animate-float">
                <DiscordMessage author="Chipolata" avatarColor="#4F6FB8" nameColor="#8FB1FF" time="21:02">
                  qui pour une DBD ce soir ? il nous manque un survivant
                </DiscordMessage>
                <DiscordMessage author="Hermes" nameColor="#C9B5FF" time="21:04" bot>
                  <DiscordEmbed title="Promotion !">
                    <p>Andouillette passe Caporal Chipolata (niveau 5). Médaille en papier alu envoyée en MP. Repos, soldat.</p>
                    <XpBar ratio={0.62} label="Progression d'Andouillette" />
                  </DiscordEmbed>
                </DiscordMessage>
              </DiscordWindow>

              <DiscordWindow title="commandes-bot" icon={<Hash />} className="w-[520px] max-w-full">
                <DiscordMessage author="Chipolata" avatarColor="#4F6FB8" nameColor="#8FB1FF" time="21:12">
                  <code className="font-mono text-sm font-semibold text-cyan">/rang</code>
                </DiscordMessage>
                <DiscordMessage author="Hermes" nameColor="#C9B5FF" time="21:12" bot>
                  <DiscordEmbed title="Chipolata, Lieutenant Toulouse" accent="var(--color-cyan)">
                    <p>Niveau 21, 10 115 XP. Série de 14 jours.</p>
                    <XpBar ratio={0.38} label="Progression de Chipolata" />
                    <p className="text-muted">Encore 1 885 XP avant le niveau 22. Courage. Ou pas, je ne juge pas.</p>
                  </DiscordEmbed>
                </DiscordMessage>
              </DiscordWindow>
            </div>
          </KitSection>

          <KitSection title="Barre d'XP">
            <div className="grid max-w-[370px] gap-3.5 rounded-[18px] border border-violet/35 bg-[rgb(23_26_46/0.92)] px-[22px] py-5 shadow-[0_24px_50px_rgb(0_0_0/0.5),0_0_40px_rgb(155_107_255/0.25)]">
              <div className="flex items-center gap-3.5">
                <Avatar name="Kéfir" color="#3E8A5C" size={56} ring="var(--color-violet)" />
                <div>
                  <b className="mb-1 block font-display text-xl">Kéfir</b>
                  <GradeBadge grade={GRADES[2]} />
                </div>
              </div>
              <XpBar ratio={progress.ratio} height={10} sausage label="Progression vers le niveau suivant" />
              <p className="text-[13px] text-muted">
                Niveau {progress.level}, {formatNumber(8902)} XP. {formatNumber(progress.next - 8902)} XP avant le
                niveau {progress.level + 1}.
              </p>
              <Chip example>Exemple</Chip>
            </div>
            <div className="grid max-w-[460px] gap-3">
              <XpBar ratio={0} sausage height={12} label="Barre vide" />
              <XpBar ratio={1} sausage height={12} label="Barre pleine" />
              <XpBar ratio={1} color="var(--color-green)" label="Quête terminée" />
            </div>
          </KitSection>

          <KitSection title="Compte à rebours">
            <Countdown target={eventStart} />
            <Countdown target="2020-01-01T00:00:00Z" />
          </KitSection>
        </div>

        <KitSection title="Bandeau défilant" bleed>
          <div className="grid gap-[18px]">
            <Marquee
              aria-label="Tous nos jeux"
              items={GAMES.map(([n, a, b]) => <GameCard key={n} name={n} from={a} to={b} />)}
            />
            <Marquee
              reverse
              speed={55}
              items={GAMES.map(([n, a]) => (
                <Chip key={n} color={a} className="px-4 py-2 text-sm">
                  {n}
                </Chip>
              ))}
            />
          </div>
        </KitSection>
      </main>

      <Footer />
    </>
  )
}
