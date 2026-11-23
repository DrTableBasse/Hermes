import "server-only"
import { Pool } from "pg"

/** Connexion à la base du site (BetterAuth, réglages du bot, droits d'accès), partagée par le serveur Next. */
export const pool = new Pool({
  host:     process.env.PG_HOST,
  port:     parseInt(process.env.PG_PORT ?? "5432"),
  database: process.env.PG_DB,
  user:     process.env.PG_USER,
  password: process.env.PG_PASSWORD,
  // Base injoignable : échec en 5 s plutôt qu'une attente sans fin d'une connexion libre.
  connectionTimeoutMillis: 5000,
})
