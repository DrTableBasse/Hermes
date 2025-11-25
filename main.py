"""
Module principal d'Hermes Bot - Bot Discord multifonctionnel

Ce module contient le point d'entrée principal du bot Discord Hermes.
Il gère l'initialisation, la configuration, le chargement des cogs et
le démarrage du bot avec toutes ses fonctionnalités.

Fonctionnalités principales:
- Initialisation et configuration du bot Discord
- Chargement automatique des cogs (modules de commandes)
- Gestion de la base de données PostgreSQL
- Système de planification des tâches (scheduler)
- Gestion des événements Discord (messages, mentions)
- Synchronisation des commandes slash avec Discord
- Validation de la configuration et des variables d'environnement

Dépendances:
- discord.py: API Discord
- rich: Interface console colorée
- apscheduler: Planification des tâches
- dotenv: Gestion des variables d'environnement

Auteur: Dr.TableBasse
Version: 2.0
"""

import discord
from discord import Embed, Colour
from discord.ext import commands
import os
import sys
import json
import asyncio
import threading

# Ajouter le répertoire courant au chemin d'importation AVANT les imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Importer les modules avec gestion d'erreur
try:
    from utils.constants import cogs_names
    from utils.database import init_database, voice_manager, warn_manager
    from utils.command_manager import init_command_status_table
    from config import validate_config, TOKEN_BLAGUE_API
except ImportError as e:
    print(f"❌ Erreur d'importation: {e}")
    print(f"📁 Répertoire courant: {current_dir}")
    print(f"📁 Contenu du répertoire:")
    for item in os.listdir(current_dir):
        print(f"   - {item}")
    print(f"📁 Contenu du dossier utils:")
    utils_dir = os.path.join(current_dir, 'utils')
    if os.path.exists(utils_dir):
        for item in os.listdir(utils_dir):
            print(f"   - {item}")
    else:
        print("   ❌ Dossier utils non trouvé!")
    sys.exit(1)

from rich.console import Console
from rich.table import Table
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

console = Console()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='/', intents=intents)

async def load_cogs():
    """
    Charge tous les cogs (modules de commandes) du bot.
    
    Cette fonction charge dynamiquement tous les cogs définis dans utils.constants
    et affiche un tableau de statut pour chaque cog chargé.
    
    Returns:
        None
    """
    table = Table(title="Chargement des Cogs", show_lines=True)

    # Ajouter les colonnes
    table.add_column("Nom du Cog", justify="left", style="cyan", no_wrap=True)
    table.add_column("Statut", justify="center", style="green")

    loaded_cogs = 0
    total_cogs = len(cogs_names())

    for cog in cogs_names():
        try:
            await bot.load_extension(f'{cog}')
            table.add_row(cog, "[bold green]✅ Chargé")
            loaded_cogs += 1
        except Exception as e:
            table.add_row(cog, f"[bold red]❌ Erreur: {str(e)[:30]}...")
            console.print(f"[red]Erreur détaillée pour {cog}: {e}[/red]")

    # Afficher le tableau
    console.print(table)
    console.print(f"[green]📊 {loaded_cogs}/{total_cogs} cogs chargés avec succès[/green]")

@bot.event
async def on_ready():
    """
    Événement déclenché quand le bot se connecte avec succès à Discord.
    
    Cette fonction:
    1. Valide la configuration du bot
    2. Vérifie les variables d'environnement
    3. Initialise la base de données
    4. Configure le scheduler pour les tâches automatiques
    5. Envoie un message de démarrage
    6. Charge les cogs
    7. Synchronise les commandes slash
    8. Configure l'instance du bot pour l'API
    
    Returns:
        None
    """
    console.print(f'[green]✅ Bot connecté en tant que {bot.user.name}[/green]')

    # Configurer l'instance du bot pour l'API
    try:
        from api import set_bot_instance
        set_bot_instance(bot)
        console.print('[green]✅ Instance du bot configurée pour l\'API[/green]')
    except Exception as e:
        console.print(f'[yellow]⚠️ Impossible de configurer l\'API: {e}[/yellow]')
    
    # Vérifier la configuration
    try:
        validate_config()
    except ValueError as e:
        console.print(f'[red]❌ Erreur de configuration: {e}[/red]')
        return

    # Récupérer les variables d'environnement
    GUILD_ID = os.getenv('GUILD_ID')
    BOT_CHANNEL_START = os.getenv('BOT_CHANNEL_START')
    
    if not GUILD_ID:
        console.print('[red]❌ Variable d\'environnement GUILD_ID manquante dans le fichier .env[/red]')
        return
    if not BOT_CHANNEL_START:
        console.print('[red]❌ Variable d\'environnement BOT_CHANNEL_START manquante dans le fichier .env[/red]')
        return
        
    GUILD_ID = int(GUILD_ID)
    BOT_CHANNEL_START = int(BOT_CHANNEL_START)

    # Vérifie si le serveur existe
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        console.print('[red]❌ Serveur non trouvé.[/red]')
        return

    # Vérifie si le salon existe
    channel = guild.get_channel(BOT_CHANNEL_START)
    if not channel:
        console.print(f'[red]❌ Salon spécifié non trouvé pour BOT_CHANNEL_START (valeur: {BOT_CHANNEL_START})[/red]')
        return
    
    # Initialiser la base de données
    try:
        await init_database()
        console.print('[green]✅ Base de données initialisée[/green]')
        
        # Initialiser la table des statuts de commandes
        await init_command_status_table()
        console.print('[green]✅ Table des statuts de commandes initialisée[/green]')
    except Exception as e:
        console.print(f'[red]❌ Erreur d\'initialisation de la base de données: {e}[/red]')
        return
    
    # Synchroniser tous les membres du serveur dans la base de données (APRÈS l'initialisation)
    try:
        from utils.database import voice_manager
        if GUILD_ID:
            guild = bot.get_guild(int(GUILD_ID))
            if guild:
                console.print(f'[cyan]🔄 Synchronisation des membres du serveur {guild.name}...[/cyan]')
                # Charger tous les membres (même ceux hors ligne) avec chunk
                await guild.chunk(cache=True)
                synced = 0
                # Itérer sur tous les membres maintenant chargés
                for member in guild.members:
                    if not member.bot:
                        nickname = member.display_name if member.display_name != member.name else None
                        await voice_manager.sync_member(member.id, member.name, nickname)
                        synced += 1
                console.print(f'[green]✅ {synced} membres synchronisés dans la base de données[/green]')
    except Exception as e:
        console.print(f'[yellow]⚠️ Erreur lors de la synchronisation des membres: {e}[/yellow]')



    try:
        # Création de l'embed
        embed = Embed(
            title="Hermes au pied ! 🐾",
            description="Bark Bark ! Je suis prêt à servir ! 🐶\n"
                        "[Clique ici pour voir mon développeur ❤️](https://homepage.drtablebasse.fr)",
            colour=Colour.blue()
        )

        # Ajout de la photo de profil du bot
        avatar_url = bot.user.avatar.url if bot.user.avatar else bot.user.default_avatar.url
        embed.set_thumbnail(url=avatar_url)

        # Ajout des informations supplémentaires
        embed.add_field(name="Nom du Bot", value=f"{bot.user.name}", inline=False)
        embed.add_field(name="Github du Bot", value=f"[Github](https://github.com/drtablebasse/Hermes)", inline=False)

        # Ajout d'un footer
        embed.set_footer(text="Développé avec ❤️ par Dr.TableBasse")

        # Envoi de l'embed dans le salon
        await channel.send(embed=embed)
        console.print(f'[green]✅ Message envoyé avec succès dans le salon {channel.name}[/green]')
    except Exception as e:
        console.print(f'[red]❌ Erreur lors de l\'envoi du message: {e}[/red]')

    # Charger les cogs
    await load_cogs()

    # Synchronisation des commandes sur le serveur
    try:
        bot.tree.copy_global_to(guild=discord.Object(id=GUILD_ID))
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        console.print("[green]✅ Commandes synchronisées avec le serveur[/green]")
    except Exception as e:
        console.print(f'[red]❌ Erreur de synchronisation des commandes: {e}[/red]')

    with open('.env', 'r', encoding='utf-8') as f:
        print('--- CONTENU .env ---')
        print(f.read())
        print('--------------------')
    print('Valeur brute de COMMAND_LOG_CHANNEL_ID:', os.getenv('COMMAND_LOG_CHANNEL_ID'))

@bot.event
async def on_message(message):
    """
    Événement déclenché à chaque message reçu sur le serveur.
    
    Cette fonction gère:
    - Les mentions du bot (réponse avec une vidéo)
    - Le traitement des commandes normales
    - La prévention des boucles infinies
    
    Args:
        message: Objet message Discord reçu
        
    Returns:
        None
    """
    # Ignore les messages du bot lui-même pour éviter des boucles infinies
    if message.author == bot.user:
        return
    
    # Vérifie si le bot a été mentionné
    if bot.user.mentioned_in(message):
        try:
            # Remplacez le chemin par l'endroit où votre vidéo est stockée
            video_path = 'src/ping.mp4'
            
            # Vérifier si le fichier existe
            if os.path.exists(video_path):
                await message.reply(
                    "Arrête de me mentionner tocard ! Wouaf ! 🐶",
                    file=discord.File(video_path)
                )
            else:
                await message.reply("Arrête de me mentionner tocard ! Wouaf ! 🐶")
        except Exception as e:
            console.print(f'[red]Erreur lors de l\'envoi de la vidéo: {e}[/red]')
            await message.reply("Arrête de me mentionner tocard ! Wouaf ! 🐶")
        return

    # Assurez-vous que les autres commandes et événements fonctionnent correctement
    await bot.process_commands(message)

def start_api():
    """Démarre le serveur API dans un thread séparé"""
    try:
        from api import set_bot_instance, run_api
        set_bot_instance(bot)
        run_api()
    except Exception as e:
        console.print(f'[red]❌ Erreur lors du démarrage de l\'API: {e}[/red]')

async def main():
    """
    Fonction principale d'initialisation et de démarrage du bot.
    
    Cette fonction:
    1. Récupère le token Discord depuis les variables d'environnement
    2. Valide la présence du token
    3. Démarre le bot avec le token
    4. Démarre l'API web en parallèle
    
    Returns:
        None
    """
    try:
        # Démarrer l'API dans un thread séparé
        api_thread = threading.Thread(target=start_api, daemon=True)
        api_thread.start()
        console.print('[green]✅ API web démarrée[/green]')
        
        # Récupérer le token Discord depuis les variables d'environnement
        TOKEN = os.getenv('DISCORD_TOKEN')
        if not TOKEN:
            console.print('[red]❌ Token Discord manquant dans les variables d\'environnement[/red]')
            return
            
        await bot.start(TOKEN)
    except Exception as e:
        console.print(f'[red]❌ Erreur lors du démarrage du bot: {e}[/red]')

# Exécuter le bot
if __name__ == "__main__":
    asyncio.run(main())
