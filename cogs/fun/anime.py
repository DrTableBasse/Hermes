import requests
import discord
from discord import app_commands
from discord.ext import commands, tasks
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from PIL import Image
from io import BytesIO
from collections import Counter
import asyncio

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


async def send_articles(bot):
    CHANNEL_ID = 1388804969129574500
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("❌ Erreur : Canal non trouvé.")
        return

    print(f"🔍 Vérification des articles pour le canal {CHANNEL_ID}...")
    articles = filter_articles()
    print(f"📰 {len(articles)} articles trouvés")
    
    if not articles:
        print("📭 Aucun article publié hier.")
        await channel.send("📭 Aucun article publié hier.")
        return

    ANIME_DECTECTOR = ["anime", "épisode", "episode", "épisodes", "episodes"]

    for title, link, date, thumbnail in articles:
            info = "Anime" if any(dec in title.lower() for dec in ANIME_DECTECTOR) else "Manga" if "manga" in title.lower() else ""
            color = get_dominant_color(thumbnail)
            embed = discord.Embed(title=f"{info} News !",
                            description=title,
                            url=link,
                            colour=color)

            embed.set_author(name="Yù",
                            url="https://github.com/YuToutCourt",
                            icon_url="https://avatars.githubusercontent.com/u/63105226?v=4")

            embed.set_image(url=thumbnail)

            embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1027875503144701952/1337007021618364476/2c8e477cf2875f06776c14b5f112e90a.png?ex=67a5e052&is=67a48ed2&hm=8c6dc97b68fa7fa11a765e0bae71434650927b50e2c4e7dee5fef72a23c54bec&")

            embed.set_footer(text=f"📰 Date de publication : {date}\nFonctionnalité développée par Yù, car Dr.Tablebasse ne sait pas coder !")

            await channel.send(embed=embed)


class Article(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Démarrer automatiquement la tâche de fond
        self.anime_check.start()

    @tasks.loop(hours=24)
    async def anime_check(self):
        try:
            print("🔄 Tâche de fond exécutée - Vérification des articles...")
            await send_articles(self.bot)
        except Exception as e:
            print(f"❌ Erreur dans la tâche de fond: {e}")

    @anime_check.before_loop
    async def before_anime_check(self):
        await self.bot.wait_until_ready()
        print("✅ Bot prêt - Tâche de fond démarrée")

    @app_commands.command(name="check_articles", description="Vérifier et envoyer les articles d'hier")
    async def check_articles(self, interaction: discord.Interaction):
        """
        Commande slash pour vérifier et envoyer les articles d'hier.
        """
        await interaction.response.send_message("🔍 Vérification des articles d'hier...")
        await send_articles(self.bot)

    def cog_unload(self):
        self.anime_check.cancel()


async def setup(bot):
    await bot.add_cog(Article(bot))
