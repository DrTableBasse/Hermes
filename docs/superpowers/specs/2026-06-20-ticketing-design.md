# Spec — Système de Ticketing

**Date :** 2026-06-20
**Statut :** Approuvé

---

## Périmètre

Système de support bidirectionnel web ↔ Discord : les tickets peuvent être créés depuis le site web ou via la commande `/newticket` Discord. Les messages se synchronisent dans les deux sens en temps réel.

---

## Contraintes métier

- Un seul ticket `open` par utilisateur à la fois.
- Les admins peuvent créer des tickets pour n'importe quel utilisateur.
- Les admins voient tous les tickets ; les users voient uniquement le leur.
- Fermeture : l'user peut "résoudre" (status=`resolved`), l'admin peut "fermer" (status=`closed`).
- Un ticket fermé/résolu est en lecture seule (web + Discord).

---

## Base de données

```sql
CREATE TABLE tickets (
    id               SERIAL PRIMARY KEY,
    user_id          BIGINT NOT NULL,
    title            TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'open', -- open | resolved | closed
    discord_channel_id BIGINT,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    closed_at        TIMESTAMPTZ,
    created_by_admin BOOLEAN DEFAULT FALSE,
    CONSTRAINT one_open_ticket_per_user
        EXCLUDE (user_id WITH =) WHERE (status = 'open')
);

CREATE TABLE ticket_messages (
    id          SERIAL PRIMARY KEY,
    ticket_id   INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    author_id   BIGINT NOT NULL,
    author_name TEXT NOT NULL,
    content     TEXT NOT NULL,
    source      TEXT NOT NULL, -- 'web' | 'discord'
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON tickets(user_id);
CREATE INDEX ON tickets(status);
CREATE INDEX ON ticket_messages(ticket_id);
```

---

## Architecture — Flux de synchronisation

### Flux A : Web → Discord

1. User poste un message sur le web (`POST /tickets/{id}/message`)
2. `web-api` insère le message en DB (source=`web`)
3. `web-api` appelle `bot:8001/tickets/{id}/message` avec le contenu
4. Le bot poste le message dans le salon Discord du ticket

### Flux B : Discord → Web

1. Admin/user envoie un message dans le salon Discord du ticket
2. Le bot (`on_message`) détecte que le salon est un salon ticket (lookup en DB)
3. Le bot insère le message en DB (source=`discord`)
4. Le web affiche le message au prochain rechargement (ou polling léger)

### Création depuis le web

1. `POST /tickets` → `web-api` appelle `bot:8001/tickets/create`
2. Le bot crée le salon `ticket-{username}-{id}` dans la catégorie `777139814599491584`
3. Permissions : visible par rôle `Administration` uniquement + bot
4. Le bot poste un embed d'introduction et retourne le `discord_channel_id`
5. `web-api` stocke le `discord_channel_id` en DB

### Création depuis Discord (`/newticket`)

1. User tape `/newticket <titre>` dans n'importe quel salon
2. Le bot crée l'entrée en DB directement (accès asyncpg)
3. Le bot crée le salon Discord, met à jour `discord_channel_id` en DB
4. Le bot répond ephémeralement avec un lien vers la page web du ticket

### Fermeture

- **Résolution (user)** : `POST /tickets/{id}/resolve` → status=`resolved`, message système posté dans le salon Discord
- **Fermeture (admin)** : `POST /tickets/{id}/close` → appelle `bot:8001/tickets/{id}/close` → bot archive le salon (permissions en lecture seule), poste embed "Ticket fermé", status=`closed`

---

## Bot — Nouveau cog `bot/cogs/system/ticket_manager.py`

Responsabilités :
- Commande slash `/newticket <titre>` (avec `@command_enabled()`)
- Listener `on_message` pour sync Discord → DB (filtre sur `discord_channel_id` connus)
- Helper partagé `create_ticket_channel(guild, user, ticket_id, title)` → retourne `channel_id`

## Bot — Nouveaux endpoints `bot/api.py`

```
POST /tickets/create         → crée salon Discord, retourne discord_channel_id
POST /tickets/{id}/message   → poste un message dans le salon
POST /tickets/{id}/close     → archive le salon
```

---

## web-api — Nouveau module `web-api/routes/tickets.py`

```
POST   /tickets                → créer ticket (vérifie contrainte 1 open max)
GET    /tickets                → liste (admin: tous | user: le sien)
GET    /tickets/{id}           → détail + messages (admin ou propriétaire)
POST   /tickets/{id}/message   → envoyer message → bot:8001
POST   /tickets/{id}/resolve   → user résout (status=resolved)
POST   /tickets/{id}/close     → admin ferme (status=closed) → bot:8001
POST   /tickets/admin          → admin crée ticket pour un autre user
```

Enregistré dans `web-api/main.py` avec prefix `/tickets`.

---

## Web — Pages Next.js

### `/[locale]/tickets` (admin only)
- Liste paginée de tous les tickets avec filtres statut
- Badge statut coloré (open=vert, resolved=jaune, closed=gris)
- Clic → `/[locale]/tickets/[id]`

### `/[locale]/tickets/[id]`
- Fil de messages avec badge source (🌐 Web / 🎮 Discord)
- Champ de réponse en bas
- Bouton "Marquer résolu" (user) ou "Fermer" (admin)
- Accessible au propriétaire du ticket ou à un admin

### Onglet "Tickets" dans `/[locale]/profile`
- Affiche le ticket ouvert avec lien vers la page détail
- Formulaire de création si aucun ticket open
- Historique des tickets fermés/résolus

---

## Gestion d'erreurs

- Création : si l'user a déjà un ticket open → erreur 409 avec message explicite
- Salon Discord non créé (bot offline) → ticket créé en DB sans `discord_channel_id`, salon créé au prochain redémarrage du bot (tâche de backfill au `on_ready`)
- Message Discord dans salon inconnu → ignoré silencieusement par le listener

---

## Hors périmètre

- Notifications en temps réel (WebSocket) — polling simple suffit pour v1
- Pièces jointes dans les tickets
- Tags/catégories de tickets
- Transfert de ticket entre admins
