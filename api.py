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
import asyncio
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Header, Depends, Request, Body, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import discord
from dotenv import load_dotenv
from collections import defaultdict
from datetime import datetime

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

class WarnInfo(BaseModel):
    id: int
    user_id: int
    reason: str
    create_time: int
    moderator_id: int
    username: Optional[str] = None

class WarnsResponse(BaseModel):
    user_id: int
    warn_count: int
    warns: List[WarnInfo]

class DeleteWarnRequest(BaseModel):
    moderator_id: int
    moderator_name: Optional[str] = None

class DeleteWarnResponse(BaseModel):
    success: bool
    message: str
    warn_count: Optional[int] = None

class UpdateWarnReasonRequest(BaseModel):
    reason: str
    moderator_id: int
    moderator_name: Optional[str] = None

class UpdateWarnReasonResponse(BaseModel):
    success: bool
    message: str
    warn: Optional[WarnInfo] = None

class BulkDeleteWarnsRequest(BaseModel):
    warn_ids: List[int]
    moderator_id: int
    moderator_name: Optional[str] = None

class BulkDeleteWarnsResponse(BaseModel):
    success: bool
    message: str
    deleted_count: int
    warn_count: Optional[int] = None

# Modèles pour les actions de modération
class ModerationActionRequest(BaseModel):
    user_id: int
    reason: str = "Aucune raison spécifiée"
    moderator_id: int
    moderator_name: Optional[str] = None

class ModerationActionResponse(BaseModel):
    success: bool
    message: str

class TempModerationActionRequest(BaseModel):
    user_id: int
    duration: int
    unit: str  # "secondes", "minutes", "heures", "jours", "mois", "années"
    reason: str = "Aucune raison spécifiée"
    moderator_id: int
    moderator_name: Optional[str] = None

class TempModerationActionResponse(BaseModel):
    success: bool
    message: str
    unban_time: Optional[int] = None  # Timestamp Unix pour le débannissement automatique

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

# Middleware pour tracker les métriques Prometheus
@app.middleware("http")
async def track_metrics(request: Request, call_next):
    """Middleware pour tracker les métriques HTTP"""
    start_time = time.time()
    endpoint = f"{request.method} {request.url.path}"
    
    try:
        response = await call_next(request)
        
        # Enregistrer la requête
        _metrics['http_requests_total'][endpoint] += 1
        
        # Enregistrer la durée
        duration = time.time() - start_time
        _metrics['http_request_duration_seconds'].append(duration)
        
        # Garder seulement les 1000 dernières durées pour éviter la consommation mémoire
        if len(_metrics['http_request_duration_seconds']) > 1000:
            _metrics['http_request_duration_seconds'] = _metrics['http_request_duration_seconds'][-1000:]
        
        # Enregistrer les erreurs (4xx et 5xx)
        if response.status_code >= 400:
            _metrics['http_errors_total'][f"{endpoint} {response.status_code}"] += 1
        
        return response
    except Exception as e:
        # Enregistrer l'erreur
        _metrics['http_errors_total'][f"{endpoint} exception"] += 1
        raise

# Variable globale pour stocker l'instance du bot
bot_instance: Optional[discord.Client] = None

# Métriques Prometheus
_metrics = {
    'http_requests_total': defaultdict(int),
    'http_request_duration_seconds': [],
    'http_errors_total': defaultdict(int),
    'api_warns_total': 0,
    'api_kicks_total': 0,
    'api_bans_total': 0,
    'api_mutes_total': 0,
    'bot_status': 0,  # 0 = offline, 1 = online
    'start_time': time.time()
}

def set_bot_instance(bot: discord.Client):
    """Définit l'instance du bot Discord pour l'API"""
    global bot_instance
    bot_instance = bot
    _metrics['bot_status'] = 1

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

@app.get("/metrics")
async def metrics():
    """
    Endpoint Prometheus pour exposer les métriques de l'API
    Format compatible avec Prometheus
    """
    try:
        # Calculer le temps de fonctionnement
        uptime_seconds = time.time() - _metrics['start_time']
        
        # Calculer la durée moyenne des requêtes
        avg_duration = 0
        if _metrics['http_request_duration_seconds']:
            avg_duration = sum(_metrics['http_request_duration_seconds']) / len(_metrics['http_request_duration_seconds'])
        
        # Compter les requêtes totales
        total_requests = sum(_metrics['http_requests_total'].values())
        total_errors = sum(_metrics['http_errors_total'].values())
        
        # Obtenir le nombre de warns depuis la base de données
        try:
            warns_count = await warn_manager.get_total_warns()
        except:
            warns_count = 0
        
        # Format Prometheus
        metrics_output = []
        
        # Métriques générales
        metrics_output.append(f"# HELP hermes_api_uptime_seconds Temps de fonctionnement de l'API en secondes")
        metrics_output.append(f"# TYPE hermes_api_uptime_seconds gauge")
        metrics_output.append(f"hermes_api_uptime_seconds {uptime_seconds}")
        
        metrics_output.append(f"# HELP hermes_api_http_requests_total Nombre total de requêtes HTTP")
        metrics_output.append(f"# TYPE hermes_api_http_requests_total counter")
        for endpoint, count in _metrics['http_requests_total'].items():
            metrics_output.append(f'hermes_api_http_requests_total{{endpoint="{endpoint}"}} {count}')
        
        metrics_output.append(f"# HELP hermes_api_http_errors_total Nombre total d'erreurs HTTP")
        metrics_output.append(f"# TYPE hermes_api_http_errors_total counter")
        for endpoint, count in _metrics['http_errors_total'].items():
            metrics_output.append(f'hermes_api_http_errors_total{{endpoint="{endpoint}"}} {count}')
        
        metrics_output.append(f"# HELP hermes_api_http_request_duration_seconds Durée moyenne des requêtes HTTP")
        metrics_output.append(f"# TYPE hermes_api_http_request_duration_seconds gauge")
        metrics_output.append(f"hermes_api_http_request_duration_seconds {avg_duration:.4f}")
        
        metrics_output.append(f"# HELP hermes_api_warns_total Nombre total d'avertissements")
        metrics_output.append(f"# TYPE hermes_api_warns_total counter")
        metrics_output.append(f"hermes_api_warns_total {warns_count}")
        
        metrics_output.append(f"# HELP hermes_api_actions_total Nombre total d'actions de modération")
        metrics_output.append(f"# TYPE hermes_api_actions_total counter")
        metrics_output.append(f'hermes_api_actions_total{{action="warn"}} {_metrics["api_warns_total"]}')
        metrics_output.append(f'hermes_api_actions_total{{action="kick"}} {_metrics["api_kicks_total"]}')
        metrics_output.append(f'hermes_api_actions_total{{action="ban"}} {_metrics["api_bans_total"]}')
        metrics_output.append(f'hermes_api_actions_total{{action="mute"}} {_metrics["api_mutes_total"]}')
        
        metrics_output.append(f"# HELP hermes_bot_status Statut du bot Discord (0=offline, 1=online)")
        metrics_output.append(f"# TYPE hermes_bot_status gauge")
        metrics_output.append(f"hermes_bot_status {_metrics['bot_status']}")
        
        return Response(
            content="\n".join(metrics_output) + "\n",
            media_type="text/plain; version=0.0.4; charset=utf-8"
        )
    except Exception as e:
        logger.error(f"Erreur lors de la génération des métriques: {e}")
        return Response(
            content=f"# Erreur: {str(e)}\n",
            media_type="text/plain",
            status_code=500
        )

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
        # Note: On utilise uniquement get_member() car fetch_member() cause des erreurs de timeout
        # Si l'utilisateur n'est pas dans le cache, on peut quand même créer l'avertissement
        # mais on ne pourra pas envoyer de message privé
        user = guild.get_member(request.user_id)
        user_display_name = None
        if user:
            user_display_name = user.display_name
        else:
            # L'utilisateur n'est pas dans le cache, mais on peut quand même créer l'avertissement
            # On utilisera l'ID comme nom d'affichage
            logger.warning(f"Utilisateur {request.user_id} non trouvé dans le cache du serveur. L'avertissement sera créé mais aucune notification ne sera envoyée.")
            user_display_name = f"User_{request.user_id}"
        
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
        
        # Logs de débogage avant l'ajout
        logger.info(f"🔍 DEBUG warn_user: user_id reçu={request.user_id} (type: {type(request.user_id)})")
        logger.info(f"🔍 DEBUG warn_user: reason={request.reason}")
        logger.info(f"🔍 DEBUG warn_user: moderator_id={request.moderator_id}")
        
        # Ajouter l'avertissement en base de données
        success = await warn_manager.add_warn(
            user_id=request.user_id,
            reason=request.reason,
            moderator_id=request.moderator_id
        )
        
        logger.info(f"🔍 DEBUG warn_user: add_warn retourné success={success}")
        
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
                    user_mention = user.mention if user else f"<@{request.user_id}>"
                    embed = discord.Embed(
                        title="⚠️ Avertissement donné (via API)",
                        description=f"{user_mention} a été averti",
                        color=discord.Color.orange()
                    )
                    embed.add_field(name="Raison", value=request.reason, inline=False)
                    embed.add_field(name="Modérateur", value=moderator_name, inline=True)
                    embed.add_field(name="Date", value=f"<t:{int(time.time())}:F>", inline=True)
                    embed.add_field(name="Total d'avertissements", value=str(warn_count), inline=True)
                    
                    await log_channel.send(embed=embed)
            except Exception as e:
                logger.warning(f"Impossible d'envoyer le log dans le canal admin: {e}")
        
        # Envoyer une notification privée à l'utilisateur (seulement si on a trouvé l'utilisateur)
        if user:
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
        else:
            logger.info(f"Utilisateur {request.user_id} n'est pas sur le serveur ou n'est pas dans le cache, aucune notification privée envoyée")
        
        logger.info(f'Avertissement ajouté via API par {moderator_name} pour {user_display_name}: {request.reason}')
        
        # Incrémenter le compteur de métriques
        _metrics['api_warns_total'] += 1
        
        return WarnResponse(
            success=True,
            message=f"Avertissement ajouté avec succès pour {user_display_name}",
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

@app.get("/warns/{user_id}", response_model=WarnsResponse)
async def get_user_warns(
    user_id: int,
    _: bool = Depends(verify_api_token)
):
    """
    Récupère tous les avertissements d'un utilisateur Discord
    
    Args:
        user_id: ID Discord de l'utilisateur
        _: Vérification du token API (via dependency)
    
    Returns:
        WarnsResponse: Liste des avertissements de l'utilisateur
    """
    try:
        logger.info(f"Récupération des warns pour l'utilisateur {user_id} (type: {type(user_id)})")
        
        # Récupérer les avertissements depuis la base de données
        warns = await warn_manager.get_user_warns(user_id)
        warn_count = await warn_manager.get_warn_count(user_id)
        
        logger.info(f"Warns trouvés: {len(warns)} warns, count: {warn_count}")
        if warns:
            logger.info(f"Détails du premier warn: {warns[0]}")
        else:
            logger.warning(f"Aucun warn trouvé pour user_id={user_id}, mais count={warn_count}")
        
        # Convertir les warns en modèles Pydantic
        warn_list = []
        for warn in warns:
            warn_list.append(WarnInfo(
                id=warn.get('id'),
                user_id=warn.get('user_id'),
                reason=warn.get('reason'),
                create_time=warn.get('create_time'),
                moderator_id=warn.get('moderator_id'),
                username=warn.get('username')
            ))
        
        logger.info(f"Retour de {len(warn_list)} warns pour l'utilisateur {user_id}")
        
        return WarnsResponse(
            user_id=user_id,
            warn_count=warn_count,
            warns=warn_list
        )
        
    except Exception as e:
        logger.error(f'Erreur dans l\'endpoint /warns/{user_id}: {e}', exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne: {str(e)}"
        )

@app.delete("/warns/{warn_id}", response_model=DeleteWarnResponse)
async def delete_warn(
    warn_id: int,
    request: DeleteWarnRequest,
    _: bool = Depends(verify_api_token)
):
    """
    Supprime un avertissement par son ID
    
    Args:
        warn_id: ID de l'avertissement à supprimer
        request: Données de la requête (moderator_id, moderator_name)
        _: Vérification du token API (via dependency)
    
    Returns:
        DeleteWarnResponse: Résultat de l'opération
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
        # Récupérer l'avertissement pour vérifier qu'il existe
        warn = await warn_manager.get_warn_by_id(warn_id)
        if not warn:
            raise HTTPException(
                status_code=404,
                detail=f"Avertissement {warn_id} non trouvé"
            )
        
        user_id = warn.get('user_id')
        
        # Récupérer le serveur Discord
        guild = bot_instance.get_guild(GUILD_ID)
        if not guild:
            raise HTTPException(
                status_code=404,
                detail=f"Serveur Discord (Guild ID: {GUILD_ID}) non trouvé"
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
                    f"Tentative de suppression d'avertissement par {moderator.display_name} (ID: {request.moderator_id}) "
                    f"sans les permissions nécessaires. Rôles: {moderator_roles}, Rôles autorisés: {ALLOWED_ROLE_IDS}"
                )
                raise HTTPException(
                    status_code=403,
                    detail="Vous n'avez pas les permissions nécessaires pour supprimer un avertissement. "
                           "Vous devez avoir un des rôles Discord autorisés."
                )
        
        # Supprimer l'avertissement
        success = await warn_manager.delete_warn(warn_id)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Erreur lors de la suppression de l'avertissement en base de données"
            )
        
        # Récupérer le nouveau nombre total d'avertissements
        warn_count = await warn_manager.get_warn_count(user_id)
        
        # Envoyer une notification dans le canal de logs admin (si configuré)
        if ADMIN_LOG_CHANNEL_ID:
            try:
                log_channel_id = int(ADMIN_LOG_CHANNEL_ID)
                log_channel = guild.get_channel(log_channel_id)
                
                if log_channel:
                    user = guild.get_member(user_id)
                    user_mention = user.mention if user else f"<@{user_id}>"
                    
                    embed = discord.Embed(
                        title="🗑️ Avertissement supprimé (via API)",
                        description=f"Avertissement #{warn_id} supprimé pour {user_mention}",
                        color=discord.Color.red()
                    )
                    embed.add_field(name="Raison originale", value=warn.get('reason', 'N/A'), inline=False)
                    embed.add_field(name="Modérateur", value=moderator_name, inline=True)
                    embed.add_field(name="Date", value=f"<t:{int(time.time())}:F>", inline=True)
                    embed.add_field(name="Total d'avertissements restants", value=str(warn_count), inline=True)
                    
                    await log_channel.send(embed=embed)
            except Exception as e:
                logger.warning(f"Impossible d'envoyer le log dans le canal admin: {e}")
        
        logger.info(f'Avertissement {warn_id} supprimé via API par {moderator_name} pour utilisateur {user_id}')
        
        return DeleteWarnResponse(
            success=True,
            message=f"Avertissement #{warn_id} supprimé avec succès",
            warn_count=warn_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Erreur dans l\'endpoint DELETE /warns/{warn_id}: {e}', exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne: {str(e)}"
        )

@app.put("/warns/{warn_id}", response_model=UpdateWarnReasonResponse)
async def update_warn_reason(
    warn_id: int,
    request: UpdateWarnReasonRequest,
    _: bool = Depends(verify_api_token)
):
    """
    Met à jour la raison d'un avertissement
    
    Args:
        warn_id: ID de l'avertissement à modifier
        request: Données de la requête (reason, moderator_id, moderator_name)
        _: Vérification du token API (via dependency)
    
    Returns:
        UpdateWarnReasonResponse: Résultat de l'opération
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
        # Récupérer l'avertissement pour vérifier qu'il existe
        warn = await warn_manager.get_warn_by_id(warn_id)
        if not warn:
            raise HTTPException(
                status_code=404,
                detail=f"Avertissement {warn_id} non trouvé"
            )
        
        user_id = warn.get('user_id')
        
        # Récupérer le serveur Discord
        guild = bot_instance.get_guild(GUILD_ID)
        if not guild:
            raise HTTPException(
                status_code=404,
                detail=f"Serveur Discord (Guild ID: {GUILD_ID}) non trouvé"
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
                    f"Tentative de modification de warn par {moderator.display_name} (ID: {request.moderator_id}) "
                    f"sans les permissions nécessaires. Rôles: {moderator_roles}, Rôles autorisés: {ALLOWED_ROLE_IDS}"
                )
                raise HTTPException(
                    status_code=403,
                    detail="Vous n'avez pas les permissions nécessaires pour modifier un avertissement. "
                           "Vous devez avoir un des rôles Discord autorisés."
                )
        
        # Mettre à jour la raison
        success = await warn_manager.update_warn_reason(warn_id, request.reason)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Erreur lors de la mise à jour de l'avertissement en base de données"
            )
        
        # Récupérer l'avertissement mis à jour
        updated_warn = await warn_manager.get_warn_by_id(warn_id)
        warn_info = None
        if updated_warn:
            warn_info = WarnInfo(
                id=updated_warn['id'],
                user_id=updated_warn['user_id'],
                reason=updated_warn['reason'],
                create_time=updated_warn['create_time'],
                moderator_id=updated_warn['moderator_id'],
                username=updated_warn.get('username')
            )
        
        # Envoyer une notification dans le canal de logs admin (si configuré)
        if ADMIN_LOG_CHANNEL_ID:
            try:
                log_channel_id = int(ADMIN_LOG_CHANNEL_ID)
                log_channel = guild.get_channel(log_channel_id)
                
                if log_channel:
                    user = guild.get_member(user_id)
                    user_mention = user.mention if user else f"<@{user_id}>"
                    
                    embed = discord.Embed(
                        title="✏️ Avertissement modifié (via API)",
                        description=f"Avertissement #{warn_id} modifié pour {user_mention}",
                        color=discord.Color.blue()
                    )
                    embed.add_field(name="Ancienne raison", value=warn.get('reason', 'N/A'), inline=False)
                    embed.add_field(name="Nouvelle raison", value=request.reason, inline=False)
                    embed.add_field(name="Modérateur", value=moderator_name, inline=True)
                    embed.add_field(name="Date", value=f"<t:{int(time.time())}:F>", inline=True)
                    
                    await log_channel.send(embed=embed)
            except Exception as e:
                logger.warning(f"Impossible d'envoyer le log dans le canal admin: {e}")
        
        logger.info(f'Avertissement {warn_id} modifié via API par {moderator_name} pour utilisateur {user_id}')
        
        return UpdateWarnReasonResponse(
            success=True,
            message=f"Avertissement #{warn_id} modifié avec succès",
            warn=warn_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Erreur dans l\'endpoint PUT /warns/{warn_id}: {e}', exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne: {str(e)}"
        )

@app.post("/warns/bulk", response_model=BulkDeleteWarnsResponse)
async def bulk_delete_warns(
    request: BulkDeleteWarnsRequest,
    _: bool = Depends(verify_api_token)
):
    """
    Supprime plusieurs avertissements en une fois
    
    Args:
        request: Données de la requête (warn_ids, moderator_id, moderator_name)
        _: Vérification du token API (via dependency)
    
    Returns:
        BulkDeleteWarnsResponse: Résultat de l'opération
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
        # Extraire les données de la requête
        warn_ids = request.warn_ids
        moderator_id = request.moderator_id
        moderator_name = request.moderator_name
        
        if not warn_ids:
            raise HTTPException(
                status_code=400,
                detail="Aucun avertissement à supprimer"
            )
        
        if not moderator_id:
            raise HTTPException(
                status_code=400,
                detail="moderator_id est requis"
            )
        
        # Récupérer le serveur Discord
        guild = bot_instance.get_guild(GUILD_ID)
        if not guild:
            raise HTTPException(
                status_code=404,
                detail=f"Serveur Discord (Guild ID: {GUILD_ID}) non trouvé"
            )
        
        # Récupérer le modérateur et vérifier ses permissions
        moderator = guild.get_member(moderator_id)
        if not moderator:
            raise HTTPException(
                status_code=404,
                detail=f"Modérateur Discord (ID: {moderator_id}) non trouvé sur le serveur"
            )
        
        moderator_name = moderator_name or moderator.display_name
        
        # Vérifier que le modérateur a un des rôles autorisés
        if ALLOWED_ROLE_IDS:
            moderator_roles = [str(role.id) for role in moderator.roles]
            has_permission = any(str(role_id).strip() in moderator_roles for role_id in ALLOWED_ROLE_IDS)
            
            if not has_permission:
                logger.warning(
                    f"Tentative de suppression multiple de warns par {moderator.display_name} (ID: {moderator_id}) "
                    f"sans les permissions nécessaires. Rôles: {moderator_roles}, Rôles autorisés: {ALLOWED_ROLE_IDS}"
                )
                raise HTTPException(
                    status_code=403,
                    detail="Vous n'avez pas les permissions nécessaires pour supprimer des avertissements. "
                           "Vous devez avoir un des rôles Discord autorisés."
                )
        
        # Récupérer les warns pour obtenir les user_id (pour le log)
        warns_to_delete = []
        for warn_id in warn_ids:
            warn = await warn_manager.get_warn_by_id(warn_id)
            if warn:
                warns_to_delete.append(warn)
        
        if not warns_to_delete:
            raise HTTPException(
                status_code=404,
                detail="Aucun avertissement trouvé parmi les IDs fournis"
            )
        
        # Supprimer les avertissements
        deleted_count = await warn_manager.delete_multiple_warns(warn_ids)
        
        if deleted_count == 0:
            raise HTTPException(
                status_code=500,
                detail="Erreur lors de la suppression des avertissements en base de données"
            )
        
        # Récupérer le user_id du premier warn pour le log (on suppose qu'ils sont tous du même utilisateur)
        user_id = warns_to_delete[0].get('user_id')
        warn_count = await warn_manager.get_warn_count(user_id)
        
        # Envoyer une notification dans le canal de logs admin (si configuré)
        if ADMIN_LOG_CHANNEL_ID:
            try:
                log_channel_id = int(ADMIN_LOG_CHANNEL_ID)
                log_channel = guild.get_channel(log_channel_id)
                
                if log_channel:
                    user = guild.get_member(user_id)
                    user_mention = user.mention if user else f"<@{user_id}>"
                    
                    embed = discord.Embed(
                        title="🗑️ Avertissements supprimés en masse (via API)",
                        description=f"{deleted_count} avertissement(s) supprimé(s) pour {user_mention}",
                        color=discord.Color.red()
                    )
                    embed.add_field(name="IDs supprimés", value=', '.join([f"#{w['id']}" for w in warns_to_delete[:10]]), inline=False)
                    if len(warns_to_delete) > 10:
                        embed.add_field(name="...", value=f"Et {len(warns_to_delete) - 10} autre(s)", inline=False)
                    embed.add_field(name="Modérateur", value=moderator_name, inline=True)
                    embed.add_field(name="Date", value=f"<t:{int(time.time())}:F>", inline=True)
                    embed.add_field(name="Total d'avertissements restants", value=str(warn_count), inline=True)
                    
                    await log_channel.send(embed=embed)
            except Exception as e:
                logger.warning(f"Impossible d'envoyer le log dans le canal admin: {e}")
        
        logger.info(f'{deleted_count} avertissement(s) supprimé(s) via API par {moderator_name} pour utilisateur {user_id}')
        
        return BulkDeleteWarnsResponse(
            success=True,
            message=f"{deleted_count} avertissement(s) supprimé(s) avec succès",
            deleted_count=deleted_count,
            warn_count=warn_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Erreur dans l\'endpoint DELETE /warns/bulk: {e}', exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne: {str(e)}"
        )

# ==================== ENDPOINTS DE MODÉRATION ====================

@app.post("/kick", response_model=ModerationActionResponse)
async def kick_user(
    request: ModerationActionRequest,
    _: bool = Depends(verify_api_token)
):
    """
    Expulse un utilisateur du serveur Discord.
    """
    if not bot_instance or not bot_instance.is_ready():
        raise HTTPException(status_code=503, detail="Bot Discord non disponible ou non connecté")
    
    try:
        guild = bot_instance.get_guild(GUILD_ID)
        if not guild:
            raise HTTPException(status_code=404, detail=f"Serveur Discord (Guild ID: {GUILD_ID}) non trouvé")
        
        user = guild.get_member(request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"Utilisateur Discord (ID: {request.user_id}) non trouvé sur le serveur")
        
        moderator = guild.get_member(request.moderator_id)
        if not moderator:
            raise HTTPException(status_code=404, detail=f"Modérateur Discord (ID: {request.moderator_id}) non trouvé sur le serveur")
        
        moderator_name = request.moderator_name or moderator.display_name
        
        # Vérifier les permissions
        if ALLOWED_ROLE_IDS:
            moderator_roles = [str(role.id) for role in moderator.roles]
            has_permission = any(str(role_id).strip() in moderator_roles for role_id in ALLOWED_ROLE_IDS)
            if not has_permission:
                raise HTTPException(status_code=403, detail="Vous n'avez pas les permissions nécessaires pour expulser un utilisateur.")
        
        # Vérifier que le modérateur ne peut pas se kick lui-même
        if user.id == moderator.id:
            raise HTTPException(status_code=400, detail="Vous ne pouvez pas vous expulser vous-même.")
        
        # Vérifier que le modérateur ne peut pas kick quelqu'un avec des permissions supérieures
        if user.top_role >= moderator.top_role:
            raise HTTPException(status_code=403, detail="Vous ne pouvez pas expulser quelqu'un avec un rôle supérieur ou égal au vôtre.")
        
        # Expulser l'utilisateur
        await user.kick(reason=request.reason)
        
        # Log dans le canal admin si configuré
        if ADMIN_LOG_CHANNEL_ID:
            try:
                log_channel = guild.get_channel(int(ADMIN_LOG_CHANNEL_ID))
                if log_channel:
                    embed = discord.Embed(
                        title="👢 Utilisateur Expulsé (via API)",
                        description=f"{user.mention} a été expulsé du serveur",
                        color=discord.Color.red()
                    )
                    embed.add_field(name="Raison", value=request.reason, inline=False)
                    embed.add_field(name="Modérateur", value=moderator_name, inline=True)
                    embed.add_field(name="Date", value=f"<t:{int(time.time())}:F>", inline=True)
                    await log_channel.send(embed=embed)
            except Exception as e:
                logger.warning(f"Impossible d'envoyer le log dans le canal admin: {e}")
        
        logger.info(f'Utilisateur {user.display_name} (ID: {user.id}) expulsé via API par {moderator_name}')
        
        # Incrémenter le compteur de métriques
        _metrics['api_kicks_total'] += 1
        
        return ModerationActionResponse(
            success=True,
            message=f"{user.display_name} a été expulsé avec succès."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Erreur dans l\'endpoint POST /kick: {e}', exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")

@app.post("/ban", response_model=ModerationActionResponse)
async def ban_user(
    request: ModerationActionRequest,
    _: bool = Depends(verify_api_token)
):
    """
    Bannit un utilisateur du serveur Discord.
    """
    if not bot_instance or not bot_instance.is_ready():
        raise HTTPException(status_code=503, detail="Bot Discord non disponible ou non connecté")
    
    try:
        guild = bot_instance.get_guild(GUILD_ID)
        if not guild:
            raise HTTPException(status_code=404, detail=f"Serveur Discord (Guild ID: {GUILD_ID}) non trouvé")
        
        user = guild.get_member(request.user_id)
        user_obj = None
        user_display = None
        
        if user:
            moderator = guild.get_member(request.moderator_id)
            if not moderator:
                raise HTTPException(status_code=404, detail=f"Modérateur Discord (ID: {request.moderator_id}) non trouvé sur le serveur")
            
            moderator_name = request.moderator_name or moderator.display_name
            
            # Vérifier les permissions
            if ALLOWED_ROLE_IDS:
                moderator_roles = [str(role.id) for role in moderator.roles]
                has_permission = any(str(role_id).strip() in moderator_roles for role_id in ALLOWED_ROLE_IDS)
                if not has_permission:
                    raise HTTPException(status_code=403, detail="Vous n'avez pas les permissions nécessaires pour bannir un utilisateur.")
            
            # Vérifier que le modérateur ne peut pas se ban lui-même
            if user.id == moderator.id:
                raise HTTPException(status_code=400, detail="Vous ne pouvez pas vous bannir vous-même.")
            
            # Vérifier que le modérateur ne peut pas ban quelqu'un avec des permissions supérieures
            if user.top_role >= moderator.top_role:
                raise HTTPException(status_code=403, detail="Vous ne pouvez pas bannir quelqu'un avec un rôle supérieur ou égal au vôtre.")
            
            user_obj = user
            user_display = user.display_name
        else:
            # Si l'utilisateur n'est pas sur le serveur, on peut quand même le bannir par ID
            try:
                user_obj = await bot_instance.fetch_user(request.user_id)
                moderator = guild.get_member(request.moderator_id)
                if not moderator:
                    raise HTTPException(status_code=404, detail=f"Modérateur Discord (ID: {request.moderator_id}) non trouvé sur le serveur")
                
                moderator_name = request.moderator_name or moderator.display_name
                
                # Vérifier les permissions
                if ALLOWED_ROLE_IDS:
                    moderator_roles = [str(role.id) for role in moderator.roles]
                    has_permission = any(str(role_id).strip() in moderator_roles for role_id in ALLOWED_ROLE_IDS)
                    if not has_permission:
                        raise HTTPException(status_code=403, detail="Vous n'avez pas les permissions nécessaires pour bannir un utilisateur.")
                
                user_display = f"Utilisateur ID: {request.user_id}"
            except discord.NotFound:
                raise HTTPException(status_code=404, detail=f"Utilisateur Discord (ID: {request.user_id}) non trouvé")
        
        # Bannir l'utilisateur
        await guild.ban(user_obj, reason=request.reason, delete_message_days=7)
        
        # Log dans le canal admin si configuré
        if ADMIN_LOG_CHANNEL_ID:
            try:
                log_channel = guild.get_channel(int(ADMIN_LOG_CHANNEL_ID))
                if log_channel:
                    embed = discord.Embed(
                        title="🔨 Utilisateur Banni (via API)",
                        description=f"{user_obj.mention if hasattr(user_obj, 'mention') else user_display} a été banni du serveur",
                        color=discord.Color.red()
                    )
                    embed.add_field(name="Raison", value=request.reason, inline=False)
                    embed.add_field(name="Modérateur", value=moderator_name, inline=True)
                    embed.add_field(name="Date", value=f"<t:{int(time.time())}:F>", inline=True)
                    await log_channel.send(embed=embed)
            except Exception as e:
                logger.warning(f"Impossible d'envoyer le log dans le canal admin: {e}")
        
        logger.info(f'Utilisateur {user_display} (ID: {request.user_id}) banni via API par {moderator_name}')
        
        # Incrémenter le compteur de métriques
        _metrics['api_bans_total'] += 1
        
        return ModerationActionResponse(
            success=True,
            message=f"{user_display} a été banni avec succès."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Erreur dans l\'endpoint POST /ban: {e}', exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")

@app.post("/mute", response_model=ModerationActionResponse)
async def mute_user(
    request: ModerationActionRequest,
    _: bool = Depends(verify_api_token)
):
    """
    Mute un utilisateur dans le serveur Discord.
    """
    if not bot_instance or not bot_instance.is_ready():
        raise HTTPException(status_code=503, detail="Bot Discord non disponible ou non connecté")
    
    try:
        guild = bot_instance.get_guild(GUILD_ID)
        if not guild:
            raise HTTPException(status_code=404, detail=f"Serveur Discord (Guild ID: {GUILD_ID}) non trouvé")
        
        user = guild.get_member(request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"Utilisateur Discord (ID: {request.user_id}) non trouvé sur le serveur")
        
        moderator = guild.get_member(request.moderator_id)
        if not moderator:
            raise HTTPException(status_code=404, detail=f"Modérateur Discord (ID: {request.moderator_id}) non trouvé sur le serveur")
        
        moderator_name = request.moderator_name or moderator.display_name
        
        # Vérifier les permissions
        if ALLOWED_ROLE_IDS:
            moderator_roles = [str(role.id) for role in moderator.roles]
            has_permission = any(str(role_id).strip() in moderator_roles for role_id in ALLOWED_ROLE_IDS)
            if not has_permission:
                raise HTTPException(status_code=403, detail="Vous n'avez pas les permissions nécessaires pour muter un utilisateur.")
        
        # Assurer que le rôle "mute" existe
        muted_role = discord.utils.get(guild.roles, name="mute")
        if not muted_role:
            muted_role = await guild.create_role(name="mute", reason="Role needed for mute functionality")
            for channel in guild.channels:
                try:
                    await channel.set_permissions(muted_role, send_messages=False, speak=False)
                except:
                    pass  # Ignorer les erreurs pour les catégories
        
        # Ajouter le rôle "mute" au membre
        await user.add_roles(muted_role, reason=request.reason)
        
        # Log dans le canal admin si configuré
        if ADMIN_LOG_CHANNEL_ID:
            try:
                log_channel = guild.get_channel(int(ADMIN_LOG_CHANNEL_ID))
                if log_channel:
                    embed = discord.Embed(
                        title="🔇 Utilisateur Muté (via API)",
                        description=f"{user.mention} a été muté",
                        color=discord.Color.orange()
                    )
                    embed.add_field(name="Raison", value=request.reason, inline=False)
                    embed.add_field(name="Modérateur", value=moderator_name, inline=True)
                    embed.add_field(name="Date", value=f"<t:{int(time.time())}:F>", inline=True)
                    await log_channel.send(embed=embed)
            except Exception as e:
                logger.warning(f"Impossible d'envoyer le log dans le canal admin: {e}")
        
        logger.info(f'Utilisateur {user.display_name} (ID: {user.id}) muté via API par {moderator_name}')
        
        # Incrémenter le compteur de métriques
        _metrics['api_mutes_total'] += 1
        
        return ModerationActionResponse(
            success=True,
            message=f"{user.display_name} a été muté avec succès."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Erreur dans l\'endpoint POST /mute: {e}', exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")

@app.post("/unmute", response_model=ModerationActionResponse)
async def unmute_user(
    request: ModerationActionRequest,
    _: bool = Depends(verify_api_token)
):
    """
    Unmute un utilisateur dans le serveur Discord.
    """
    if not bot_instance or not bot_instance.is_ready():
        raise HTTPException(status_code=503, detail="Bot Discord non disponible ou non connecté")
    
    try:
        guild = bot_instance.get_guild(GUILD_ID)
        if not guild:
            raise HTTPException(status_code=404, detail=f"Serveur Discord (Guild ID: {GUILD_ID}) non trouvé")
        
        user = guild.get_member(request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"Utilisateur Discord (ID: {request.user_id}) non trouvé sur le serveur")
        
        moderator = guild.get_member(request.moderator_id)
        if not moderator:
            raise HTTPException(status_code=404, detail=f"Modérateur Discord (ID: {request.moderator_id}) non trouvé sur le serveur")
        
        moderator_name = request.moderator_name or moderator.display_name
        
        # Vérifier les permissions
        if ALLOWED_ROLE_IDS:
            moderator_roles = [str(role.id) for role in moderator.roles]
            has_permission = any(str(role_id).strip() in moderator_roles for role_id in ALLOWED_ROLE_IDS)
            if not has_permission:
                raise HTTPException(status_code=403, detail="Vous n'avez pas les permissions nécessaires pour unmuter un utilisateur.")
        
        # Vérifier si le rôle "mute" existe
        muted_role = discord.utils.get(guild.roles, name="mute")
        if not muted_role:
            raise HTTPException(status_code=404, detail="Le rôle 'mute' n'existe pas.")
        
        # Retirer le rôle "mute" du membre
        await user.remove_roles(muted_role, reason=request.reason or "Unmute via API")
        
        # Log dans le canal admin si configuré
        if ADMIN_LOG_CHANNEL_ID:
            try:
                log_channel = guild.get_channel(int(ADMIN_LOG_CHANNEL_ID))
                if log_channel:
                    embed = discord.Embed(
                        title="🔊 Utilisateur Unmuté (via API)",
                        description=f"{user.mention} a été unmuté",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="Raison", value=request.reason or "Aucune raison spécifiée", inline=False)
                    embed.add_field(name="Modérateur", value=moderator_name, inline=True)
                    embed.add_field(name="Date", value=f"<t:{int(time.time())}:F>", inline=True)
                    await log_channel.send(embed=embed)
            except Exception as e:
                logger.warning(f"Impossible d'envoyer le log dans le canal admin: {e}")
        
        logger.info(f'Utilisateur {user.display_name} (ID: {user.id}) unmuté via API par {moderator_name}')
        
        return ModerationActionResponse(
            success=True,
            message=f"{user.display_name} a été unmuté avec succès."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Erreur dans l\'endpoint POST /unmute: {e}', exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")

@app.post("/tempban", response_model=TempModerationActionResponse)
async def tempban_user(
    request: TempModerationActionRequest,
    _: bool = Depends(verify_api_token)
):
    """
    Bannit temporairement un utilisateur du serveur Discord.
    """
    if not bot_instance or not bot_instance.is_ready():
        raise HTTPException(status_code=503, detail="Bot Discord non disponible ou non connecté")
    
    try:
        guild = bot_instance.get_guild(GUILD_ID)
        if not guild:
            raise HTTPException(status_code=404, detail=f"Serveur Discord (Guild ID: {GUILD_ID}) non trouvé")
        
        user = guild.get_member(request.user_id)
        user_obj = None
        user_display = None
        
        if user:
            moderator = guild.get_member(request.moderator_id)
            if not moderator:
                raise HTTPException(status_code=404, detail=f"Modérateur Discord (ID: {request.moderator_id}) non trouvé sur le serveur")
            
            moderator_name = request.moderator_name or moderator.display_name
            
            # Vérifier les permissions
            if ALLOWED_ROLE_IDS:
                moderator_roles = [str(role.id) for role in moderator.roles]
                has_permission = any(str(role_id).strip() in moderator_roles for role_id in ALLOWED_ROLE_IDS)
                if not has_permission:
                    raise HTTPException(status_code=403, detail="Vous n'avez pas les permissions nécessaires pour bannir temporairement un utilisateur.")
            
            # Vérifier que le modérateur ne peut pas se ban lui-même
            if user.id == moderator.id:
                raise HTTPException(status_code=400, detail="Vous ne pouvez pas vous bannir vous-même.")
            
            # Vérifier que le modérateur ne peut pas ban quelqu'un avec des permissions supérieures
            if user.top_role >= moderator.top_role:
                raise HTTPException(status_code=403, detail="Vous ne pouvez pas bannir quelqu'un avec un rôle supérieur ou égal au vôtre.")
            
            user_obj = user
            user_display = user.display_name
        else:
            # Si l'utilisateur n'est pas sur le serveur, on peut quand même le bannir par ID
            try:
                user_obj = await bot_instance.fetch_user(request.user_id)
                moderator = guild.get_member(request.moderator_id)
                if not moderator:
                    raise HTTPException(status_code=404, detail=f"Modérateur Discord (ID: {request.moderator_id}) non trouvé sur le serveur")
                
                moderator_name = request.moderator_name or moderator.display_name
                
                # Vérifier les permissions
                if ALLOWED_ROLE_IDS:
                    moderator_roles = [str(role.id) for role in moderator.roles]
                    has_permission = any(str(role_id).strip() in moderator_roles for role_id in ALLOWED_ROLE_IDS)
                    if not has_permission:
                        raise HTTPException(status_code=403, detail="Vous n'avez pas les permissions nécessaires pour bannir temporairement un utilisateur.")
                
                user_display = f"Utilisateur ID: {request.user_id}"
            except discord.NotFound:
                raise HTTPException(status_code=404, detail=f"Utilisateur Discord (ID: {request.user_id}) non trouvé")
        
        # Convertir la durée en secondes
        unit = request.unit.lower()
        if unit in ["secondes", "seconde"]:
            duration_seconds = request.duration
        elif unit in ["minutes", "minute"]:
            duration_seconds = request.duration * 60
        elif unit in ["heures", "heure"]:
            duration_seconds = request.duration * 60 * 60
        elif unit in ["jours", "jour"]:
            duration_seconds = request.duration * 60 * 60 * 24
        elif unit in ["mois"]:
            duration_seconds = request.duration * 60 * 60 * 24 * 30
        elif unit in ["années", "année"]:
            duration_seconds = request.duration * 60 * 60 * 24 * 365
        else:
            raise HTTPException(status_code=400, detail="Unité de temps invalide. Utilisez 'secondes', 'minutes', 'heures', 'jours', 'mois', ou 'années'.")
        
        # Bannir l'utilisateur
        await guild.ban(user_obj, reason=request.reason, delete_message_days=7)
        
        # Calculer le timestamp de débannissement
        unban_time = int(time.time()) + duration_seconds
        
        # Créer une tâche pour débannir le membre après la durée spécifiée
        async def temp_unban():
            await asyncio.sleep(duration_seconds)
            try:
                await guild.unban(user_obj, reason="Bannissement temporaire terminé")
                logger.info(f'Utilisateur {user_obj.display_name if hasattr(user_obj, "display_name") else user_obj.id} (ID: {user_obj.id}) débanni automatiquement')
            except Exception as e:
                logger.error(f"Erreur lors du débannissement automatique de {user_obj.id}: {e}")
        
        asyncio.create_task(temp_unban())
        
        # Log dans le canal admin si configuré
        if ADMIN_LOG_CHANNEL_ID:
            try:
                log_channel = guild.get_channel(int(ADMIN_LOG_CHANNEL_ID))
                if log_channel:
                    embed = discord.Embed(
                        title="⏰ Utilisateur Banni Temporairement (via API)",
                        description=f"{user_obj.mention if hasattr(user_obj, 'mention') else user_display} a été banni temporairement",
                        color=discord.Color.orange()
                    )
                    embed.add_field(name="Durée", value=f"{request.duration} {request.unit}", inline=True)
                    embed.add_field(name="Débannissement prévu", value=f"<t:{unban_time}:F>", inline=True)
                    embed.add_field(name="Raison", value=request.reason, inline=False)
                    embed.add_field(name="Modérateur", value=moderator_name, inline=True)
                    embed.add_field(name="Date", value=f"<t:{int(time.time())}:F>", inline=True)
                    await log_channel.send(embed=embed)
            except Exception as e:
                logger.warning(f"Impossible d'envoyer le log dans le canal admin: {e}")
        
        logger.info(f'Utilisateur {user_display} (ID: {request.user_id}) banni temporairement via API par {moderator_name} pour {request.duration} {request.unit}')
        
        return TempModerationActionResponse(
            success=True,
            message=f"{user_display} a été banni temporairement pour {request.duration} {request.unit}.",
            unban_time=unban_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Erreur dans l\'endpoint POST /tempban: {e}', exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")

@app.post("/tempmute", response_model=TempModerationActionResponse)
async def tempmute_user(
    request: TempModerationActionRequest,
    _: bool = Depends(verify_api_token)
):
    """
    Mute temporairement un utilisateur dans le serveur Discord.
    """
    if not bot_instance or not bot_instance.is_ready():
        raise HTTPException(status_code=503, detail="Bot Discord non disponible ou non connecté")
    
    try:
        guild = bot_instance.get_guild(GUILD_ID)
        if not guild:
            raise HTTPException(status_code=404, detail=f"Serveur Discord (Guild ID: {GUILD_ID}) non trouvé")
        
        user = guild.get_member(request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"Utilisateur Discord (ID: {request.user_id}) non trouvé sur le serveur")
        
        moderator = guild.get_member(request.moderator_id)
        if not moderator:
            raise HTTPException(status_code=404, detail=f"Modérateur Discord (ID: {request.moderator_id}) non trouvé sur le serveur")
        
        moderator_name = request.moderator_name or moderator.display_name
        
        # Vérifier les permissions
        if ALLOWED_ROLE_IDS:
            moderator_roles = [str(role.id) for role in moderator.roles]
            has_permission = any(str(role_id).strip() in moderator_roles for role_id in ALLOWED_ROLE_IDS)
            if not has_permission:
                raise HTTPException(status_code=403, detail="Vous n'avez pas les permissions nécessaires pour muter temporairement un utilisateur.")
        
        # Convertir la durée en secondes
        unit = request.unit.lower()
        if unit in ["secondes", "seconde"]:
            duration_seconds = request.duration
        elif unit in ["minutes", "minute"]:
            duration_seconds = request.duration * 60
        elif unit in ["heures", "heure"]:
            duration_seconds = request.duration * 60 * 60
        elif unit in ["jours", "jour"]:
            duration_seconds = request.duration * 60 * 60 * 24
        elif unit in ["mois"]:
            duration_seconds = request.duration * 60 * 60 * 24 * 30
        elif unit in ["années", "année"]:
            duration_seconds = request.duration * 60 * 60 * 24 * 365
        else:
            raise HTTPException(status_code=400, detail="Unité de temps invalide. Utilisez 'secondes', 'minutes', 'heures', 'jours', 'mois', ou 'années'.")
        
        # Assurer que le rôle "mute" existe
        muted_role = discord.utils.get(guild.roles, name="mute")
        if not muted_role:
            muted_role = await guild.create_role(name="mute", reason="Role needed for mute functionality")
            for channel in guild.channels:
                try:
                    await channel.set_permissions(muted_role, send_messages=False, speak=False)
                except:
                    pass  # Ignorer les erreurs pour les catégories
        
        # Ajouter le rôle "mute" au membre
        await user.add_roles(muted_role, reason=request.reason)
        
        # Calculer le timestamp de unmute
        unmute_time = int(time.time()) + duration_seconds
        
        # Créer une tâche pour unmuter le membre après la durée spécifiée
        async def temp_unmute():
            await asyncio.sleep(duration_seconds)
            try:
                await user.remove_roles(muted_role, reason="Mute temporaire terminé")
                logger.info(f'Utilisateur {user.display_name} (ID: {user.id}) unmuté automatiquement')
            except Exception as e:
                logger.error(f"Erreur lors du unmute automatique de {user.id}: {e}")
        
        asyncio.create_task(temp_unmute())
        
        # Log dans le canal admin si configuré
        if ADMIN_LOG_CHANNEL_ID:
            try:
                log_channel = guild.get_channel(int(ADMIN_LOG_CHANNEL_ID))
                if log_channel:
                    embed = discord.Embed(
                        title="⏰ Utilisateur Muté Temporairement (via API)",
                        description=f"{user.mention} a été muté temporairement",
                        color=discord.Color.orange()
                    )
                    embed.add_field(name="Durée", value=f"{request.duration} {request.unit}", inline=True)
                    embed.add_field(name="Unmute prévu", value=f"<t:{unmute_time}:F>", inline=True)
                    embed.add_field(name="Raison", value=request.reason, inline=False)
                    embed.add_field(name="Modérateur", value=moderator_name, inline=True)
                    embed.add_field(name="Date", value=f"<t:{int(time.time())}:F>", inline=True)
                    await log_channel.send(embed=embed)
            except Exception as e:
                logger.warning(f"Impossible d'envoyer le log dans le canal admin: {e}")
        
        logger.info(f'Utilisateur {user.display_name} (ID: {user.id}) muté temporairement via API par {moderator_name} pour {request.duration} {request.unit}')
        
        return TempModerationActionResponse(
            success=True,
            message=f"{user.display_name} a été muté temporairement pour {request.duration} {request.unit}.",
            unban_time=unmute_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Erreur dans l\'endpoint POST /tempmute: {e}', exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")

def run_api(host: str = "0.0.0.0", port: int = None):
    """Démarre le serveur API"""
    import uvicorn
    port = port or API_PORT
    logger.info(f"🚀 Démarrage de l'API Hermes sur {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")

