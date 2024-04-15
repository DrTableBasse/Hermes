import { InteractionCreated } from '#events/interaction_created'

export default class InteractionCreatedListener {
  async handle(payloadEvent: InteractionCreated) {
    const { event } = payloadEvent

    if (!event.isChatInputCommand()) return

    switch (event.commandName) {
      case 'ping':
        await event.reply('Pong!')
        break
      case 'echo':
        const input = event.options.getString('input', true)
        await event.reply(input.split('').reverse().join(''))
        break
      default:
        await event.reply('Unknown command')
        break
    }
  }
}
