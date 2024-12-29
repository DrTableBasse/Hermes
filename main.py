import discord
from discord import Embed, Colour
from discord.ext import commands
import os
import sys
import json
from utils.constants import cogs_names, LOG_CHANNEL_ID  # Assurez-vous d'avoir l'ID du salon dans vos constants
from utils.logging import log_command_usage
from rich.console import Console
from rich.table import Table

console = Console()

# Ajoute le répertoire Hermes au chemin d'importation
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'cogs')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'utils')))

# Importer la configuration
from config import TOKEN, GUILD_ID

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='/', intents=intents)

# Charger la liste des commandes depuis le fichier JSON
def load_commands():
    try:
        with open("list-commands.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# Sauvegarder les commandes dans le fichier JSON
def save_commands(commands_data):
    with open("list-commands.json", "w") as f:
        json.dump(commands_data, f, indent=4)

# Charger les cogs avec affichage propre
async def load_cogs():
    table = Table(title="Chargement des Cogs", show_lines=True)

    # Ajouter les colonnes
    table.add_column("Nom du Cog", justify="left", style="cyan", no_wrap=True)
    table.add_column("Statut", justify="center", style="green")

    for cog in cogs_names():
        try:
            await bot.load_extension(f'{cog}')
            # Ajouter une ligne pour les cogs chargés avec succès
            table.add_row(cog, "[bold green]✅ Chargé")
        except Exception:
            # Ajouter une ligne pour les cogs échoués (si nécessaire)
            table.add_row(cog, "[bold red]❌ Erreur")

    # Afficher le tableau
    console.print(table)

# Commande pour lister les commandes disponibles
@bot.tree.command(name="list-command", description="Liste toutes les commandes disponibles.")
async def list_commands(interaction: discord.Interaction):
    commands_data = load_commands()

    # Créer un embed pour afficher les commandes
    embed = discord.Embed(title="Commandes disponibles", color=discord.Color.blue())
    
    # Ajouter les commandes et leurs statuts sous forme de champs dans l'embed
    for command, status in commands_data.items():
        status_text = "Activée ✅" if status else "Désactivée ❌"
        
        # Ajouter un champ pour le nom de la commande (inline=True pour être côte à côte)
        embed.add_field(
            name=f"/{command}", 
            value=status_text,  # Afficher l'état de la commande dans le champ de la commande
            inline=True
        )

    if not embed.fields:
        await interaction.response.send_message("Aucune commande disponible.", ephemeral=True)
        return

    await interaction.response.send_message(embed=embed)

# Commande pour activer une commande
@bot.tree.command(name="enable-command", description="Activer une commande.")
async def enable_command(interaction: discord.Interaction, command_name: str):
    commands_data = load_commands()
    
    if command_name in commands_data and commands_data[command_name]:
        await interaction.response.send_message(f"La commande /{command_name} est déjà activée.", ephemeral=True)
        return
    
    commands_data[command_name] = True
    save_commands(commands_data)
    await interaction.response.send_message(f"La commande /{command_name} a été activée.", ephemeral=True)

# Commande pour désactiver une commande
@bot.tree.command(name="disable-command", description="Désactiver une commande.")
async def disable_command(interaction: discord.Interaction, command_name: str):
    commands_data = load_commands()
    
    if command_name in commands_data and not commands_data[command_name]:
        await interaction.response.send_message(f"La commande /{command_name} est déjà désactivée.", ephemeral=True)
        return
    
    commands_data[command_name] = False
    save_commands(commands_data)
    await interaction.response.send_message(f"La commande /{command_name} a été désactivée.", ephemeral=True)

from discord import Embed, Colour

@bot.event
async def on_ready():
    print(f'\033[92m[INFO] \033[94mBot connecté en tant que {bot.user.name}\033[0m')  # Message d'info dans le terminal

    # Vérifie si le serveur existe
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        print('\033[91m[ERROR] \033[97mServeur non trouvé.\033[0m')
        return

    # Vérifie si le salon existe
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if not channel:
        print('\033[91m[ERROR] \033[97mSalon spécifié non trouvé.\033[0m')
        return

    try:
        # Création de l'embed
        embed = Embed(
            title="Hermes au pied ! 🐾",
            description="Bark Bark ! Je suis prêt à servir ! 🐶\n"
                        "[Clique ici pour voir mon développeur ❤️](https://homepage.drtablebasse.fr)",
            colour=Colour.blue()  # Bleu ciel
        )

        # Ajout de la photo de profil du bot
        avatar_url = bot.user.avatar.url if bot.user.avatar else bot.user.default_avatar.url
        embed.set_thumbnail(url=avatar_url)

        # Ajout des informations supplémentaires
        embed.add_field(name="Nom du Bot", value=f"{bot.user.name}", inline=False)
        embed.add_field(name="Github du Bot",value=f"[Github](https://github.com/drtablebasse/Hermes)", inline=False)

        # Ajout d'un footer
        embed.set_footer(text="Développé avec ❤️ par Dr.TableBasse")

        # Envoi de l'embed dans le salon
        await channel.send(embed=embed)
        print(f'\033[92m[INFO] \033[94mMessage envoyé avec succès dans le salon {channel.name}\033[0m')
    except Exception as e:
        print(f'\033[91m[ERROR] \033[97mUne erreur est survenue lors de l\'envoi du message: {e}\033[0m')


    # await load_cogs()

    # Synchronisation des commandes sur le serveur
    bot.tree.copy_global_to(guild=discord.Object(id=GUILD_ID))
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print("\033[92m[INFO] \033[94mCommandes synchronisées avec le serveur\033[0m")

# Vérification avant l'exécution de la commande
@bot.event
async def on_message(message):
    # Ignore les messages du bot lui-même pour éviter des boucles infinies
    if message.author == bot.user:
        return

    # Vérifie si la commande est dans le fichier list-commands.json
    commands_data = load_commands()
    command_name = message.content.split()[0][1:]  # Récupère le nom de la commande
    if command_name in commands_data and not commands_data[command_name]:
        await message.reply(f"La commande /{command_name} est actuellement désactivée.", ephemeral=True)
        return

    # Assurez-vous que les autres commandes et événements fonctionnent correctement
    await bot.process_commands(message)

# Charger les cogs et démarrer le bot
async def main():
    await load_cogs()
    await bot.start(TOKEN)

# Exécuter le bot
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
