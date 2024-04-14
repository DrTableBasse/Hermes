import type { Client } from 'discord.js'

declare module '@adonisjs/core/types' {
  interface EventsList {
    'bot:started': Client
  }
}
