"""
Module API Web pour Hermes Bot

Ce module fournit une API REST pour permettre au site web SaucisseLand
d'utiliser les commandes du bot Discord via des requêtes HTTP.

Fonctionnalités:
- Endpoint /warn pour donner un avertissement à un utilisateur
- Authentification par token API
- Intégration avec le bot Discord pour envoyer des notifications

Auteur: Dr.TableBasse
Version: 1.0
"""

import os
import time
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import discord
from dotenv import load_dotenv

from utils.database import warn_manager

# Charger les variables d'environnement
load_dotenv()

logger = logging.getLogger(__name__)

# Configuration
API_TOKEN = os.getenv('API_TOKEN')
API_PORT = int(os.getenv('API_PORT', '8001'))
GUILD_ID = int(os.getenv('GUILD_ID', '0'))
ADMIN_LOG_CHANNEL_ID = os.getenv('ADMIN_LOG_CHANNEL_ID')
# Rôles autorisés (même que pour les articles sur le site web)
ALLOWED_ROLE_IDS_STR = os.getenv('ALLOWED_ROLE_IDS', '')
ALLOWED_ROLE_IDS = [
    role_id.strip() 
    for role_id in ALLOWED_ROLE_IDS_STR.split(',') 
    if role_id.strip()
] if ALLOWED_ROLE_IDS_STR else []

# Modèle de données pour les requêtes
class WarnRequest(BaseModel):
    user_id: int
    reason: str = "Aucune raison spécifiée"
    moderator_id: int
    moderator_name: Optional[str] = None

class WarnResponse(BaseModel):
    success: bool
    message: str
    warn_count: Optional[int] = None

# Instance FastAPI
app = FastAPI(
    title="Hermes Bot API",
    description="API REST pour contrôler le bot Discord Hermes",
    version="1.0.0"
)

# Configuration CORS pour permettre les requêtes depuis le site web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production, spécifier les origines autorisées
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Variable globale pour stocker l'instance du bot
bot_instance: Optional[discord.Client] = None

def set_bot_instance(bot: discord.Client):
    """Définit l'instance du bot Discord pour l'API"""
    global bot_instance
    bot_instance = bot

def verify_api_token(authorization: str = Header(None)) -> bool:
    """Vérifie le token API dans les en-têtes"""
    if not API_TOKEN:
        logger.warning("API_TOKEN non configuré dans les variables d'environnement")
        raise HTTPException(
            status_code=500,
            detail="API non configurée correctement"
        )
    
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Token d'authentification manquant"
        )
    
    # Format attendu: "Bearer <token>"
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=401,
                detail="Format d'authentification invalide. Utilisez 'Bearer <token>'"
            )
        if token != API_TOKEN:
            raise HTTPException(
                status_code=401,
                detail="Token d'authentification invalide"
            )
        return True
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Format d'authentification invalide. Utilisez 'Bearer <token>'"
        )

@app.get("/")
async def root():
    """Endpoint de santé de l'API"""
    return {
        "status": "online",
        "service": "Hermes Bot API",
        "version": "1.0.0"
    }

@app.get("/health")
async def health():
    """Vérification de l'état de l'API et du bot"""
    bot_status = "connected" if bot_instance and bot_instance.is_ready() else "disconnected"
    return {
        "api": "online",
        "bot": bot_status,
        "guild_id": GUILD_ID
    }

@app.post("/warn", response_model=WarnResponse)
async def warn_user(
    request: WarnRequest,
    _: bool = Depends(verify_api_token)
):
    """
    Donne un avertissement à un utilisateur Discord
    
    Args:
        request: Données de la requête (user_id, reason, moderator_id)
        _: Vérification du token API (via dependency)
    
    Returns:
        WarnResponse: Résultat de l'opération
    """
    if not bot_instance:
        raise HTTPException(
            status_code=503,
            detail="Bot Discord non disponible"
        )
    
    if not bot_instance.is_ready():
        raise HTTPException(
            status_code=503,
            detail="Bot Discord non connecté"
        )
    
    try:
        # Récupérer le serveur Discord
        guild = bot_instance.get_guild(GUILD_ID)
        if not guild:
            raise HTTPException(
                status_code=404,
                detail=f"Serveur Discord (Guild ID: {GUILD_ID}) non trouvé"
            )
        
        # Récupérer l'utilisateur à avertir
        user = guild.get_member(request.user_id)
        if not user:
            # Essayer de fetch l'utilisateur si pas dans le cache
            try:
                user = await bot_instance.fetch_user(request.user_id)
            except discord.NotFound:
                raise HTTPException(
                    status_code=404,
                    detail=f"Utilisateur Discord (ID: {request.user_id}) non trouvé"
                )
            except Exception as e:
                logger.error(f"Erreur lors de la récupération de l'utilisateur: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Erreur lors de la récupération de l'utilisateur: {str(e)}"
                )
        
        # Récupérer le modérateur et vérifier ses permissions
        moderator = guild.get_member(request.moderator_id)
        if not moderator:
            raise HTTPException(
                status_code=404,
                detail=f"Modérateur Discord (ID: {request.moderator_id}) non trouvé sur le serveur"
            )
        
        moderator_name = request.moderator_name or moderator.display_name
        
        # Vérifier que le modérateur a un des rôles autorisés
        if ALLOWED_ROLE_IDS:
            moderator_roles = [str(role.id) for role in moderator.roles]
            has_permission = any(str(role_id).strip() in moderator_roles for role_id in ALLOWED_ROLE_IDS)
            
            if not has_permission:
                logger.warning(
                    f"Tentative d'avertissement par {moderator.display_name} (ID: {request.moderator_id}) "
                    f"sans les permissions nécessaires. Rôles: {moderator_roles}, Rôles autorisés: {ALLOWED_ROLE_IDS}"
                )
                raise HTTPException(
                    status_code=403,
                    detail="Vous n'avez pas les permissions nécessaires pour donner un avertissement. "
                           "Vous devez avoir un des rôles Discord autorisés."
                )
        else:
            logger.warning("ALLOWED_ROLE_IDS non configuré - aucune vérification de rôle effectuée")
        
        # Ajouter l'avertissement en base de données
        success = await warn_manager.add_warn(
            user_id=request.user_id,
            reason=request.reason,
            moderator_id=request.moderator_id
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Erreur lors de l'ajout de l'avertissement en base de données"
            )
        
        # Récupérer le nombre total d'avertissements
        warn_count = await warn_manager.get_warn_count(request.user_id)
        
        # Envoyer une notification dans le canal de logs admin (si configuré)
        if ADMIN_LOG_CHANNEL_ID:
            try:
                log_channel_id = int(ADMIN_LOG_CHANNEL_ID)
                log_channel = guild.get_channel(log_channel_id)
                
                if log_channel:
                    embed = discord.Embed(
                        title="⚠️ Avertissement (via API)",
                        description=f"{user.mention if isinstance(user, discord.Member) else f'<@{request.user_id}>'} a été averti",
                        color=discord.Color.orange()
                    )
                    embed.add_field(name="Raison", value=request.reason, inline=False)
                    embed.add_field(name="Modérateur", value=moderator_name, inline=True)
                    embed.add_field(name="Date", value=f"<t:{int(time.time())}:F>", inline=True)
                    embed.add_field(name="Total d'avertissements", value=str(warn_count), inline=True)
                    
                    await log_channel.send(embed=embed)
            except Exception as e:
                logger.warning(f"Impossible d'envoyer le log dans le canal admin: {e}")
        
        # Envoyer une notification privée à l'utilisateur (si c'est un membre du serveur)
        if isinstance(user, discord.Member):
            try:
                user_embed = discord.Embed(
                    title="⚠️ Avertissement reçu",
                    description=f"Vous avez été averti sur le serveur **{guild.name}**",
                    color=discord.Color.orange()
                )
                user_embed.add_field(name="Raison", value=request.reason, inline=False)
                user_embed.add_field(name="Modérateur", value=moderator_name, inline=True)
                user_embed.add_field(name="Date", value=f"<t:{int(time.time())}:F>", inline=True)
                
                await user.send(embed=user_embed)
            except discord.Forbidden:
                logger.warning(f"Impossible d'envoyer un message privé à {user.display_name} (DMs fermés)")
            except Exception as e:
                logger.warning(f"Erreur lors de l'envoi du DM à {user.display_name}: {e}")
        
        logger.info(f'Avertissement ajouté via API par {moderator_name} pour {user.display_name if isinstance(user, discord.Member) else f"User_{request.user_id}"}: {request.reason}')
        
        return WarnResponse(
            success=True,
            message=f"Avertissement ajouté avec succès pour {user.display_name if isinstance(user, discord.Member) else f'User_{request.user_id}'}",
            warn_count=warn_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Erreur dans l\'endpoint /warn: {e}', exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne: {str(e)}"
        )

def run_api(host: str = "0.0.0.0", port: int = None):
    """Démarre le serveur API"""
    import uvicorn
    port = port or API_PORT
    logger.info(f"🚀 Démarrage de l'API Hermes sur {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")

