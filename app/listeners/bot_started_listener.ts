import logger from '@adonisjs/core/services/logger'
import BotStarted from '#events/bot_started'
import { ApplicationCommandDataResolvable } from 'discord.js'

// Todo: Temporary command list, will be extracted to a separate file with a better structure
const COMMANDS: ApplicationCommandDataResolvable[] = [
  {
    name: 'ping',
    description: 'Replies with pong',
  },
  {
    name: 'echo',
    description: 'Replies with your input',
    options: [
      {
        name: 'input',
        description: 'The input to echo',
        type: 3,
        required: true,
      },
    ],
  },
]

export default class BotStartedListener {
  async handle({ discordClient }: BotStarted) {
    logger.info(`Logged in as ${discordClient.user?.tag}!`)
    logger.info('Last uptime date was %s', discordClient.readyAt?.toISOString())

    const [guilds, applicationCommands] = await Promise.all([
      discordClient.guilds.fetch(),
      this.refreshSlashCommands({ discordClient }),
    ])

    logger.info('Bot is in %s guilds', guilds.size)
    logger.info('Bot has %s slash commands', applicationCommands?.size)
  }

  async refreshSlashCommands({ discordClient }: BotStarted) {
    logger.info('Refreshing slash commands with %s commands', COMMANDS.length)
    return discordClient.application?.commands.set(COMMANDS)
  }
}
