import { BaseEvent } from '@adonisjs/core/events'
import type { Client } from 'discord.js'

export class BotStarted extends BaseEvent {
  /**
   * Accept event data as constructor parameters
   */
  constructor(public discordClient: Client) {
    super()
  }
}
