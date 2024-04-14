import emitter from '@adonisjs/core/services/emitter'
import BotStarted from '#events/bot_started'

emitter.on(BotStarted, [() => import('#listeners/bot_started_listener')])
