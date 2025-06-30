"""
Exemple de fichier principal avec le système de logging automatique

Ce fichier montre comment configurer votre bot pour utiliser le logging automatique.
"""

import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import logging

# Charger les variables d'environnement
load_dotenv()

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Configuration du bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    """Événement déclenché quand le bot est prêt"""
    print(f'🤖 {bot.user} est connecté et prêt!')
    print(f'📊 Servant {len(bot.guilds)} serveur(s)')
    print(f'👥 {len(bot.users)} utilisateur(s) total')
    
    # Synchroniser les commandes slash
    try:
        synced = await bot.tree.sync()
        print(f'✅ {len(synced)} commande(s) slash synchronisée(s)')
    except Exception as e:
        print(f'❌ Erreur lors de la synchronisation: {e}')

async def load_extensions():
    """Charge tous les cogs du bot"""
    print("🔄 Chargement des extensions...")
    
    # Liste des cogs à charger
    extensions = [
        # Système (charger en premier)
        "cogs.system.command_logger",  # 🔥 LOGGING AUTOMATIQUE
        "cogs.system.command_management",
        "cogs.system.member_logs",
        "cogs.system.reload",
        "cogs.system.shutdown",
        
        # Modération
        "cogs.moderation.warn",
        "cogs.moderation.kick",
        "cogs.moderation.ban",
        "cogs.moderation.mute",
        "cogs.moderation.tempmute",
        "cogs.moderation.tempban",
        "cogs.moderation.unmute",
        "cogs.moderation.clear",
        "cogs.moderation.reglement",
        "cogs.moderation.role_assignment",
        "cogs.moderation.voice",
        "cogs.moderation.check_voice",
        "cogs.moderation.check_warn",
        "cogs.moderation.list_users",
        
        # Fun
        "cogs.fun.blague",
        "cogs.fun.anime",
        "cogs.fun.confess",
        "cogs.fun.games",
        
        # Autres
        "cogs.ddl",
    ]
    
    loaded_count = 0
    failed_count = 0
    
    for extension in extensions:
        try:
            await bot.load_extension(extension)
            print(f'✅ {extension} chargé')
            loaded_count += 1
        except Exception as e:
            print(f'❌ Erreur lors du chargement de {extension}: {e}')
            failed_count += 1
    
    print(f"\n📊 Résumé du chargement:")
    print(f"✅ {loaded_count} extension(s) chargée(s) avec succès")
    if failed_count > 0:
        print(f"❌ {failed_count} extension(s) en échec")
    
    # Message spécial pour le logging automatique
    print("\n🚀 SYSTÈME DE LOGGING AUTOMATIQUE ACTIVÉ!")
    print("📝 Toutes les commandes seront automatiquement loggées")
    print("🎯 Aucune modification de code requise dans vos commandes")

@bot.event
async def on_command_error(ctx, error):
    """Gestion globale des erreurs de commandes"""
    if isinstance(error, commands.CommandNotFound):
        return  # Ignorer les commandes non trouvées
    
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Vous n'avez pas les permissions nécessaires pour cette commande.", delete_after=10)
        return
    
    if isinstance(error, commands.BotMissingPermissions):
        await ctx.send("❌ Je n'ai pas les permissions nécessaires pour exécuter cette commande.", delete_after=10)
        return
    
    # Log l'erreur
    logging.error(f"Erreur de commande non gérée: {error}")
    
    # Message générique pour l'utilisateur
    await ctx.send("❌ Une erreur inattendue s'est produite. Veuillez réessayer.", delete_after=10)

async def main():
    """Fonction principale"""
    print("🚀 Démarrage d'Hermes Bot avec logging automatique...")
    
    # Charger les extensions
    await load_extensions()
    
    # Démarrer le bot
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ DISCORD_TOKEN non trouvé dans le fichier .env")
        return
    
    try:
        await bot.start(token)
    except KeyboardInterrupt:
        print("\n🛑 Arrêt du bot...")
    except Exception as e:
        print(f"❌ Erreur lors du démarrage: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 