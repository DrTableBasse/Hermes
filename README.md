# 🤖 Hermes Bot - Bot Discord Multifonctionnel

Bot Discord intelligent et moderne pour la communauté SaucisseLand, spécialisé dans la modération, les statistiques vocales, l'intégration d'articles anime et la gestion avancée des commandes.

## ✨ Fonctionnalités

### 🎤 Gestion Vocale Avancée
- **Suivi automatique** du temps passé en vocal avec PostgreSQL
- **Classements** des utilisateurs les plus actifs
- **Commandes** `/voice` et `/check-voice`
- **Logs détaillés** des événements vocaux
- **Attribution automatique de rôles** basée sur le temps vocal

### 🛡️ Modération Complète
- **Système d'avertissements** avec base de données PostgreSQL
- **Commandes** `/warn`, `/check-warn`, `/kick`, `/ban`, `/mute`
- **Sanctions temporaires** `/tempban`, `/tempmute`
- **Notifications** automatiques aux utilisateurs
- **Logs de sanctions** détaillés et persistants

### 📰 Intégration Articles Anime
- **Récupération automatique** d'articles depuis Animotaku.fr
- **Filtrage intelligent** des articles d'hier
- **Système de cache** pour éviter les doublons
- **Commandes** `/anime-status`, `/anime-cache`
- **Envoi automatique** toutes les 5 minutes

### 🎮 Fonctionnalités Fun
- **Système de blagues** via API Blagues
- **Système de confessions** anonymes
- **Commandes de jeux** et divertissement
- **Gestion des rôles** automatique

### ⚙️ Administration Avancée
- **Gestion des commandes** avec activation/désactivation dynamique
- **Système de cache** pour optimiser les performances
- **Logs système** complets avec Rich
- **Scheduler** pour les tâches automatiques
- **Interface console** moderne et colorée

## 🚀 Installation

### Prérequis
- Python 3.8+
- PostgreSQL 12+
- Token Discord Bot
- Serveur Discord

### Configuration

1. **Cloner le repository**
```bash
git clone <repository-url>
cd Hermes
```

2. **Installer les dépendances**
```bash
pip install -r requirements.txt
```

3. **Configurer PostgreSQL**
```bash
# Créer la base de données
createdb saucisseland

# Exécuter le script d'initialisation
psql -d saucisseland -f init-postgres.sql
```

4. **Configurer les variables d'environnement**
```bash
cp env.example .env
# Éditer .env avec vos tokens et configurations
```

5. **Variables d'environnement requises**
```env
# Configuration Discord (OBLIGATOIRE)
DISCORD_TOKEN=your_discord_bot_token
GUILD_ID=your_guild_id

# Configuration API (OBLIGATOIRE)
BLAGUES_API_TOKEN=your_blagues_api_token

# Configuration des canaux Discord (OBLIGATOIRE)
BOT_CHANNEL_START=your_bot_channel_id
LOG_CHANNEL_ID=your_log_channel_id
VOICE_LOG_CHANNEL_ID=your_voice_log_channel_id
CONFESSION_CHANNEL_ID=your_confession_channel_id
ANIME_NEWS_CHANNEL_ID=your_anime_news_channel_id
WELCOME_CHANNEL_ID=your_welcome_channel_id
MEMBER_LOGS_CHANNEL_ID=your_member_logs_channel_id

# Configuration des rôles Discord (OBLIGATOIRE)
AUTHORIZED_ROLES=role1,role2,role3
ROLE_BATMAN=your_batman_role_name
VOICE_HOURS_FOR_ROLE=100

# Configuration PostgreSQL (OBLIGATOIRE)
PG_HOST=localhost
PG_PORT=5432
PG_DB=saucisseland
PG_USER=your_database_user
PG_PASSWORD=your_database_password

# Configuration des URLs (OBLIGATOIRE)
ANIME_THUMBNAIL_URL=your_anime_thumbnail_url
ANIME_AUTHOR_AVATAR_URL=your_anime_author_avatar_url
```

**Note :** Copiez le fichier `env.example` vers `.env` et remplissez les valeurs avec vos propres configurations. Assurez-vous de ne pas inclure de commentaires dans les valeurs des variables.

### Démarrage

```bash
python main.py
```

### Validation de la configuration

Avant de démarrer le bot, vous pouvez valider votre configuration :

```bash
# Valider la configuration
python config.py

# Configurer la table des statuts de commandes
python setup_command_status_table.py

# Nettoyer le projet (optionnel)
python scripts/cleanup_project.py
```

## 📊 Architecture

### Structure des Cogs
```
cogs/
├── fun/           # Commandes de divertissement
│   ├── anime.py   # Intégration articles anime
│   ├── blague.py  # Système de blagues
│   ├── confess.py # Système de confessions
│   └── games.py   # Jeux
├── moderation/    # Outils de modération
│   ├── voice.py   # Gestion vocale
│   ├── warn.py    # Système d'avertissements
│   ├── kick.py    # Expulsion
│   ├── ban.py     # Bannissement
│   ├── mute.py    # Mute
│   └── ...
└── system/        # Commandes système
    ├── reload.py  # Rechargement des cogs
    ├── shutdown.py # Arrêt du bot
    └── ...
```

### Base de Données PostgreSQL
- **Tables principales** :
  - `user_voice_data` : Statistiques vocales des utilisateurs
  - `warn` : Avertissements et sanctions
  - `user_message_stats` : Statistiques des messages
  - `command_status` : Statuts des commandes (activé/désactivé)

### Utilitaires
```
utils/
├── database.py      # Gestionnaire de base de données
├── command_manager.py # Gestion des statuts de commandes
├── constants.py     # Constantes et variables d'environnement
└── logging.py       # Système de logging
```

## 🔧 Commandes Principales

### Modération
- `/warn @user raison` - Avertir un utilisateur
- `/check-warn @user` - Voir les avertissements
- `/kick @user raison` - Expulser un utilisateur
- `/ban @user raison` - Bannir un utilisateur
- `/mute @user durée raison` - Muter un utilisateur
- `/tempban @user durée raison` - Bannir temporairement

### Vocal
- `/voice [@user]` - Voir le temps vocal
- `/check-voice [nombre]` - Classement vocal

### Articles Anime
- `/anime-status` - Statut de la récupération d'articles
- `/anime-cache [action]` - Gérer le cache des articles

### Administration
- `/command-management` - Gérer les commandes
- `/reload` - Recharger les cogs
- `/shutdown` - Arrêter le bot

## 🔄 Intégration Site Web

Le bot est conçu pour s'intégrer avec le site web SaucisseLand :

- **Articles automatiques** : Récupération quotidienne depuis Animotaku.fr
- **Base de données partagée** : PostgreSQL pour la persistance
- **API REST** : Communication bidirectionnelle
- **Authentification unifiée** : Système commun

## 🛠️ Développement

### Ajouter une nouvelle commande

1. **Créer le cog**
```python
# cogs/fun/ma_commande.py
import discord
from discord.ext import commands
from discord import app_commands
from utils.command_manager import CommandStatusManager
import logging

logger = logging.getLogger(__name__)

class MaCommandeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="macommande", description="Description de ma commande")
    async def ma_commande(self, interaction: discord.Interaction):
        command_name = interaction.command.name
        is_enabled = await CommandStatusManager.get_command_status(command_name, guild_id=interaction.guild_id, use_cache=False)
        
        if not is_enabled:
            await interaction.response.send_message(
                f"❌ La commande `/{command_name}` est actuellement désactivée.",
                ephemeral=True
            )
            return
            
        await interaction.response.send_message("Ma commande fonctionne !")

async def setup(bot):
    await bot.add_cog(MaCommandeCog(bot))
```

2. **Ajouter au système de gestion des commandes**
```bash
# La commande sera automatiquement ajoutée lors du prochain redémarrage
# ou vous pouvez l'ajouter manuellement dans la base de données
```

### Nettoyage du projet

```bash
# Nettoyer les fichiers temporaires et caches
python scripts/cleanup_project.py

# Nettoyer l'environnement
python scripts/clean_env.py
```

### Migration de données

```bash
# Migrer de SQLite vers PostgreSQL
python scripts/migrate_sqlite_to_postgres.py

# Vérifier la migration
python scripts/verify_migration.py
```

## 📝 Changelog

### Version 2.0
- ✅ Migration complète vers PostgreSQL
- ✅ Système de gestion des commandes avec activation/désactivation
- ✅ Intégration articles anime avec cache intelligent
- ✅ Nettoyage complet du code et ajout de docstrings
- ✅ Suppression des commandes de test
- ✅ Interface console moderne avec Rich
- ✅ Gestion avancée des erreurs et logging
- ✅ Scripts de maintenance et nettoyage

### Version 1.x
- Système de modération basique
- Gestion vocale avec SQLite
- Commandes fun et divertissement

## 🤝 Contribution

1. Fork le projet
2. Créer une branche feature (`git checkout -b feature/AmazingFeature`)
3. Commit les changements (`git commit -m 'Add some AmazingFeature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## 👨‍💻 Auteur

**Dr.TableBasse**
- GitHub: [@drtablebasse](https://github.com/drtablebasse)
- Site web: [homepage.drtablebasse.fr](https://homepage.drtablebasse.fr)

## 🙏 Remerciements

- Discord.py pour l'API Discord
- PostgreSQL pour la base de données
- Rich pour l'interface console
- APScheduler pour la planification des tâches
- BeautifulSoup pour le parsing HTML
- Pillow pour le traitement d'images 