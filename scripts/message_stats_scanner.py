"""
Script de scan des messages Discord pour les statistiques

Ce script va scanner tous les messages du serveur Discord pour :
1. Compter le nombre total de messages par utilisateur
2. Compter le nombre de messages par salon
3. Exclure les catégories spécifiées

Auteur: Dr.TableBasse
"""

import discord
import asyncio
import os
from dotenv import load_dotenv
import psycopg2
from datetime import datetime
import logging

# Charger les variables d'environnement
load_dotenv()

# Configuration
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID'))

# Catégories à exclure
EXCLUDED_CATEGORIES = [
    777116825250168852,
    777139814599491584,
    989815462755962890
]

# Configuration PostgreSQL
PG_HOST = os.getenv('PG_HOST')
PG_USER = os.getenv('PG_USER')
PG_DB = os.getenv('PG_DB')
PG_PASSWORD = os.getenv('PG_PASSWORD')

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MessageStatsScanner:
    def __init__(self):
        intents = discord.Intents.all()
        intents.message_content = True
        intents.guilds = True
        intents.messages = True
        self.client = discord.Client(intents=intents)
        self.user_message_counts = {}
        self.channel_message_counts = {}
        self.total_messages_scanned = 0
        self.start_time = None
        
    async def connect_db(self):
        """Connexion à la base de données PostgreSQL"""
        try:
            self.db_conn = psycopg2.connect(
                host=PG_HOST,
                user=PG_USER,
                password=PG_PASSWORD,
                database=PG_DB
            )
            self.db_cursor = self.db_conn.cursor()
            logger.info("✅ Connexion à la base de données réussie")
        except Exception as e:
            logger.error(f"❌ Erreur de connexion à la base: {e}")
            raise
    
    def get_valid_channels(self, guild):
        """Récupère tous les canaux textuels valides (excluant les catégories spécifiées)"""
        valid_channels = []
        
        for channel in guild.channels:
            # Vérifier si c'est un canal textuel
            if isinstance(channel, discord.TextChannel):
                # Vérifier si la catégorie est exclue
                if channel.category_id in EXCLUDED_CATEGORIES:
                    logger.info(f"🚫 Canal exclu (catégorie {channel.category_id}): {channel.name}")
                    continue
                
                valid_channels.append(channel)
                logger.info(f"✅ Canal inclus: {channel.name} (ID: {channel.id})")
        
        logger.info(f"📊 Total des canaux valides: {len(valid_channels)}")
        return valid_channels
    
    async def scan_channel_messages(self, channel):
        """Scanne tous les messages d'un canal"""
        logger.info(f"🔍 Scan du canal: {channel.name}")
        
        try:
            message_count = 0
            last_save_count = 0
            
            async for message in channel.history(limit=None):
                # Compter pour l'utilisateur
                user_id = message.author.id
                if user_id not in self.user_message_counts:
                    self.user_message_counts[user_id] = 0
                self.user_message_counts[user_id] += 1
                
                # Compter pour le canal
                channel_id = channel.id
                if channel_id not in self.channel_message_counts:
                    self.channel_message_counts[channel_id] = 0
                self.channel_message_counts[channel_id] += 1
                
                message_count += 1
                self.total_messages_scanned += 1
                
                # Affichage en temps réel tous les 10 messages
                if self.total_messages_scanned % 10 == 0:
                    print(f"{self.total_messages_scanned} messages scannés")
                
                # Log tous les 500 messages avec progression globale
                if message_count % 500 == 0:
                    logger.info(f"📝 {channel.name}: {message_count:,} messages | Total global: {self.total_messages_scanned:,}")
                
                # Sauvegarde progressive tous les 2000 messages
                if self.total_messages_scanned - last_save_count >= 2000:
                    await self.save_progress()
                    last_save_count = self.total_messages_scanned
                    
                    # Calculer le temps écoulé et la vitesse
                    if self.start_time:
                        elapsed_time = datetime.now() - self.start_time
                        speed = self.total_messages_scanned / elapsed_time.total_seconds()
                        logger.info(f"💾 Sauvegarde progressive: {self.total_messages_scanned:,} messages traités | Temps: {elapsed_time} | Vitesse: {speed:.1f} msg/s")
                    else:
                        logger.info(f"💾 Sauvegarde progressive: {self.total_messages_scanned:,} messages traités")
            
            logger.info(f"✅ {channel.name}: {message_count:,} messages au total")
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du scan de {channel.name}: {e}")
    
    async def save_progress(self):
        """Sauvegarde progressive des données sans vider les tables"""
        try:
            # Sauvegarder les stats utilisateurs (UPSERT)
            for user_id, message_count in self.user_message_counts.items():
                self.db_cursor.execute("""
                    INSERT INTO user_message_stats (user_id, channel_id, message_count)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, channel_id) 
                    DO UPDATE SET message_count = EXCLUDED.message_count
                """, (user_id, 0, message_count))
            
            # Sauvegarder les stats par canal (UPSERT)
            for channel_id, message_count in self.channel_message_counts.items():
                self.db_cursor.execute("""
                    INSERT INTO channel_message_stats (channel_id, message_count, last_updated)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (channel_id) 
                    DO UPDATE SET message_count = EXCLUDED.message_count, last_updated = EXCLUDED.last_updated
                """, (channel_id, message_count, datetime.now()))
            
            self.db_conn.commit()
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la sauvegarde progressive: {e}")
            self.db_conn.rollback()

    async def save_to_database(self):
        """Sauvegarde finale des statistiques dans la base de données"""
        try:
            # Vider les tables existantes
            self.db_cursor.execute("DELETE FROM user_message_stats")
            self.db_cursor.execute("DELETE FROM channel_message_stats")
            logger.info("🗑️ Tables vidées")
            
            # Insérer les stats utilisateurs
            for user_id, message_count in self.user_message_counts.items():
                self.db_cursor.execute("""
                    INSERT INTO user_message_stats (user_id, channel_id, message_count)
                    VALUES (%s, %s, %s)
                """, (user_id, 0, message_count))  # channel_id = 0 pour le total global
            
            # Insérer les stats par canal
            for channel_id, message_count in self.channel_message_counts.items():
                self.db_cursor.execute("""
                    INSERT INTO channel_message_stats (channel_id, message_count, last_updated)
                    VALUES (%s, %s, %s)
                """, (channel_id, message_count, datetime.now()))
            
            self.db_conn.commit()
            logger.info(f"💾 {len(self.user_message_counts)} utilisateurs et {len(self.channel_message_counts)} canaux sauvegardés")
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la sauvegarde: {e}")
            self.db_conn.rollback()
    
    async def run_scan(self):
        """Lance le scan complet"""
        logger.info("🚀 Début du scan des messages Discord")
        self.start_time = datetime.now()
        
        try:
            # Connexion à la base
            await self.connect_db()
            
            # Démarrer le client Discord
            await self.client.start(TOKEN)
            
            # Attendre que le client soit prêt
            await self.client.wait_until_ready()
            
            # Récupérer le serveur
            guild = self.client.get_guild(GUILD_ID)
            if not guild:
                logger.error(f"❌ Serveur {GUILD_ID} non trouvé")
                return
            
            logger.info(f"🎯 Serveur trouvé: {guild.name}")
            
            # Récupérer les canaux valides
            valid_channels = self.get_valid_channels(guild)
            
            # Scanner chaque canal
            for channel in valid_channels:
                await self.scan_channel_messages(channel)
            
            # Sauvegarder dans la base
            await self.save_to_database()
            
            # Calculer le temps écoulé
            end_time = datetime.now()
            duration = end_time - self.start_time
            
            # Afficher le résumé
            logger.info("📊 RÉSUMÉ DU SCAN:")
            logger.info(f"   - Messages scannés: {self.total_messages_scanned:,}")
            logger.info(f"   - Utilisateurs uniques: {len(self.user_message_counts)}")
            logger.info(f"   - Canaux scannés: {len(self.channel_message_counts)}")
            logger.info(f"   - Temps écoulé: {duration}")
            logger.info(f"   - Vitesse: {self.total_messages_scanned / duration.total_seconds():.1f} messages/seconde")
            
            # Top 10 utilisateurs
            top_users = sorted(self.user_message_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            logger.info("🏆 TOP 10 UTILISATEURS:")
            for i, (user_id, count) in enumerate(top_users, 1):
                user = guild.get_member(user_id)
                username = user.display_name if user else f"User_{user_id}"
                logger.info(f"   {i}. {username}: {count} messages")
            
            # Top 10 canaux
            top_channels = sorted(self.channel_message_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            logger.info("📺 TOP 10 CANAUX:")
            for i, (channel_id, count) in enumerate(top_channels, 1):
                channel = guild.get_channel(channel_id)
                channel_name = channel.name if channel else f"Channel_{channel_id}"
                logger.info(f"   {i}. #{channel_name}: {count} messages")
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du scan: {e}")
        finally:
            if hasattr(self, 'db_conn'):
                self.db_conn.close()
            await self.client.close()

async def main():
    """Fonction principale"""
    scanner = MessageStatsScanner()
    await scanner.run_scan()

if __name__ == "__main__":
    asyncio.run(main()) 