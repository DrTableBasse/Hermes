import os
import asyncio
import logging
from datetime import datetime, timedelta
from io import BytesIO
from collections import Counter

import discord
from discord import app_commands
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
from PIL import Image

from utils import settings
from utils.command_manager import command_enabled

logger = logging.getLogger(__name__)

MONTHS_EN_FR = {
    "January": "janvier", "February": "février", "March": "mars",
    "April": "avril", "May": "mai", "June": "juin",
    "July": "juillet", "August": "août", "September": "septembre",
    "October": "octobre", "November": "novembre", "December": "décembre",
}


def _get_dominant_color(image_url: str) -> discord.Color:
    try:
        resp = requests.get(image_url, timeout=10)
        img = Image.open(BytesIO(resp.content)).resize((100, 100)).convert('RGB')
        dominant = Counter(img.getdata()).most_common(1)[0][0]
        return discord.Color.from_rgb(*dominant)
    except Exception:
        return discord.Color.blurple()


def _fetch_articles() -> list:
    r = requests.get("https://animotaku.fr/actualite-manga-anime/", timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    articles = []
    for container in soup.find_all("div", class_="elementor-posts-container"):
        for article in container.find_all("article", class_="elementor-post"):
            title_tag = article.find("h3", class_="elementor-post__title")
            title_link = title_tag.find("a") if title_tag else None
            title = title_link.text.strip() if title_link else "Titre non trouvé"
            link = title_link["href"] if title_link else "#"

            date_tag = article.find("span", class_="elementor-post-date")
            date = date_tag.text.strip() if date_tag else ""

            thumbnail_tag = article.find("a", class_="elementor-post__thumbnail__link")
            img_tag = thumbnail_tag.find("img") if thumbnail_tag else None
            thumbnail_url = ""
            if img_tag:
                thumbnail_url = img_tag.get("data-lazy-src", img_tag.get("src", ""))
                if thumbnail_url.startswith("//"):
                    thumbnail_url = "https:" + thumbnail_url

            articles.append((title, link, date, thumbnail_url))
    return articles


def _filter_yesterday(articles: list) -> list:
    yesterday = datetime.now() - timedelta(days=1)
    day = yesterday.strftime("%d").lstrip("0")
    month_fr = MONTHS_EN_FR[yesterday.strftime("%B")]
    year = yesterday.strftime("%Y")
    target = f"{day} {month_fr} {year}".lower()
    return [a for a in articles if a[2].strip().lower() == target]


class AnimeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.anime_check.start()

    def cog_unload(self):
        self.anime_check.cancel()

    async def _news_channel(self):
        """Salon des actualités ; ``None`` si le réglage est vide (fonction désactivée)."""
        guild = self.bot.get_guild(int(os.getenv('GUILD_ID', '0') or '0'))
        return await settings.configured_channel(guild, 'anime_news_channel')

    async def _send_articles(self, channel: discord.TextChannel, articles: list):
        thumbnail_url = settings.get('anime_thumbnail_url')
        author_avatar_url = settings.get('anime_author_avatar_url')
        anime_keywords = {"anime", "épisode", "episode", "épisodes", "episodes"}
        for title, link, date, thumbnail in articles:
            title_lower = title.lower()
            if any(k in title_lower for k in anime_keywords):
                category = "Anime"
            elif "manga" in title_lower:
                category = "Manga"
            else:
                category = ""

            color = await asyncio.to_thread(_get_dominant_color, thumbnail) if thumbnail else discord.Color.blurple()

            embed = discord.Embed(
                title=f"{category} News !" if category else "News !",
                description=title,
                url=link,
                colour=color,
            )
            embed.set_author(
                name="Yù",
                url="https://github.com/YuToutCourt",
                icon_url=author_avatar_url or discord.utils.MISSING,
            )
            if thumbnail:
                embed.set_image(url=thumbnail)
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)
            embed.set_footer(text=f"📰 Date de publication : {date}\nFonctionnalité développée par Yù")

            await channel.send(embed=embed)

    @tasks.loop(hours=24)
    async def anime_check(self):
        if not settings.get('anime_news_channel'):
            return
        channel = await self._news_channel()
        if not channel:
            logger.warning("AnimeCog: salon des actualités anime introuvable")
            return
        try:
            articles = await asyncio.to_thread(_fetch_articles)
            articles = _filter_yesterday(articles)
            logger.info(f"AnimeCog: {len(articles)} article(s) trouvé(s) pour hier")
            if articles:
                await self._send_articles(channel, articles)
        except Exception as e:
            logger.error(f"AnimeCog: erreur lors de la vérification: {e}")

    @anime_check.before_loop
    async def before_anime_check(self):
        await self.bot.wait_until_ready()
        await settings.ready.wait()  # salon et URL lus dès le premier tour

    @app_commands.command(name="check_articles", description="Vérifie et envoie les articles anime/manga d'hier")
    @command_enabled()
    async def check_articles(self, interaction: discord.Interaction):
        await interaction.response.send_message("🔍 Vérification des articles d'hier...", ephemeral=True)
        if not settings.get('anime_news_channel'):
            await interaction.followup.send("⚠️ Salon des actualités anime non configuré.", ephemeral=True)
            return
        channel = await self._news_channel()
        if not channel:
            await interaction.followup.send("⚠️ Canal introuvable.", ephemeral=True)
            return
        articles = await asyncio.to_thread(_fetch_articles)
        articles = _filter_yesterday(articles)
        if not articles:
            await interaction.followup.send("📭 Aucun article publié hier.", ephemeral=True)
            return
        await self._send_articles(channel, articles)
        await interaction.followup.send(f"✅ {len(articles)} article(s) envoyé(s).", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AnimeCog(bot))
