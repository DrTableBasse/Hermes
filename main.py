import discord
from discord import Embed, Colour
from discord.ext import commands
import os
import sys
import json
from utils.constants import cogs_names, BOT_CHANNEL_START  # Assurez-vous d'avoir l'ID du salon dans vos constants
# from utils.logging import log_command_usage
from rich.console import Console
from rich.table import Table

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from PIL import Image
from io import BytesIO
from collections import Counter
from apscheduler.schedulers.asyncio import AsyncIOScheduler

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

def get_dominant_color(image_url):
    """
    Récupère la couleur dominante d'une image via son URL.
    Merci GPT
    """
    response = requests.get(image_url)
    img = Image.open(BytesIO(response.content))

    # Redimensionne l'image pour accélérer le processus (plus petite taille)
    img = img.resize((100, 100))

    # Convertir en mode RGB et récupérer les couleurs
    img = img.convert('RGB')
    pixels = list(img.getdata())

    # Compter les couleurs et obtenir la couleur dominante
    color_counts = Counter(pixels)
    dominant_color = color_counts.most_common(1)[0][0]  # Récupère la couleur la plus fréquente
    return discord.Color.from_rgb(*dominant_color)  # Renvoie la couleur sous forme de discord.Color


def get_articles():
    """Scrape les articles du site et retourne une liste (titre, lien, date, image)."""
    r = requests.get("https://animotaku.fr/actualite-manga-anime/")
    print(r.status_code)
    soup = BeautifulSoup(r.text, "html.parser")
    articles = []

    containers = soup.find_all("div", class_="elementor-posts-container")

    for container in containers:
        for article in container.find_all("article", class_="elementor-post"):

            title_tag = article.find("h3", class_="elementor-post__title")
            title_link = title_tag.find("a") if title_tag else None
            title = title_link.text.strip() if title_link else "Titre non trouvé"
            link = title_link["href"] if title_link else "Pas de lien"


            date_tag = article.find("span", class_="elementor-post-date")
            date = date_tag.text.strip() if date_tag else "Date non trouvée"

            thumbnail_tag = article.find("a", class_="elementor-post__thumbnail__link")
            img_tag = thumbnail_tag.find("img") if thumbnail_tag else None
            if img_tag:
                thumbnail_url = img_tag.get("data-lazy-src", img_tag.get("src", "Pas d'image"))
                if thumbnail_url.startswith("//"):
                    thumbnail_url = "https:" + thumbnail_url
            else:
                thumbnail_url = "Pas d'image"

            articles.append((title, link, date, thumbnail_url))

    return articles


def filter_articles():
    MONTHS_EN_FR = {
        "January": "janvier",
        "February": "février",
        "March": "mars",
        "April": "avril",
        "May": "mai",
        "June": "juin",
        "July": "juillet",
        "August": "août",
        "September": "septembre",
        "October": "octobre",
        "November": "novembre",
        "December": "décembre",
    }
    yesterday = datetime.now() - timedelta(days=1)
    day = yesterday.strftime("%d").lstrip("0")
    month_en = yesterday.strftime("%B")
    year = yesterday.strftime("%Y")

    month_fr = MONTHS_EN_FR[month_en]
    formatted_yesterday = f"{day} {month_fr} {year}"

    articles = get_articles()

    return [a for a in articles if a[2].strip().lower() == formatted_yesterday.lower()]


async def send_articles():
    CHANNEL_ID = 768885611595038722 
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("❌ Erreur : Canal non trouvé.")
        return

    articles = filter_articles()
    if not articles:
        await channel.send("📭 Aucun article publié hier.")
        return

    for title, link, date, thumbnail in articles:
        color = get_dominant_color(thumbnail)
        embed = discord.Embed(title=title,
                        url=link,
                        colour=color)

        embed.set_author(name="Yù",
                        url="https://github.com/YuToutCourt",
                        icon_url="https://avatars.githubusercontent.com/u/63105226?v=4")

        embed.set_image(url=thumbnail)

        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1027875503144701952/1337007021618364476/2c8e477cf2875f06776c14b5f112e90a.png?ex=67a5e052&is=67a48ed2&hm=8c6dc97b68fa7fa11a765e0bae71434650927b50e2c4e7dee5fef72a23c54bec&")

        embed.set_footer(text=f"📰 Date de publication : {date}")

        await channel.send(embed=embed)

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
    channel = guild.get_channel(BOT_CHANNEL_START)
    if not channel:
        print('\033[91m[ERROR] \033[97mSalon spécifié non trouvé.\033[0m')
        return
    
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_articles, "cron", hour=18, minute=00) # Modifier l'heure ou le bot va request le site
    scheduler.start()

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
    
      # Vérifie si le bot a été mentionné
    if bot.user.mentioned_in(message):
        # Remplacez le chemin par l'endroit où votre vidéo est stockée
        video_path = 'src/ping.mp4'  # Local path ou URL
        
        # Envoyer la vidéo
        await message.reply(
            "Arrête de me mentionner tocard ! Wouaf ! 🐶",
            file=discord.File(video_path)  # Envoie la vidéo
        )
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
