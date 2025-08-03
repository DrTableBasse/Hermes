# 🤖 Hermes Bot - Bot Discord Multifonctionnel

<div align="center">

![Discord](https://img.shields.io/badge/Discord-7289DA?style=for-the-badge&logo=discord&logoColor=white)
![Python](https://img.shields.io/badge/Python-FFD43B?style=for-the-badge&logo=python&logoColor=blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)

**Bot Discord intelligent et moderne pour la communauté SaucisseLand**

[🚀 Installation](#-installation) • [✨ Fonctionnalités](#-fonctionnalités) • [📚 Documentation](#-documentation) • [🤝 Contribution](#-contribution)

</div>

---

## 🎯 Présentation

**Hermes Bot** est un bot Discord multifonctionnel conçu pour la communauté **SaucisseLand**. Il combine modération avancée, gestion vocale intelligente, intégration d'articles anime et fonctionnalités divertissantes dans une solution complète et moderne.

### 🌟 Points Forts

- **🛡️ Modération Complète** : Système d'avertissements, sanctions temporaires, gestion des rôles
- **🎤 Gestion Vocale Avancée** : Suivi automatique du temps vocal avec classements
- **📰 Intégration Anime** : Récupération automatique d'articles depuis Animotaku.fr
- **🎮 Fonctionnalités Fun** : Blagues, confessions anonymes, jeux
- **⚙️ Administration Avancée** : Gestion dynamique des commandes, logs détaillés
- **🗄️ Base de Données PostgreSQL** : Persistance robuste et performances optimales

---

## ✨ Fonctionnalités

### 🛡️ Système de Modération

| Fonctionnalité | Description | Commandes |
|----------------|-------------|-----------|
| **Avertissements** | Système complet avec base de données | `/warn`, `/check-warn` |
| **Sanctions Temporaires** | Bannissement et mute temporaires | `/tempban`, `/tempmute` |
| **Expulsion & Bannissement** | Sanctions permanentes | `/kick`, `/ban` |
| **Mute/Unmute** | Contrôle vocal des utilisateurs | `/mute`, `/unmute` |
| **Nettoyage** | Suppression de messages | `/clear` |
| **Règlement** | Affichage des règles du serveur | `/reglement` |

### 🎤 Gestion Vocale Intelligente

- **Suivi Automatique** : Enregistrement du temps passé en vocal
- **Classements** : Top des utilisateurs les plus actifs
- **Attribution de Rôles** : Rôles automatiques basés sur le temps vocal
- **Logs Détaillés** : Historique complet des événements vocaux
- **Commandes** : `/voice`, `/check-voice`

### 📰 Intégration Articles Anime

- **Récupération Automatique** : Articles depuis Animotaku.fr
- **Filtrage Intelligent** : Articles d'hier uniquement
- **Système de Cache** : Évite les doublons
- **Envoi Automatique** : Toutes les 5 minutes
- **Commandes** : `/anime-status`, `/anime-cache`

### 🎮 Fonctionnalités Divertissantes

- **Système de Blagues** : API Blagues intégrée
- **Confessions Anonymes** : Système de confessions sécurisé
- **Jeux** : Commandes de divertissement
- **Gestion des Rôles** : Attribution automatique

### ⚙️ Administration Avancée

- **Gestion des Commandes** : Activation/désactivation dynamique
- **Système de Cache** : Optimisation des performances
- **Logs Système** : Interface console moderne avec Rich
- **Scheduler** : Planification des tâches automatiques
- **Logs Membres** : Suivi des arrivées/départs

---

## 🚀 Installation

### 📋 Prérequis

- **Python** 3.8 ou supérieur
- **PostgreSQL** 12 ou supérieur
- **Token Discord Bot** (créé via [Discord Developer Portal](https://discord.com/developers/applications))
- **Serveur Discord** avec permissions administrateur

### 🔧 Configuration Rapide

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

# Initialiser les tables
psql -d saucisseland -f init-postgres.sql
```

4. **Configurer l'environnement**
```bash
cp env.example .env
# Éditer .env avec vos configurations
```

### 🔐 Variables d'Environnement

Créez un fichier `.env` avec les variables suivantes :

```env
# === CONFIGURATION DISCORD (OBLIGATOIRE) ===
DISCORD_TOKEN=your_discord_bot_token
GUILD_ID=your_guild_id

# === CONFIGURATION API (OBLIGATOIRE) ===
BLAGUES_API_TOKEN=your_blagues_api_token

# === CANAUX DISCORD (OBLIGATOIRE) ===
BOT_CHANNEL_START=your_bot_channel_id
LOG_CHANNEL_ID=your_log_channel_id
VOICE_LOG_CHANNEL_ID=your_voice_log_channel_id
CONFESSION_CHANNEL_ID=your_confession_channel_id
ANIME_NEWS_CHANNEL_ID=your_anime_news_channel_id
WELCOME_CHANNEL_ID=your_welcome_channel_id
MEMBER_LOGS_CHANNEL_ID=your_member_logs_channel_id

# === RÔLES DISCORD (OBLIGATOIRE) ===
AUTHORIZED_ROLES=role1,role2,role3
ROLE_BATMAN=your_batman_role_name
VOICE_HOURS_FOR_ROLE=100

# === CONFIGURATION POSTGRESQL (OBLIGATOIRE) ===
PG_HOST=localhost
PG_PORT=5432
PG_DB=saucisseland
PG_USER=your_database_user
PG_PASSWORD=your_database_password

# === URLS (OBLIGATOIRE) ===
ANIME_THUMBNAIL_URL=your_anime_thumbnail_url
ANIME_AUTHOR_AVATAR_URL=your_anime_author_avatar_url
```

### 🚀 Démarrage

```bash
# Validation de la configuration
python config.py

# Configuration des commandes
python setup_command_status_table.py

# Démarrage du bot
python main.py
```

---

## 📚 Documentation

### 🏗️ Architecture

```
Hermes/
├── 📁 cogs/                    # Modules de commandes
│   ├── 🎮 fun/                # Commandes divertissantes
│   │   ├── anime.py           # Intégration articles anime
│   │   ├── blague.py          # Système de blagues
│   │   ├── confess.py         # Confessions anonymes
│   │   └── games.py           # Jeux et divertissement
│   ├── 🛡️ moderation/        # Outils de modération
│   │   ├── voice.py           # Gestion vocale
│   │   ├── warn.py            # Système d'avertissements
│   │   ├── kick.py            # Expulsion
│   │   ├── ban.py             # Bannissement
│   │   ├── mute.py            # Mute/Unmute
│   │   └── ...                # Autres commandes
│   └── ⚙️ system/            # Commandes système
│       ├── command_management.py # Gestion des commandes
│       ├── member_logs.py     # Logs des membres
│       └── reload.py          # Rechargement
├── 📁 utils/                  # Utilitaires
│   ├── database.py            # Gestionnaire PostgreSQL
│   ├── command_manager.py     # Gestion des commandes
│   ├── constants.py           # Constantes
│   └── logging.py             # Système de logs
├── 📁 scripts/                # Scripts utilitaires
├── main.py                    # Point d'entrée
├── config.py                  # Configuration
└── requirements.txt           # Dépendances
```

### 🗄️ Base de Données

**Tables principales :**
- `user_voice_data` : Statistiques vocales des utilisateurs
- `warn` : Avertissements et sanctions
- `user_message_stats` : Statistiques des messages
- `command_status` : Statuts des commandes (activé/désactivé)

### 🔧 Commandes Principales

#### 🛡️ Modération
| Commande | Description | Utilisation |
|----------|-------------|-------------|
| `/warn` | Avertir un utilisateur | `/warn @user raison` |
| `/check-warn` | Voir les avertissements | `/check-warn @user` |
| `/kick` | Expulser un utilisateur | `/kick @user raison` |
| `/ban` | Bannir un utilisateur | `/ban @user raison` |
| `/mute` | Muter un utilisateur | `/mute @user durée raison` |
| `/tempban` | Bannir temporairement | `/tempban @user durée raison` |

#### 🎤 Vocal
| Commande | Description | Utilisation |
|----------|-------------|-------------|
| `/voice` | Voir le temps vocal | `/voice [@user]` |
| `/check-voice` | Classement vocal | `/check-voice [nombre]` |

#### 📰 Articles Anime
| Commande | Description | Utilisation |
|----------|-------------|-------------|
| `/anime-status` | Statut de la récupération | `/anime-status` |
| `/anime-cache` | Gérer le cache | `/anime-cache [action]` |

#### ⚙️ Administration
| Commande | Description | Utilisation |
|----------|-------------|-------------|
| `/command-management` | Gérer les commandes | `/command-management` |
| `/reload` | Recharger les cogs | `/reload` |
| `/shutdown` | Arrêter le bot | `/shutdown` |

---

## 🛠️ Développement

### 📝 Ajouter une Nouvelle Commande

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
        is_enabled = await CommandStatusManager.get_command_status(
            command_name, 
            guild_id=interaction.guild_id, 
            use_cache=False
        )
        
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

2. **Redémarrer le bot** - La commande sera automatiquement ajoutée

### 🧹 Scripts de Maintenance

```bash
# Nettoyer les fichiers temporaires
python scripts/cleanup_project.py

# Nettoyer l'environnement
python scripts/clean_env.py

# Migrer de SQLite vers PostgreSQL
python scripts/migrate_sqlite_to_postgres.py
```

---

## 📊 Statistiques

- **+15 commandes** de modération
- **+10 commandes** fun et divertissement
- **+5 commandes** système et administration
- **Base de données PostgreSQL** pour la persistance
- **Interface console moderne** avec Rich
- **Logs détaillés** pour le debugging

---

## 🔄 Intégration Site Web

Le bot est conçu pour s'intégrer avec le site web **SaucisseLand** :

- **Articles automatiques** : Récupération quotidienne depuis Animotaku.fr
- **Base de données partagée** : PostgreSQL pour la persistance
- **API REST** : Communication bidirectionnelle
- **Authentification unifiée** : Système commun

---

## 📝 Changelog

### 🆕 Version 2.0 (Actuelle)
- ✅ Migration complète vers PostgreSQL
- ✅ Système de gestion des commandes avec activation/désactivation
- ✅ Intégration articles anime avec cache intelligent
- ✅ Nettoyage complet du code et ajout de docstrings
- ✅ Suppression des commandes de test
- ✅ Interface console moderne avec Rich
- ✅ Gestion avancée des erreurs et logging
- ✅ Scripts de maintenance et nettoyage

### 📜 Version 1.x
- Système de modération basique
- Gestion vocale avec SQLite
- Commandes fun et divertissement

---

## 🤝 Contribution

Nous accueillons les contributions ! Voici comment participer :

1. **Fork** le projet
2. **Créer** une branche feature (`git checkout -b feature/AmazingFeature`)
3. **Commit** les changements (`git commit -m 'Add some AmazingFeature'`)
4. **Push** vers la branche (`git push origin feature/AmazingFeature`)
5. **Ouvrir** une Pull Request

### 📋 Guidelines

- Respectez le style de code existant
- Ajoutez des tests pour les nouvelles fonctionnalités
- Documentez les nouvelles commandes
- Testez sur un serveur de développement

---

## 📄 Licence

Ce projet est sous licence **MIT**. Voir le fichier [`LICENSE`](LICENSE) pour plus de détails.

---

## 👨‍💻 Auteur

**Dr.TableBasse**
- 🌐 **Site web** : [homepage.drtablebasse.fr](https://homepage.drtablebasse.fr)
- 🐙 **GitHub** : [@drtablebasse](https://github.com/drtablebasse)

---

## 🙏 Remerciements

- **Discord.py** pour l'API Discord
- **PostgreSQL** pour la base de données robuste
- **Rich** pour l'interface console moderne
- **APScheduler** pour la planification des tâches
- **BeautifulSoup** pour le parsing HTML
- **Pillow** pour le traitement d'images

---

<div align="center">

**⭐ N'oubliez pas de mettre une étoile si ce projet vous a aidé ! ⭐**

</div> 