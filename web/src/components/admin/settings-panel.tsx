"use client"

import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import type { DiscordChannel, DiscordRole, SettingGroup } from "@/lib/api/types"
import { SettingField } from "./setting-field"

type Props = {
  groups: SettingGroup[]
  channels: DiscordChannel[] | null
  roles: DiscordRole[] | null
  /** Propriétaire ou admin : seuls à pouvoir modifier les réglages `admin_only`. */
  isAdmin: boolean
}

/** Réglages du serveur : une carte par groupe du registre. */
export function SettingsPanel({ groups, channels: initialChannels, roles, isAdmin }: Props) {
  // Un salon créé depuis un champ devient choisissable dans les autres.
  const [channels, setChannels] = useState(initialChannels)
  const added = (channel: DiscordChannel) =>
    setChannels(list => (list && !list.some(c => c.id === channel.id) ? [...list, channel] : list))

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {groups.map(group => (
        <Panel as="section" key={group.name} aria-labelledby={`group-${group.name}`} className="grid content-start gap-4">
          <h2 id={`group-${group.name}`} className="m-0 font-display text-xl font-extrabold">
            {group.name}
          </h2>
          {group.items.map(item => (
            <SettingField
              key={item.key}
              item={item}
              channels={channels}
              roles={roles}
              onChannelCreated={added}
              readOnly={item.admin_only && !isAdmin}
            />
          ))}
        </Panel>
      ))}
    </div>
  )
}
