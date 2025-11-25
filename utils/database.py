"""
Module de gestion de base de données PostgreSQL pour Hermes Bot

Ce module fournit une interface complète pour la gestion de la base de données
PostgreSQL avec pool de connexions, gestion d'erreurs et managers spécialisés
pour différentes fonctionnalités du bot.

Fonctionnalités:
- Gestionnaire de base de données avec pool de connexions
- Managers spécialisés (Voice, Warn, UserMessageStats)
- Gestion sécurisée des transactions
- Requêtes optimisées avec gestion d'erreurs
- Support des opérations batch
- Logging automatique des opérations

Classes principales:
- DatabaseManager: Gestionnaire principal de base de données
- VoiceDataManager: Gestion des données vocales des utilisateurs
- WarnManager: Gestion des avertissements
- UserMessageStatsManager: Statistiques des messages

Auteur: Dr.TableBasse
Version: 2.0
"""

import asyncpg
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any, Tuple
import logging
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration PostgreSQL
def get_postgres_config():
    """Récupère la configuration PostgreSQL depuis les variables d'environnement"""
    pg_port = os.getenv('PG_PORT', '5432')
    try:
        port = int(pg_port) if pg_port else 5432
    except (ValueError, TypeError):
        port = 5432
    
    return {
        'host': os.getenv('PG_HOST', 'localhost'),
        'port': port,
        'database': os.getenv('PG_DB', ''),
        'user': os.getenv('PG_USER', ''),
        'password': os.getenv('PG_PASSWORD', '')
    }

POSTGRES_CONFIG = get_postgres_config()

class DatabaseManager:
    """
    Gestionnaire de base de données PostgreSQL avec pool de connexions et gestion d'erreurs.
    
    Cette classe fournit une interface sécurisée pour interagir avec la base de données
    PostgreSQL en utilisant un pool de connexions pour optimiser les performances.
    
    Fonctionnalités:
    - Pool de connexions automatique
    - Gestion sécurisée des transactions
    - Requêtes optimisées avec gestion d'erreurs
    - Support des opérations batch
    """
    
    def __init__(self):
        """
        Initialise le gestionnaire de base de données.
        
        Returns:
            None
        """
        self._pool = None
        self._lock = asyncio.Lock()
        self._pool_loop = None  # Stocker la boucle d'événements du pool
        
    async def initialize(self):
        """
        Initialise le pool de connexions PostgreSQL.
        
        Cette méthode crée un pool de connexions avec les paramètres
        de configuration définis dans POSTGRES_CONFIG.
        
        Raises:
            Exception: Si l'initialisation du pool échoue
            
        Returns:
            None
        """
        try:
            config = get_postgres_config()
            # Vérifier que les variables obligatoires sont définies
            if not config['database'] or not config['user']:
                raise ValueError(
                    "Variables PostgreSQL manquantes: PG_DB et PG_USER doivent être définis dans le fichier .env"
                )
            self._pool = await asyncpg.create_pool(**config, min_size=2, max_size=10)
            # Stocker la boucle d'événements actuelle
            try:
                self._pool_loop = asyncio.get_running_loop()
            except RuntimeError:
                self._pool_loop = None
            logger.info("✅ Pool de connexions PostgreSQL initialisé")
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'initialisation du pool PostgreSQL: {e}")
            raise
    
    async def close(self):
        """
        Ferme le pool de connexions PostgreSQL.
        
        Returns:
            None
        """
        if self._pool:
            await self._pool.close()
            logger.info("🔒 Pool de connexions PostgreSQL fermé")
    
    @asynccontextmanager
    async def get_connection(self):
        """
        Contexte manager pour obtenir une connexion de manière sécurisée.
        
        Ce contexte manager gère automatiquement l'acquisition et la libération
        des connexions du pool, ainsi que la gestion des erreurs.
        
        Yields:
            asyncpg.Connection: Connexion à la base de données
            
        Raises:
            Exception: En cas d'erreur de connexion ou de requête
        """
        # Vérifier si le pool existe et est dans la bonne boucle d'événements
        try:
            current_loop = asyncio.get_running_loop()
            
            # Si le pool n'existe pas ou est dans une autre boucle, le recréer
            if not self._pool or (self._pool_loop and self._pool_loop != current_loop):
                async with self._lock:
                    # Double vérification après avoir acquis le lock
                    if not self._pool or (self._pool_loop and self._pool_loop != current_loop):
                        if self._pool:
                            try:
                                await self._pool.close()
                            except Exception:
                                pass
                            self._pool = None
                            self._pool_loop = None
                        await self.initialize()
        except RuntimeError:
            # Pas de boucle d'événements en cours, initialiser normalement
            if not self._pool:
                await self.initialize()
        
        # À ce point, self._pool ne peut pas être None
        assert self._pool is not None
        
        conn = None
        try:
            conn = await self._pool.acquire()
            yield conn
        except Exception as e:
            logger.error(f"Erreur de base de données: {e}")
            # Note: asyncpg gère automatiquement les rollbacks en cas d'erreur
            raise
        finally:
            if conn and self._pool:
                try:
                    await self._pool.release(conn)
                except Exception as e:
                    logger.error(f"Erreur lors de la libération de la connexion: {e}")
    
    async def execute_query(self, query: str, *args) -> Optional[List[Dict[str, Any]]]:
        """
        Exécute une requête SELECT et retourne les résultats.
        
        Args:
            query (str): Requête SQL à exécuter
            *args: Paramètres de la requête
            
        Returns:
            Optional[List[Dict[str, Any]]]: Résultats de la requête ou None si aucun résultat
            
        Raises:
            Exception: En cas d'erreur lors de l'exécution de la requête
        """
        async with self.get_connection() as conn:
            try:
                rows = await conn.fetch(query, *args)
                return [dict(row) for row in rows] if rows else None
            except Exception as e:
                logger.error(f"Erreur lors de l'exécution de la requête: {e}")
                raise
    
    async def execute_update(self, query: str, *args) -> int:
        """
        Exécute une requête INSERT/UPDATE/DELETE et retourne le nombre de lignes affectées.
        
        Args:
            query (str): Requête SQL à exécuter
            *args: Paramètres de la requête
            
        Returns:
            int: Nombre de lignes affectées par la requête
            
        Raises:
            Exception: En cas d'erreur lors de l'exécution de la requête
        """
        async with self.get_connection() as conn:
            try:
                result = await conn.execute(query, *args)
                # Extraire le nombre de lignes affectées du résultat
                if 'UPDATE' in query.upper():
                    return int(result.split()[-1])
                elif 'INSERT' in query.upper():
                    return 1
                elif 'DELETE' in query.upper():
                    return int(result.split()[-1])
                return 0
            except Exception as e:
                logger.error(f"Erreur lors de l'exécution de la mise à jour: {e}")
                raise
    
    async def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """
        Exécute plusieurs requêtes en batch.
        
        Args:
            query (str): Requête SQL à exécuter
            params_list (List[tuple]): Liste des paramètres pour chaque requête
            
        Returns:
            int: Nombre de requêtes exécutées
            
        Raises:
            Exception: En cas d'erreur lors de l'exécution des requêtes
        """
        async with self.get_connection() as conn:
            try:
                await conn.executemany(query, params_list)
                return len(params_list)
            except Exception as e:
                logger.error(f"Erreur lors de l'exécution batch: {e}")
                raise

class VoiceDataManager:
    """
    Gestionnaire spécifique pour les données vocales des utilisateurs.
    
    Cette classe gère toutes les opérations liées aux données vocales
    des utilisateurs (temps passé en vocal, statistiques, etc.).
    """
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialise le gestionnaire de données vocales.
        
        Args:
            db_manager (DatabaseManager): Instance du gestionnaire de base de données
        """
        self.db = db_manager
    
    async def get_user_voice_data(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Récupère les données vocales d'un utilisateur.
        
        Args:
            user_id (int): ID de l'utilisateur Discord
            
        Returns:
            Optional[Dict[str, Any]]: Données vocales de l'utilisateur ou None si non trouvé
        """
        query = "SELECT * FROM user_voice_data WHERE user_id = $1"
        results = await self.db.execute_query(query, user_id)
        return results[0] if results else None
    
    async def update_user_voice_time(self, user_id: int, username: str, time_spent: int) -> bool:
        """
        Met à jour le temps vocal d'un utilisateur.
        
        Args:
            user_id (int): ID de l'utilisateur Discord
            username (str): Nom d'utilisateur Discord
            time_spent (int): Temps passé en vocal (en secondes)
            
        Returns:
            bool: True si la mise à jour a réussi, False sinon
        """
        try:
            # Vérifier si l'utilisateur existe
            existing_user = await self.get_user_voice_data(user_id)
            
            if existing_user:
                # Mettre à jour le temps existant
                query = """
                    UPDATE user_voice_data 
                    SET total_time = total_time + $1, username = $2, updated_at = CURRENT_TIMESTAMP 
                    WHERE user_id = $3
                """
                await self.db.execute_update(query, time_spent, username, user_id)
            else:
                # Créer un nouvel utilisateur
                query = """
                    INSERT INTO user_voice_data (user_id, username, total_time) 
                    VALUES ($1, $2, $3)
                """
                await self.db.execute_update(query, user_id, username, time_spent)
            
            logger.info(f"Temps vocal mis à jour pour l'utilisateur {user_id}: +{time_spent}s")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du temps vocal: {e}")
            return False
    
    async def get_top_voice_users(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Récupère les utilisateurs avec le plus de temps vocal.
        
        Args:
            limit (int): Nombre maximum d'utilisateurs à retourner
        
        Returns:
            List[Dict[str, Any]]: Liste des utilisateurs triés par temps vocal
        """
        query = "SELECT * FROM user_voice_data ORDER BY total_time DESC LIMIT $1"
        return await self.db.execute_query(query, limit) or []
    
    async def sync_member(self, user_id: int, username: str, nickname: str = None):
        """
        Synchronise un membre Discord dans user_voice_data.
        
        Args:
            user_id (int): ID Discord de l'utilisateur
            username (str): Nom d'utilisateur Discord
            nickname (str, optional): Pseudo sur le serveur (nickname)
        
        Returns:
            bool: True si la synchronisation a réussi
        """
        try:
            # Vérifier si l'utilisateur existe
            existing_user = await self.get_user_voice_data(user_id)
            
            if existing_user:
                # Mettre à jour
                query = """
                    UPDATE user_voice_data 
                    SET username = $1, nickname = $2, updated_at = CURRENT_TIMESTAMP 
                    WHERE user_id = $3
                """
                await self.db.execute_update(query, username, nickname, user_id)
            else:
                # Créer un nouvel utilisateur
                query = """
                    INSERT INTO user_voice_data (user_id, username, nickname) 
                    VALUES ($1, $2, $3)
                """
                await self.db.execute_update(query, user_id, username, nickname)
            
            logger.debug(f"Membre synchronisé: {username} ({user_id}) - nickname: {nickname}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la synchronisation du membre {user_id}: {e}")
            return False
    
    async def find_user_by_username_or_nickname(self, search_term: str) -> Optional[Dict[str, Any]]:
        """
        Recherche un utilisateur par username ou nickname dans la base de données.
        
        Args:
            search_term (str): Pseudo ou username à rechercher
        
        Returns:
            Optional[Dict[str, Any]]: Données de l'utilisateur trouvé ou None
        """
        try:
            search_term_lower = search_term.strip().lower()
            query = """
                SELECT * FROM user_voice_data 
                WHERE LOWER(username) = $1 
                   OR LOWER(nickname) = $1
                   OR LOWER(username) LIKE $2
                   OR LOWER(nickname) LIKE $2
                ORDER BY 
                    CASE 
                        WHEN LOWER(username) = $1 THEN 1
                        WHEN LOWER(nickname) = $1 THEN 2
                        WHEN LOWER(username) LIKE $2 THEN 3
                        WHEN LOWER(nickname) LIKE $2 THEN 4
                    END
                LIMIT 1
            """
            results = await self.db.execute_query(query, search_term_lower, f"{search_term_lower}%")
            return results[0] if results else None
        except Exception as e:
            logger.error(f"Erreur lors de la recherche d'utilisateur: {e}")
            return None

class WarnManager:
    """
    Gestionnaire pour les avertissements des utilisateurs.
    
    Cette classe gère toutes les opérations liées aux avertissements
    (ajout, récupération, comptage, etc.).
    """
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialise le gestionnaire d'avertissements.
        
        Args:
            db_manager (DatabaseManager): Instance du gestionnaire de base de données
        """
        self.db = db_manager
    
    async def add_warn(self, user_id: int, reason: str, moderator_id: int) -> bool:
        """
        Ajoute un avertissement à un utilisateur.
        
        Args:
            user_id (int): ID de l'utilisateur à avertir
            reason (str): Raison de l'avertissement
            moderator_id (int): ID du modérateur qui donne l'avertissement
            
        Returns:
            bool: True si l'avertissement a été ajouté avec succès, False sinon
        """
        try:
            # S'assurer que l'utilisateur existe dans user_voice_data
            await self.db.execute_update(
                "INSERT INTO user_voice_data (user_id, username) VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING",
                user_id, f"User_{user_id}"
            )
            
            # Ajouter l'avertissement
            query = "INSERT INTO warn (user_id, reason, create_time, moderator_id) VALUES ($1, $2, $3, $4)"
            await self.db.execute_update(query, user_id, reason, int(datetime.now(timezone.utc).timestamp()), moderator_id)
            
            logger.info(f"Avertissement ajouté pour l'utilisateur {user_id}: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout de l'avertissement: {e}")
            return False
    
    async def get_user_warns(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Récupère tous les avertissements d'un utilisateur.
        
        Args:
            user_id (int): ID de l'utilisateur
            
        Returns:
            List[Dict[str, Any]]: Liste des avertissements de l'utilisateur
        """
        query = """
        SELECT w.*, u.username 
        FROM warn w 
        JOIN user_voice_data u ON w.user_id = u.user_id 
        WHERE w.user_id = $1 
        ORDER BY w.create_time DESC
        """
        return await self.db.execute_query(query, user_id) or []
    
    async def get_warn_count(self, user_id: int) -> int:
        """
        Compte le nombre d'avertissements d'un utilisateur.
        
        Args:
            user_id (int): ID de l'utilisateur
            
        Returns:
            int: Nombre d'avertissements de l'utilisateur
        """
        query = "SELECT COUNT(*) as count FROM warn WHERE user_id = $1"
        result = await self.db.execute_query(query, user_id)
        return result[0]['count'] if result else 0

class UserMessageStatsManager:
    """
    Gestionnaire pour les statistiques des messages utilisateur/salon.
    
    Cette classe gère les statistiques des messages envoyés par les utilisateurs
    dans différents canaux du serveur Discord.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialise le gestionnaire de statistiques de messages.
        
        Args:
            db_manager (DatabaseManager): Instance du gestionnaire de base de données
        """
        self.db = db_manager
    
    async def increment_message_count(self, user_id: int, channel_id: int):
        """
        Incrémente le compteur de messages pour un utilisateur dans un canal.
        
        Args:
            user_id (int): ID de l'utilisateur
            channel_id (int): ID du canal
            
        Returns:
            None
        """
        try:
            # D'abord, s'assurer que l'utilisateur existe dans user_voice_data
            # Si ce n'est pas le cas, le créer avec un nom d'utilisateur temporaire
            async with self.db.get_connection() as conn:
                # Vérifier si l'utilisateur existe
                user_exists = await conn.fetchval(
                    "SELECT 1 FROM user_voice_data WHERE user_id = $1", 
                    user_id
                )
                
                if not user_exists:
                    # Créer l'utilisateur avec un nom temporaire
                    await conn.execute(
                        "INSERT INTO user_voice_data (user_id, username) VALUES ($1, $2)",
                        user_id, f"User_{user_id}"
                    )
                    logger.info(f"Utilisateur {user_id} créé automatiquement dans user_voice_data")
                
                # Maintenant incrémenter le compteur de messages
                await conn.execute("""
                    INSERT INTO user_message_stats (user_id, channel_id, message_count) 
                    VALUES ($1, $2, 1) 
                    ON CONFLICT (user_id, channel_id) 
                    DO UPDATE SET message_count = user_message_stats.message_count + 1
                """, user_id, channel_id)
                
        except Exception as e:
            logger.error(f"Erreur lors de l'incrémentation du compteur de messages: {e}")
            raise
    
    async def get_total_messages(self, user_id: int) -> int:
        """
        Récupère le nombre total de messages d'un utilisateur.
        
        Args:
            user_id (int): ID de l'utilisateur
            
        Returns:
            int: Nombre total de messages de l'utilisateur
        """
        query = "SELECT SUM(message_count) as total FROM user_message_stats WHERE user_id = $1"
        result = await self.db.execute_query(query, user_id)
        return result[0]['total'] if result and result[0]['total'] else 0
    
    async def get_top_channels(self, user_id: int, limit: int = 3):
        """
        Récupère les canaux où un utilisateur a le plus posté.
        
        Args:
            user_id (int): ID de l'utilisateur
            limit (int): Nombre maximum de canaux à retourner
            
        Returns:
            List[Dict[str, Any]]: Liste des canaux triés par nombre de messages
        """
        query = """
        SELECT channel_id, message_count 
        FROM user_message_stats 
        WHERE user_id = $1 
        ORDER BY message_count DESC 
        LIMIT $2
        """
        return await self.db.execute_query(query, user_id, limit) or []
    
    async def get_leaderboard(self, limit: int = 10):
        """
        Récupère le classement des utilisateurs par nombre de messages.
        
        Args:
            limit (int): Nombre maximum d'utilisateurs à retourner
            
        Returns:
            List[Dict[str, Any]]: Classement des utilisateurs par nombre de messages
        """
        query = """
        SELECT u.user_id, u.username, SUM(ums.message_count) as total_messages
        FROM user_voice_data u
        JOIN user_message_stats ums ON u.user_id = ums.user_id
        GROUP BY u.user_id, u.username
        ORDER BY total_messages DESC
        LIMIT $1
        """
        return await self.db.execute_query(query, limit) or []
    
    async def update_username(self, user_id: int, username: str):
        """
        Met à jour le nom d'utilisateur dans user_voice_data.
        
        Args:
            user_id (int): ID de l'utilisateur
            username (str): Nouveau nom d'utilisateur
        
        Returns:
            None
        """
        try:
            query = "UPDATE user_voice_data SET username = $1 WHERE user_id = $2"
            await self.db.execute_update(query, username, user_id)
            logger.info(f"Nom d'utilisateur mis à jour pour {user_id}: {username}")
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du nom d'utilisateur: {e}")
            raise

# Instances globales
db_manager = DatabaseManager()
voice_manager = VoiceDataManager(db_manager)
warn_manager = WarnManager(db_manager)
user_message_stats_manager = UserMessageStatsManager(db_manager)

async def setup_database():
    """
    Configure et initialise la base de données PostgreSQL.
    
    Cette fonction crée toutes les tables nécessaires au fonctionnement
    du bot si elles n'existent pas déjà.
    
    Returns:
        None
    """
    try:
        await db_manager.initialize()
        
        async with db_manager.get_connection() as conn:
            # Créer la table user_voice_data
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_voice_data (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255) NOT NULL,
                    nickname VARCHAR(255),
                    total_time INTEGER DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Ajouter la colonne nickname si elle n'existe pas (migration)
            try:
                await conn.execute("""
                    ALTER TABLE user_voice_data 
                    ADD COLUMN IF NOT EXISTS nickname VARCHAR(255)
                """)
            except Exception as e:
                # La colonne existe peut-être déjà, ignorer l'erreur
                logger.debug(f"Colonne nickname: {e}")
            
            # Créer un index pour la recherche rapide par username et nickname
            try:
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_user_voice_username 
                    ON user_voice_data(username)
                """)
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_user_voice_nickname 
                    ON user_voice_data(nickname)
                """)
            except Exception as e:
                logger.debug(f"Index déjà existants: {e}")
            
            # Créer la table warn
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS warn (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    reason TEXT NOT NULL,
                    create_time BIGINT NOT NULL,
                    moderator_id BIGINT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES user_voice_data(user_id)
                )
            """)
            
            # Créer la table user_message_stats
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_message_stats (
                    user_id BIGINT NOT NULL,
                    channel_id BIGINT NOT NULL,
                    message_count INTEGER DEFAULT 1,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, channel_id),
                    FOREIGN KEY (user_id) REFERENCES user_voice_data(user_id)
                )
            """)
            
        logger.info("✅ Base de données configurée avec succès")
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la configuration de la base de données: {e}")
        raise

async def init_database():
    """
    Initialise la base de données et les managers.
    
    Cette fonction configure la base de données et initialise
    tous les managers nécessaires au fonctionnement du bot.
    
    Returns:
        None
    """
    await setup_database()
    logger.info("🚀 Gestionnaire de base de données PostgreSQL prêt") 

async def get_channel_message_stats(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Récupère les statistiques des canaux les plus actifs.
    
    Args:
        limit (int): Nombre maximum de canaux à retourner
        
    Returns:
        List[Dict[str, Any]]: Liste des canaux avec leurs statistiques
    """
    try:
        db_manager = DatabaseManager()
        await db_manager.initialize()
        
        query = """
            SELECT channel_id, message_count
            FROM channel_message_stats
            ORDER BY message_count DESC
            LIMIT $1
        """
        
        results = await db_manager.execute_query(query, limit)
        await db_manager.close()
        
        return results if results else []
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération des stats des canaux: {e}")
        return [] 