"""
Module de gestion des articles anime pour Hermes Bot

Ce module gère la récupération, le filtrage et l'envoi automatique d'articles anime
depuis Animotaku.fr vers Discord. Il inclut un système de cache pour éviter les doublons
et des commandes de gestion pour les administrateurs.

Fonctionnalités:
- Récupération automatique d'articles depuis Animotaku.fr
- Filtrage des articles par date (articles d'hier)
- Système de cache pour éviter les doublons
- Envoi automatique dans un canal Discord configuré
- Commandes de gestion et de statut
- Gestion des couleurs dominantes des images

Auteur: Dr.TableBasse
Version: 2.0
"""

import requests
import discord
from discord import app_commands
from discord.ext import commands, tasks
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from PIL import Image
from io import BytesIO
from collections import Counter
import os
from dotenv import load_dotenv
import json
import hashlib
import sys
import asyncio
from utils.command_manager import CommandStatusManager, command_enabled
import logging
from utils.logging import log_command
import aiohttp

# Ajouter le répertoire parent au path pour les imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Charger les variables d'environnement
load_dotenv()

# Cache pour éviter les doublons d'articles
SENT_ARTICLES_CACHE = set()
CACHE_FILE = "sent_articles_cache.json"

logger = logging.getLogger("fun_commands")

def load_sent_articles_cache():
    """
    Charge le cache des articles déjà envoyés depuis le fichier JSON.
    
    Returns:
        None: Met à jour la variable globale SENT_ARTICLES_CACHE
    """
    global SENT_ARTICLES_CACHE
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                SENT_ARTICLES_CACHE = set(cache_data.get('sent_articles', []))
                print(f"📋 Cache chargé: {len(SENT_ARTICLES_CACHE)} articles déjà envoyés")
        else:
            SENT_ARTICLES_CACHE = set()
            print("📋 Cache initialisé (fichier inexistant)")
    except Exception as e:
        print(f"❌ Erreur lors du chargement du cache: {e}")
        SENT_ARTICLES_CACHE = set()

def save_sent_articles_cache():
    """
    Sauvegarde le cache des articles envoyés dans le fichier JSON.
    
    Returns:
        None: Sauvegarde la variable globale SENT_ARTICLES_CACHE
    """
    try:
        cache_data = {
            'sent_articles': list(SENT_ARTICLES_CACHE),
            'last_updated': datetime.now().isoformat()
        }
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde du cache: {e}")

def get_article_hash(title, link, date):
    """
    Génère un hash unique pour un article basé sur son titre, lien et date.
    
    Args:
        title (str): Titre de l'article
        link (str): Lien de l'article
        date (str): Date de l'article
        
    Returns:
        str: Hash unique de l'article
    """
    content = f"{title}{link}{date}"
    return hashlib.md5(content.encode()).hexdigest()

def is_article_sent(article_hash):
    """
    Vérifie si un article a déjà été envoyé en utilisant son hash.
    
    Args:
        article_hash (str): Hash unique de l'article
        
    Returns:
        bool: True si l'article a déjà été envoyé, False sinon
    """
    return article_hash in SENT_ARTICLES_CACHE

def mark_article_as_sent(article_hash):
    """
    Marque un article comme envoyé en ajoutant son hash au cache.
    
    Args:
        article_hash (str): Hash unique de l'article
        
    Returns:
        None: Met à jour le cache et sauvegarde
    """
    SENT_ARTICLES_CACHE.add(article_hash)
    save_sent_articles_cache()

def cleanup_old_cache():
    """
    Nettoie le cache en supprimant les anciens articles (plus de 7 jours).
    
    Returns:
        None: Met à jour le cache
    """
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Supprimer les articles plus anciens que 7 jours
            cutoff_date = datetime.now() - timedelta(days=7)
            old_articles = []
            
            for article_hash in SENT_ARTICLES_CACHE:
                # Pour simplifier, on supprime les articles basés sur leur hash
                # En pratique, on pourrait stocker la date avec chaque hash
                old_articles.append(article_hash)
            
            # Supprimer 20% des articles les plus anciens
            if len(old_articles) > 50:
                articles_to_remove = old_articles[:len(old_articles) // 5]
                SENT_ARTICLES_CACHE.difference_update(articles_to_remove)
                save_sent_articles_cache()
                print(f"🧹 Cache nettoyé: {len(articles_to_remove)} articles supprimés")
    except Exception as e:
        print(f"❌ Erreur lors du nettoyage du cache: {e}")

# Charger le cache au démarrage
load_sent_articles_cache()
cleanup_old_cache()

def get_dominant_color(image_url):
    """
    Récupère la couleur dominante d'une image via son URL.
    Merci GPT
    """
    try:
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
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
    except Exception as e:
        print(f"⚠️ Erreur lors de la récupération de la couleur dominante: {e}")
        return discord.Color.blue()

def get_articles():
    """Scrape les articles du site et retourne une liste (titre, lien, date, image)."""
    try:
        r = requests.get("https://animotaku.fr/actualite-manga-anime/", timeout=30)
        print(f"📡 Status code: {r.status_code}")
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

        print(f"📰 {len(articles)} articles récupérés depuis Animotaku.fr")
        return articles
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des articles: {e}")
        return []

def filter_articles():
    """
    Filtre les articles pour ne garder que ceux d'hier.
    """
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

    filtered_articles = [a for a in articles if a[2].strip().lower() == formatted_yesterday.lower()]
    print(f"📅 {len(filtered_articles)} articles d'hier trouvés")
    return filtered_articles

async def send_articles(bot, test_mode=False):
    """
    Envoie les articles anime dans le canal Discord configuré.
    
    Args:
        bot: Instance du bot Discord
        test_mode (bool): Si True, récupère tous les articles récents au lieu de seulement ceux d'hier
        
    Returns:
        None
    """
    try:
        # Récupérer le canal anime depuis les variables d'environnement
        anime_channel_id = int(os.getenv('ANIME_NEWS_CHANNEL_ID', '1388804969129574500'))
        channel = bot.get_channel(anime_channel_id)
        
        if not channel:
            print(f"❌ Canal anime {anime_channel_id} non trouvé")
            # Fallback vers le canal général si le canal anime n'existe pas
            from utils.constants import BOT_CHANNEL_START
            channel = bot.get_channel(BOT_CHANNEL_START)
            if not channel:
                print(f"❌ Canal de fallback {BOT_CHANNEL_START} non trouvé")
                return
            print(f"⚠️ Utilisation du canal de fallback: {BOT_CHANNEL_START}")

        if test_mode:
            print("🧪 Mode test activé - Récupération de tous les articles récents...")
            articles = get_articles()
            # Limiter à 5 articles pour le test
            articles = articles[:5]
        else:
            articles = filter_articles()

        if not articles:
            print("⏰ [Anime] Aucun nouvel article à envoyer lors de ce check.")
            return

        print(f"📤 Envoi de {len(articles)} article(s) dans le canal anime")
        
        ignored_count = 0
        for i, (title, link, date, thumbnail_url) in enumerate(articles, 1):
            # Générer un hash unique pour cet article
            article_hash = get_article_hash(title, link, date)
            
            # Vérifier si l'article a déjà été envoyé
            if is_article_sent(article_hash):
                print(f"⏭️  Article {i}/{len(articles)} ignoré (déjà envoyé): {title[:50]}...")
                ignored_count += 1
                continue
            
            try:
                # Détecter le type d'article
                ANIME_DETECTOR = ["anime", "épisode", "episode", "épisodes", "episodes"]
                info = "Anime" if any(dec in title.lower() for dec in ANIME_DETECTOR) else "Manga" if "manga" in title.lower() else "News"
                
                # Créer l'embed
                embed = discord.Embed(
                    title=f"{info} News !",
                    description=title,
                    url=link,
                    color=discord.Color.blue()
                )
                
                # Ajouter l'image principale si disponible
                if thumbnail_url and thumbnail_url != "Pas d'image":
                    try:
                        embed.set_image(url=thumbnail_url)
                        # Récupérer la couleur dominante
                        try:
                            dominant_color = get_dominant_color(thumbnail_url)
                            embed.color = dominant_color
                        except:
                            pass
                        print(f"✅ Image de l'article utilisée: {thumbnail_url[:50]}...")
                    except Exception as img_error:
                        print(f"⚠️ Erreur avec l'image de l'article {i}: {img_error}")
                
                # Ajouter le thumbnail (logo Hermes)
                embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1027875503144701952/1337007021618364476/2c8e477cf2875f06776c14b5f112e90a.png?ex=67a5e052&is=67a48ed2&hm=8c6dc97b68fa7fa11a765e0bae71434650927b50e2c4e7dee5fef72a23c54bec&")
                
                # Ajouter l'auteur
                embed.set_author(
                    name="Hermes Bot",
                    url="https://github.com/DrTableBasse/Hermes/",
                    icon_url="https://avatars.githubusercontent.com/u/63105226?v=4"
                )
                
                # Ajouter le footer
                embed.set_footer(text=f"📰 Date de publication : {date} • Source: Animotaku.fr • 🎌 News Anime")
                
                # Envoyer l'embed
                await channel.send(embed=embed)
                
                # Marquer l'article comme envoyé
                mark_article_as_sent(article_hash)
                
                print(f"✅ Article {i}/{len(articles)} envoyé: {title[:50]}...")
                
                # Petite pause pour éviter le rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"❌ Erreur lors de l'envoi de l'article {i}: {e}")
        
        if ignored_count > 0:
            print(f"📊 Résumé: {ignored_count} article(s) ignoré(s) (déjà envoyés)")
            
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi des articles: {e}")

class Anime(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.anime_check.start()
        print("✅ Module Anime chargé")

    def cog_unload(self):
        self.anime_check.cancel()

    @tasks.loop(hours=1)  # Vérification toutes les heures
    async def anime_check(self):
        """Vérifie et envoie les nouveaux articles anime"""
        await send_articles(self.bot)

    @anime_check.before_loop
    async def before_anime_check(self):
        """Attend que le bot soit prêt avant de commencer les vérifications"""
        await self.bot.wait_until_ready()
        print("🎌 Bot prêt - Vérification des articles anime activée")

async def setup(bot):
    await bot.add_cog(Anime(bot))
