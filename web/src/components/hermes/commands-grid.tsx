import { Chip } from "@/components/ui/chip"
import { BOT_COMMANDS, COMMAND_GROUPS } from "@/content/commands"

/** Commandes réelles du bot, par famille, chacune commentée par Hermes ; le staff est signalé. */
export function CommandsGrid() {
  return (
    <div className="mt-8 grid gap-10">
      {COMMAND_GROUPS.map(group => {
        const commands = BOT_COMMANDS.filter(c => c.group === group.id)
        if (!commands.length) return null
        const titleId = `commandes-${group.id}`
        return (
          <section key={group.id} aria-labelledby={titleId}>
            <h3 id={titleId} className="m-0 mb-4 font-display text-xl font-bold">
              {group.title}
            </h3>
            <ul className="m-0 grid list-none grid-cols-3 gap-3.5 p-0 max-[1000px]:grid-cols-2 max-[560px]:grid-cols-1">
              {commands.map(c => (
                <li
                  key={c.name}
                  className="grid content-start gap-1.5 rounded-2xl border border-line bg-[rgb(12_14_26/0.6)] px-[18px] py-4 transition-colors duration-250 hover:border-cyan/40"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <code className="font-mono text-[15px] font-bold text-cyan">/{c.name}</code>
                    {c.staff && <Chip color="var(--color-orange)">Staff</Chip>}
                  </div>
                  <p className="m-0 text-[13px] leading-[1.45] text-muted">{c.comment}</p>
                </li>
              ))}
            </ul>
          </section>
        )
      })}
    </div>
  )
}
