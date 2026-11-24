/**
 * Commandes slash réelles du bot, commentées par Hermes.
 * - `BOT_COMMANDS` : commandes déclarées dans `bot/cogs/**` ;
 * - commandes d'appel des jeux : créées par le bot depuis `site_games` (pilotées par l'admin), lues sur
 *   `GET /games` (`command_name`) et commentées par `gameCommands`.
 * `src/content/__tests__/commands.test.ts` vérifie que `BOT_COMMANDS` suit les cogs (ni commande inventée,
 * ni oubliée, ni réservation au staff mal signalée) et que les commentaires de jeux suivent l'amorçage
 * de la migration 023.
 */
export type CommandGroup = "progression" | "jeux" | "services" | "staff"

export type BotCommand = {
  /** Nom tel que tapé dans Discord, sans la barre oblique (`ticket close` pour une sous-commande). */
  name: string
  group: CommandGroup
  /** Commentaire d'Hermes, ton pince-sans-rire. */
  comment: string
  /** Réservée au staff (rôle Administration ou gestion des salons). */
  staff?: boolean
}

export const COMMAND_GROUPS: Array<{ id: CommandGroup; title: string }> = [
  { id: "progression", title: "Progression" },
  { id: "jeux", title: "Jeux et détente" },
  { id: "services", title: "Services" },
  { id: "staff", title: "Réservées au staff" },
]

export const BOT_COMMANDS: readonly BotCommand[] = [
  // ── Progression ──
  { name: "rang", group: "progression", comment: "Affiche ton grade charcutier. Je ne mens jamais, même quand ça fait mal." },
  { name: "level", group: "progression", comment: "Ton niveau et ton XP. Les chiffres ne flattent personne." },
  { name: "stats", group: "progression", comment: "Toutes les statistiques d’un membre. Je note tout. Absolument tout." },
  { name: "profile", group: "progression", comment: "Le profil complet d’un membre. Plus détaillé qu’un dossier militaire." },
  { name: "compare", group: "progression", comment: "Compare deux membres. Je reste neutre. Les chiffres, un peu moins." },
  { name: "classement", group: "progression", comment: "Le classement du serveur, par catégorie. Quelqu’un doit bien être dernier." },
  { name: "leaderboard-xp", group: "progression", comment: "Le classement XP. Pour ceux qui aiment regarder vers le haut." },
  { name: "voice-leaderboard", group: "progression", comment: "Le classement du temps vocal. Dormir en vocal compte. Je ne juge pas." },
  { name: "top-today", group: "progression", comment: "Le top 5 du jour, messages et vocal. Remis à zéro chaque nuit, sans rancune." },
  { name: "voicetime", group: "progression", comment: "Le temps passé en vocal par un membre. Au chronomètre près." },
  { name: "streak", group: "progression", comment: "Ta série de jours en vocal. Un jour manqué et tout s’écroule. Pas de pression." },
  { name: "quests", group: "progression", comment: "Tes défis de la semaine. Je suis ta progression de près. Très près." },
  { name: "quest-claim", group: "progression", comment: "Réclame l’XP d’un défi terminé. Je vérifie avant de payer." },
  { name: "achievements", group: "progression", comment: "Les succès débloqués d’un membre. Certains sont secrets. Je ne dirai rien." },

  // ── Jeux et détente (les commandes d'appel des jeux viennent de `gameCommands`) ──
  { name: "blague", group: "jeux", comment: "Une blague au hasard. Je les raconte, je ne les comprends pas." },
  { name: "confess", group: "jeux", comment: "Une confession anonyme. Je garde le secret. C’est mon métier." },

  // ── Services ──
  { name: "newticket", group: "services", comment: "Ouvre un ticket privé avec le staff. Leurs MP restent intacts." },
  { name: "ticket close", group: "services", comment: "Ferme le ticket du salon. Réservé à son auteur et au staff." },
  { name: "rappel-bump", group: "services", comment: "Je t’envoie un MP quand le bump est de nouveau possible. J’insiste avec tact." },
  { name: "warns", group: "services", comment: "Les avertissements d’un membre. La liste est courte, j’espère." },
  { name: "check_articles", group: "services", comment: "Vérifie les articles anime et manga d’hier. Je lis pour vous." },

  // ── Réservées au staff ──
  { name: "warn", group: "staff", staff: true, comment: "Avertit un membre. Je consigne, sans commentaire. Enfin, presque." },
  { name: "delwarn", group: "staff", staff: true, comment: "Efface un avertissement. Je pardonne, je n’oublie pas." },
  { name: "tempmute", group: "staff", staff: true, comment: "Rend un membre muet pour un temps. Le silence lui va bien." },
  { name: "kick", group: "staff", staff: true, comment: "Expulse un membre. La porte est par là." },
  { name: "tempban", group: "staff", staff: true, comment: "Bannit un membre pour un temps. Il reviendra, peut-être plus sage." },
  { name: "clear", group: "staff", staff: true, comment: "Supprime des messages en masse. Je ne les relirai pas." },
  { name: "audit", group: "staff", staff: true, comment: "Le dossier d’audit complet d’un membre. Très complet. Trop, peut-être." },
  { name: "ticket add", group: "staff", staff: true, comment: "Ajoute un membre au ticket. Plus on est de fous." },
  { name: "ticket remove", group: "staff", staff: true, comment: "Retire un membre du ticket. Moins on est de fous." },
  { name: "ticket list", group: "staff", staff: true, comment: "La liste des tickets ouverts. Je les compte, vous les fermez." },
  { name: "reset-quests", group: "staff", staff: true, comment: "Réinitialise les quêtes de la semaine. Tout le monde repart de zéro." },
  { name: "enable-command", group: "staff", staff: true, comment: "Réactive une commande. Elle était en pause, pas en vacances." },
  { name: "disable-command", group: "staff", staff: true, comment: "Désactive une commande. Elle ne m’en voudra pas." },
  { name: "commands-status", group: "staff", staff: true, comment: "L’état de toutes les commandes. Tableau de bord du tableau de bord." },
]

/** Commentaires d'Hermes pour les commandes d'appel des jeux amorcés (clé = nom de commande). */
export const GAME_COMMAND_COMMENTS: Readonly<Record<string, string>> = {
  dbd: "Appelle les joueurs de Dead by Daylight. Je ne viens pas, j’ai peur du noir.",
  lol: "Appelle les joueurs de League of Legends. Je décline toute responsabilité.",
  warframe: "Appelle les joueurs de Warframe. Prévoir du temps. Beaucoup de temps.",
  overwatch: "Appelle les joueurs d’Overwatch. Quelqu’un devra jouer soigneur.",
  fortnite: "Appelle les joueurs de Fortnite. Je ne danserai pas.",
  minecraft: "Appelle les bâtisseurs de Minecraft. La statue de saucisse ne se finira pas seule.",
}

/** Commande d'appel d'un jeu ajouté depuis l'admin, sans commentaire écrit à la main. */
export const genericGameComment = (game: string) => `Appelle les joueurs de ${game}. Je transmets, je ne joue pas.`

/**
 * Commandes d'appel des jeux actifs (`GET /games`, dans l'ordre du site) ; un jeu sans commande inscrite
 * (`command_name` nul : non provisionné ou archivé) n'en a pas.
 */
export function gameCommands(games: ReadonlyArray<{ name: string; command_name?: string | null }>): BotCommand[] {
  return games.flatMap(g =>
    g.command_name
      ? [{ name: g.command_name, group: "jeux" as const, comment: GAME_COMMAND_COMMENTS[g.command_name] ?? genericGameComment(g.name) }]
      : [],
  )
}
