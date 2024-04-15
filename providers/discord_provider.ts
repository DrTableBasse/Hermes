import type { ApplicationService } from '@adonisjs/core/types'
import { Client, GatewayIntentBits } from 'discord.js'
import env from '#start/env'
import { InteractionCreated } from '#events/interaction_created'
import { BotStarted } from '#events/bot_started'

export default class DiscordProvider {
  constructor(protected app: ApplicationService) {}

  /**
   * Register bindings to the container
   */
  register() {
    this.app.container.singleton(Client, () => {
      return new Client({ intents: [GatewayIntentBits.Guilds] })
    })
    this.app.container.alias('discord', Client)
  }

  /**
   * The container bindings have booted
   */
  async boot() {}

  /**
   * The application has been booted
   */
  async start() {
    const client = await this.app.container.make('discord')
    client.on('ready', (clientEvent) => BotStarted.dispatch(clientEvent))
    client.on('interactionCreate', async (interaction) =>
      InteractionCreated.dispatch(interaction, client)
    )

    client.login(env.get('TOKEN'))
  }

  /**
   * The process has been started
   */
  async ready() {}

  /**
   * Preparing to shutdown the app
   */
  async shutdown() {}
}
