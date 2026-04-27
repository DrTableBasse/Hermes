# API Web Hermes Bot

L'API web permet au site SaucisseLand d'utiliser les commandes du bot Discord Hermes via des requêtes HTTP.

## Configuration

Ajoutez les variables suivantes dans votre fichier `.env` :

```env
API_TOKEN=your_api_secret_token_here
API_PORT=8001
ALLOWED_ROLE_IDS=123456789012345678,987654321098765432
```

- `API_TOKEN` : Token secret pour authentifier les requêtes à l'API
- `API_PORT` : Port sur lequel l'API sera accessible (par défaut: 8001)
- `ALLOWED_ROLE_IDS` : IDs des rôles Discord autorisés à utiliser l'API (séparés par des virgules). **Doit être le même que celui utilisé pour les articles sur le site web.**

## Démarrage

L'API démarre automatiquement avec le bot Discord. Elle est accessible sur `http://localhost:8001` (ou le port configuré).

## Endpoints

### GET `/`
Endpoint de santé de l'API.

**Réponse:**
```json
{
  "status": "online",
  "service": "Hermes Bot API",
  "version": "1.0.0"
}
```

### GET `/health`
Vérification de l'état de l'API et du bot Discord.

**Réponse:**
```json
{
  "api": "online",
  "bot": "connected",
  "guild_id": 123456789
}
```

### POST `/warn`
Donne un avertissement à un utilisateur Discord.

**Authentification:** Requis (Header `Authorization: Bearer <API_TOKEN>`)

**Permissions:** Le modérateur (défini par `moderator_id`) doit avoir un des rôles Discord autorisés (définis dans `ALLOWED_ROLE_IDS`).

**Corps de la requête:**
```json
{
  "user_id": 123456789,
  "reason": "Raison de l'avertissement",
  "moderator_id": 987654321,
  "moderator_name": "Nom du modérateur (optionnel)"
}
```

**Paramètres:**
- `user_id` (int, requis) : ID Discord de l'utilisateur à avertir
- `reason` (string, optionnel) : Raison de l'avertissement (défaut: "Aucune raison spécifiée")
- `moderator_id` (int, requis) : ID Discord du modérateur
- `moderator_name` (string, optionnel) : Nom d'affichage du modérateur

**Réponse en cas de succès:**
```json
{
  "success": true,
  "message": "Avertissement ajouté avec succès pour Username",
  "warn_count": 3
}
```

**Réponse en cas d'erreur:**
```json
{
  "detail": "Message d'erreur"
}
```

**Codes de statut:**
- `200` : Succès
- `401` : Token d'authentification invalide ou manquant
- `403` : Le modérateur n'a pas les permissions nécessaires (rôle Discord requis)
- `404` : Utilisateur, modérateur ou serveur Discord non trouvé
- `500` : Erreur interne
- `503` : Bot Discord non disponible ou non connecté

## Exemple d'utilisation

### Avec curl

```bash
curl -X POST "http://localhost:8001/warn" \
  -H "Authorization: Bearer your_api_secret_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 123456789,
    "reason": "Comportement inapproprié",
    "moderator_id": 987654321,
    "moderator_name": "Modérateur"
  }'
```

### Avec Python (requests)

```python
import requests

url = "http://localhost:8001/warn"
headers = {
    "Authorization": "Bearer your_api_secret_token_here",
    "Content-Type": "application/json"
}
data = {
    "user_id": 123456789,
    "reason": "Comportement inapproprié",
    "moderator_id": 987654321,
    "moderator_name": "Modérateur"
}

response = requests.post(url, json=data, headers=headers)
print(response.json())
```

### Avec JavaScript (fetch)

```javascript
const response = await fetch('http://localhost:8001/warn', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer your_api_secret_token_here',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    user_id: 123456789,
    reason: 'Comportement inapproprié',
    moderator_id: 987654321,
    moderator_name: 'Modérateur'
  })
});

const data = await response.json();
console.log(data);
```

## Fonctionnalités

L'endpoint `/warn` :
1. Ajoute l'avertissement en base de données
2. Envoie une notification dans le canal de logs admin (si `ADMIN_LOG_CHANNEL_ID` est configuré)
3. Envoie un message privé à l'utilisateur averti (si les DMs sont ouverts)
4. Retourne le nombre total d'avertissements de l'utilisateur

## Sécurité

- **Authentification obligatoire** : Toutes les requêtes vers `/warn` nécessitent un token valide
- **Vérification des rôles** : Seuls les utilisateurs ayant un des rôles Discord autorisés (définis dans `ALLOWED_ROLE_IDS`) peuvent donner des avertissements
- **Token secret** : Utilisez un token fort et unique dans `API_TOKEN`
- **CORS** : Actuellement configuré pour accepter toutes les origines. En production, limitez les origines autorisées dans `api.py`

**Important** : Le `ALLOWED_ROLE_IDS` doit être identique à celui utilisé sur le site web SaucisseLand pour les articles. Cela garantit que seuls les mêmes utilisateurs autorisés peuvent utiliser l'API.

## Notes

- L'API vérifie automatiquement que le bot Discord est connecté avant de traiter les requêtes
- Si l'utilisateur n'est pas membre du serveur, seul l'avertissement en base de données sera créé (pas de message privé)
- Les erreurs sont loggées pour faciliter le débogage

