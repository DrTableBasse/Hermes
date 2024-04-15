import { BaseInteraction, Client } from 'discord.js'
import { BaseEvent } from '@adonisjs/core/events'

export class InteractionCreated extends BaseEvent {
  constructor(
    public event: BaseInteraction,
    public client: Client
  ) {
    super()
  }
}
