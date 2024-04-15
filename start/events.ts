import emitter from '@adonisjs/core/services/emitter'
import { InteractionCreated } from '#events/interaction_created'
import { BotStarted } from '#events/bot_started'

emitter.on(BotStarted, [() => import('#listeners/bot_started_listener')])
emitter.on(InteractionCreated, [() => import('#listeners/interaction_created_listener')])
