"""
Module de gestion des statuts de commandes pour Hermes Bot

Ce module gère l'activation/désactivation des commandes du bot via une base de données PostgreSQL.
Il inclut un système de cache pour optimiser les performances et des fonctions utilitaires
pour la gestion des commandes.

Fonctionnalités:
- Gestion des statuts de commandes (activé/désactivé)
- Cache en mémoire pour optimiser les performances
- Support des commandes globales et spécifiques au serveur
- Décorateur pour vérifier automatiquement le statut des commandes
- Initialisation automatique de la table de base de données
- Logging des changements de statut des commandes

Auteur: Dr.TableBasse
Version: 2.1
"""

import asyncio
import functools
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable
import discord
from utils.database import DatabaseManager
from utils.logging import log_command_usage

# Cache en mémoire pour les statuts de commandes
COMMAND_STATUS_CACHE: Dict[str, bool] = {}
CACHE_EXPIRY: Dict[str, datetime] = {}
CACHE_DURATION = timedelta(minutes=5)  # Cache valide pendant 5 minutes

async def log_command_status_change(interaction: discord.Interaction, command_name: str, is_enabled: bool, guild_id: Optional[int] = None):
    """
    Log les changements de statut des commandes.
    
    Args:
        interaction (discord.Interaction): L'interaction Discord
        command_name (str): Nom de la commande
        is_enabled (bool): Nouveau statut (True = activé, False = désactivé)
        guild_id (Optional[int]): ID du serveur (optionnel)
    """
    try:
        guild = interaction.guild
        if not guild:
            return
            
        # Utiliser le canal de log des commandes ou le canal de log principal
        log_channel_id = None
        try:
            from utils.constants import get_env_var
            command_log_id = get_env_var('COMMAND_LOG_CHANNEL_ID', required=False)
            if command_log_id and command_log_id.isdigit():
                log_channel_id = int(command_log_id)
        except:
            pass
            
        if not log_channel_id:
            try:
                from utils.constants import get_env_var
                log_channel_id = int(get_env_var('LOG_CHANNEL_ID', required=True))
            except:
                print("⚠️ Impossible de récupérer l'ID du canal de log")
                return
                
        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            print(f"⚠️ Canal de log non trouvé: {log_channel_id}")
            return
            
        # Créer l'embed de log
        status_text = "✅ Activée" if is_enabled else "❌ Désactivée"
        status_icon = "✅" if is_enabled else "❌"
        color = discord.Color.green() if is_enabled else discord.Color.red()
        
        scope_text = f"serveur **{guild.name}**" if guild_id else "**globalement**"
        
        embed = discord.Embed(
            title=f"{status_icon} Changement de Statut de Commande",
            description=f"**Commande:** `/{command_name}`\n**Nouveau statut:** {status_text}\n**Portée:** {scope_text}",
            color=color,
            timestamp=datetime.now()
        )
        
        embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
        embed.add_field(name="👤 Modérateur", value=interaction.user.mention, inline=True)
        embed.add_field(name="📅 Date", value=datetime.now().strftime("%d/%m/%Y %H:%M:%S"), inline=True)
        
        # Vérifier que le canal est un TextChannel avant d'utiliser mention
        if hasattr(interaction.channel, 'mention'):
            embed.add_field(name="📍 Canal", value=interaction.channel.mention, inline=True)
        
        # Ajouter les permissions du modérateur
        if hasattr(interaction.user, 'guild_permissions') and interaction.user.guild_permissions:
            permissions = []
            if interaction.user.guild_permissions.administrator:
                permissions.append("👑 Admin")
            if interaction.user.guild_permissions.manage_guild:
                permissions.append("⚙️ Gestionnaire Serveur")
            if interaction.user.guild_permissions.manage_roles:
                permissions.append("🔑 Gestionnaire Rôles")
            if permissions:
                embed.add_field(name="🔐 Permissions", value=", ".join(permissions), inline=True)
        
        # Vérifier que le canal peut envoyer des messages
        if hasattr(log_channel, 'send'):
            await log_channel.send(embed=embed)
        
    except Exception as e:
        print(f"❌ Erreur lors du log du changement de statut: {e}")

def get_db_connection() -> Optional[DatabaseManager]:
    """
    Récupère une connexion à la base de données.
    
    Returns:
        DatabaseManager: Instance du gestionnaire de base de données ou None si erreur
    """
    try:
        return DatabaseManager()
    except Exception as e:
        print(f"❌ Erreur lors de la connexion à la base de données: {e}")
        return None

class CommandStatusManager:
    """
    Gestionnaire centralisé des statuts des commandes.
    
    Cette classe fournit des méthodes pour gérer l'activation/désactivation
    des commandes du bot via une base de données PostgreSQL avec cache.
    """
    
    @staticmethod
    async def get_command_status(command_name: str, guild_id: Optional[int] = None, use_cache: bool = True) -> bool:
        """
        Récupère le statut d'une commande depuis la base de données.
        
        Args:
            command_name (str): Nom de la commande
            guild_id (Optional[int]): ID du serveur (optionnel)
            use_cache (bool): Utiliser le cache en mémoire
            
        Returns:
            bool: True si la commande est activée, False sinon
        """
        cache_key = f"{command_name}_{guild_id}" if guild_id else command_name
        
        if use_cache:
            if cache_key in COMMAND_STATUS_CACHE:
                if datetime.now() < CACHE_EXPIRY.get(cache_key, datetime.min):
                    return COMMAND_STATUS_CACHE[cache_key]
                else:
                    del COMMAND_STATUS_CACHE[cache_key]
                    if cache_key in CACHE_EXPIRY:
                        del CACHE_EXPIRY[cache_key]
        
        try:
            db_manager = get_db_connection()
            if db_manager is None:
                print("⚠️ Base de données non disponible, retour du statut par défaut")
                return True
                
            await db_manager.initialize()
            
            async with db_manager.get_connection() as conn:
                if guild_id:
                    row = await conn.fetchrow("""
                        SELECT is_enabled FROM command_status 
                        WHERE command_name = $1 AND guild_id = $2
                    """, command_name, guild_id)
                else:
                    row = await conn.fetchrow("""
                        SELECT is_enabled FROM command_status 
                        WHERE command_name = $1 AND guild_id IS NULL
                    """, command_name)
                    
                if row is not None:
                    status = row['is_enabled']
                else:
                    status = True
                    await CommandStatusManager.set_command_status(command_name, True, guild_id)
                    
                if use_cache:
                    COMMAND_STATUS_CACHE[cache_key] = status
                    CACHE_EXPIRY[cache_key] = datetime.now() + CACHE_DURATION
                    
                return status
                
        except Exception as e:
            print(f"❌ Erreur lors de la récupération du statut de la commande {command_name}: {e}")
            return True
    
    @staticmethod
    async def set_command_status(command_name: str, is_enabled: bool, guild_id: Optional[int] = None, interaction: Optional[discord.Interaction] = None) -> bool:
        """
        Définit le statut d'une commande.
        
        Args:
            command_name (str): Nom de la commande
            is_enabled (bool): True pour activer, False pour désactiver
            guild_id (Optional[int]): ID du serveur (optionnel)
            interaction (Optional[discord.Interaction]): Interaction Discord pour le logging
            
        Returns:
            bool: True si succès, False sinon
        """
        try:
            db_manager = get_db_connection()
            if db_manager is None:
                print("⚠️ Base de données non disponible")
                return False
                
            await db_manager.initialize()
                
            async with db_manager.get_connection() as conn:
                if guild_id:
                    # Upsert pour commande spécifique au serveur
                    await conn.execute("""
                        INSERT INTO command_status (command_name, guild_id, is_enabled, updated_at)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (command_name, guild_id) 
                        DO UPDATE SET is_enabled = EXCLUDED.is_enabled, updated_at = EXCLUDED.updated_at
                    """, command_name, guild_id, is_enabled, datetime.now())
                else:
                    # Upsert pour commande globale
                    await conn.execute("""
                        INSERT INTO command_status (command_name, guild_id, is_enabled, updated_at)
                        VALUES ($1, NULL, $2, $3)
                        ON CONFLICT (command_name, guild_id) 
                        DO UPDATE SET is_enabled = EXCLUDED.is_enabled, updated_at = EXCLUDED.updated_at
                    """, command_name, is_enabled, datetime.now())
                
                # Invalider le cache
                cache_key = f"{command_name}_{guild_id}" if guild_id else command_name
                if cache_key in COMMAND_STATUS_CACHE:
                    del COMMAND_STATUS_CACHE[cache_key]
                if cache_key in CACHE_EXPIRY:
                    del CACHE_EXPIRY[cache_key]
                
                # Logger le changement si une interaction est fournie
                if interaction:
                    await log_command_status_change(interaction, command_name, is_enabled, guild_id)
                
                return True
                
        except Exception as e:
            print(f"❌ Erreur lors de la définition du statut de la commande {command_name}: {e}")
            return False
    
    @staticmethod
    async def get_all_command_status(guild_id: Optional[int] = None) -> Dict[str, bool]:
        """
        Récupère le statut de toutes les commandes.
        
        Args:
            guild_id (Optional[int]): ID du serveur (optionnel)
            
        Returns:
            Dict[str, bool]: Dictionnaire {nom_commande: statut}
        """
        try:
            db_manager = get_db_connection()
            if db_manager is None:
                print("⚠️ Base de données non disponible")
                return {}
                
            await db_manager.initialize()
                
            async with db_manager.get_connection() as conn:
                if guild_id:
                    rows = await conn.fetch("""
                        SELECT command_name, is_enabled FROM command_status 
                        WHERE guild_id = $1 OR guild_id IS NULL
                        ORDER BY command_name
                    """, guild_id)
                else:
                    rows = await conn.fetch("""
                        SELECT command_name, is_enabled FROM command_status 
                        WHERE guild_id IS NULL
                        ORDER BY command_name
                    """)
                
                return {row['command_name']: row['is_enabled'] for row in rows}
                
        except Exception as e:
            print(f"❌ Erreur lors de la récupération de tous les statuts: {e}")
            return {}
    
    @staticmethod
    async def clear_cache():
        """
        Vide le cache des statuts de commandes.
        
        Returns:
            None
        """
        global COMMAND_STATUS_CACHE, CACHE_EXPIRY
        COMMAND_STATUS_CACHE.clear()
        CACHE_EXPIRY.clear()
        print("🧹 Cache des statuts de commandes vidé")

def command_enabled(guild_specific: bool = False):
    """
    Décorateur pour vérifier automatiquement si une commande est activée.
    
    Ce décorateur vérifie le statut de la commande avant son exécution
    et envoie un message d'erreur si la commande est désactivée.
    
    Args:
        guild_specific (bool): True si la commande est spécifique au serveur
        
    Returns:
        Callable: Fonction décorée
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            # Utiliser le nom réel de la commande Discord
            command_name = getattr(interaction.command, 'name', func.__name__)
            guild_id: Optional[int] = interaction.guild_id if guild_specific else None
            
            # Désactivation du cache : on vérifie toujours en base
            is_enabled = await CommandStatusManager.get_command_status(command_name, guild_id, use_cache=False)
            
            if not is_enabled:
                await interaction.response.send_message(
                    f"❌ La commande `/{command_name}` est actuellement désactivée.",
                    ephemeral=True
                )
                return
                
            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator

async def init_command_status_table():
    """
    Initialise la table command_status dans la base de données.
    
    Cette fonction crée la table si elle n'existe pas et configure
    les index nécessaires pour optimiser les performances.
    
    Returns:
        None
    """
    try:
        db_manager = get_db_connection()
        if db_manager is None:
            print("⚠️ Base de données non disponible pour l'initialisation")
            return
            
        await db_manager.initialize()
            
        async with db_manager.get_connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS command_status (
                    id SERIAL PRIMARY KEY,
                    command_name VARCHAR(100) NOT NULL,
                    guild_id BIGINT,
                    is_enabled BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(command_name, guild_id)
                )
            """)
            
            # Créer un index pour améliorer les performances
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_command_status_name_guild 
                ON command_status(command_name, guild_id)
            """)
            
            print("✅ Table command_status initialisée")
                
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation de la table command_status: {e}") 