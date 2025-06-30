"""
Module de logging pour Hermes Bot

Ce module gère tous les logs du bot Discord, incluant:
- Logs des commandes utilisateur
- Logs des actions administratives
- Logs des événements vocaux
- Logs des attributions de rôles
- Logs des confessions

Auteur: Dr.TableBasse
Version: 2.0
"""

import discord
from datetime import datetime
import os
from dotenv import load_dotenv
from utils.constants import get_env_var
import functools
import weakref

# Charger les variables d'environnement
load_dotenv()

def get_env_var(var_name: str, required: bool = True):
    """Récupère une variable d'environnement avec gestion d'erreur"""
    value = os.getenv(var_name)
    if required and not value:
        raise ValueError(f"❌ Variable d'environnement '{var_name}' manquante dans le fichier .env")
    return value

# Fonction utilitaire pour nettoyer un ID
def clean_id(val):
    if val is None:
        return None
    return val.split('#')[0].split()[0].strip()

#Logs commandes
async def log_command_usage(interaction, command_name, member=None, reason=None, log_channel_id=None):
    """Log l'utilisation des commandes par les utilisateurs"""
    try:
        guild = interaction.guild
        
        # Utiliser l'ID du canal si fourni, sinon utiliser la valeur depuis .env
        if log_channel_id is None:
            command_log_id = get_env_var('COMMAND_LOG_CHANNEL_ID', required=False)
            cleaned = clean_id(command_log_id)
            if cleaned and cleaned.isdigit():
                log_channel_id = int(cleaned)
            else:
                log_channel_id = None
        if log_channel_id is None:
            fallback = get_env_var('LOG_CHANNEL_ID', required=True)
            cleaned = clean_id(fallback)
            if cleaned and cleaned.isdigit():
                log_channel_id = int(cleaned)
            else:
                print(f"[ERROR] log_command_usage: ID de salon invalide")
                return
        log_channel = guild.get_channel(log_channel_id)
        
        if log_channel:
            now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            
            # Déterminer la couleur selon le type de commande
            if command_name in ["warn", "kick", "ban", "mute", "tempban", "tempmute"]:
                color = discord.Color.red()
                title = "🛡️ Action Administrative"
            elif command_name in ["blague", "anime", "confess", "ping"]:
                color = discord.Color.green()
                title = "📝 Commande Utilisée"
            else:
                color = discord.Color.blue()
                title = "⚙️ Commande Système"
            
            embed = discord.Embed(
                title=title,
                description=f'{interaction.user.mention} a utilisé la commande **/{command_name}**',
                color=color,
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
            
            # Ajouter des informations supplémentaires selon le contexte
            if member:
                embed.add_field(name="👤 Utilisateur ciblé", value=member.mention, inline=True)
            if reason:
                embed.add_field(name="📋 Raison", value=reason, inline=True)
            
            embed.add_field(name="📅 Date", value=now, inline=False)
            embed.add_field(name="📍 Canal", value=interaction.channel.mention, inline=True)
            
            await log_channel.send(embed=embed)
        else:
            print(f"[ERROR] Log channel avec ID {log_channel_id} non trouvé dans guild '{guild.name}'")
            
    except Exception as e:
        print(f"[ERROR] Erreur lors du log de commande: {e}")

async def log_admin_action(interaction, action_type, target_user, reason=None, duration=None, log_channel_id=None, extra_args=None):
    """Log les actions administratives (warn, kick, ban, mute, etc.)"""
    try:
        guild = interaction.guild
        if extra_args is None:
            extra_args = {}
        if log_channel_id is None:
            admin_log_id = get_env_var('ADMIN_LOG_CHANNEL_ID', required=False)
            cleaned = clean_id(admin_log_id)
            if cleaned and cleaned.isdigit():
                log_channel_id = int(cleaned)
            else:
                log_channel_id = None
        if log_channel_id is None:
            fallback = get_env_var('LOG_CHANNEL_ID', required=True)
            cleaned = clean_id(fallback)
            if cleaned and cleaned.isdigit():
                log_channel_id = int(cleaned)
            else:
                print(f"[ERROR] log_admin_action: ID de salon invalide")
                return
        log_channel = guild.get_channel(log_channel_id)
        if log_channel:
            now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            # Définir les icônes et couleurs selon l'action
            action_config = {
                "warn": {"icon": "⚠️", "color": discord.Color.orange(), "title": "Avertissement"},
                "kick": {"icon": "👢", "color": discord.Color.red(), "title": "Expulsion"},
                "ban": {"icon": "🔨", "color": discord.Color.dark_red(), "title": "Bannissement"},
                "mute": {"icon": "🔇", "color": discord.Color.purple(), "title": "Mute"},
                "tempmute": {"icon": "⏰", "color": discord.Color.purple(), "title": "Mute Temporaire"},
                "tempban": {"icon": "⏰", "color": discord.Color.dark_red(), "title": "Bannissement Temporaire"},
                "unmute": {"icon": "🔊", "color": discord.Color.green(), "title": "Unmute"},
                "clear": {"icon": "🧹", "color": discord.Color.blue(), "title": "Nettoyage"}
            }
            config = action_config.get(action_type, {"icon": "⚙️", "color": discord.Color.light_grey(), "title": action_type.title()})
            embed = discord.Embed(
                title=f"{config['icon']} {config['title']} - Action Administrative",
                description=f"**Modérateur:** {interaction.user.mention}\n**Action:** {action_type.upper()}",
                color=config['color'],
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=target_user.avatar.url if target_user.avatar else target_user.default_avatar.url)
            embed.add_field(name="👤 Utilisateur", value=target_user.mention, inline=True)
            embed.add_field(name="🛡️ Modérateur", value=interaction.user.mention, inline=True)
            if reason:
                embed.add_field(name="📋 Raison", value=reason, inline=False)
            if duration:
                embed.add_field(name="⏱️ Durée", value=duration, inline=True)
            # Afficher les arguments de la commande
            if extra_args:
                args_str = "\n".join([f"`{k}`: {v}" for k, v in extra_args.items()])
                embed.add_field(name="📋 Arguments", value=args_str, inline=False)
            embed.add_field(name="📅 Date", value=now, inline=False)
            embed.add_field(name="📍 Canal", value=interaction.channel.mention, inline=True)
            # Ajouter des informations sur les permissions du modérateur
            if hasattr(interaction.user, 'guild_permissions'):
                permissions = []
                if interaction.user.guild_permissions.administrator:
                    permissions.append("👑 Admin")
                if interaction.user.guild_permissions.manage_messages:
                    permissions.append("🛡️ Modérateur")
                if interaction.user.guild_permissions.manage_roles:
                    permissions.append("🔑 Gestionnaire Rôles")
                if permissions:
                    embed.add_field(name="🔐 Permissions", value=", ".join(permissions), inline=True)
            moderator_roles = [role.name for role in getattr(interaction.user, 'roles', []) if hasattr(role, 'permissions') and (role.permissions.manage_messages or role.permissions.administrator)]
            if moderator_roles:
                embed.add_field(name="🔑 Rôles Modérateur", value=", ".join(moderator_roles), inline=False)
            await log_channel.send(embed=embed)
        else:
            print(f"[ERROR] Admin log channel avec ID {log_channel_id} non trouvé dans guild '{guild.name}'")
    except Exception as e:
        print(f"[ERROR] Erreur lors du log d'action administrative: {e}")

async def log_voice_event(bot, event_type, user_id, content, log_channel_id=None):
    """Log les événements vocaux"""
    try:
        # Récupérer le GUILD_ID depuis les variables d'environnement
        GUILD_ID = int(get_env_var('GUILD_ID', required=True))
        guild = bot.get_guild(GUILD_ID)
        
        if not guild:
            print(f"[ERROR] Guild non trouvé pour l'ID: {GUILD_ID}")
            return
        
        if log_channel_id is None:
            voice_log_id = get_env_var('VOICE_LOG_CHANNEL_ID', required=False)
            cleaned = clean_id(voice_log_id)
            if cleaned and cleaned.isdigit():
                log_channel_id = int(cleaned)
            else:
                log_channel_id = None
        if log_channel_id is None:
            fallback = get_env_var('LOG_CHANNEL_ID', required=True)
            cleaned = clean_id(fallback)
            if cleaned and cleaned.isdigit():
                log_channel_id = int(cleaned)
            else:
                print(f"[ERROR] log_voice_event: ID de salon invalide")
                return
        log_channel = guild.get_channel(log_channel_id)
        
        if log_channel:
            now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            embed = discord.Embed(
                title="Log de Salon Vocal",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            # Essayer de récupérer l'utilisateur
            try:
                user = await bot.fetch_user(user_id)
                embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
                embed.add_field(name="Utilisateur", value=user.mention, inline=False)
            except:
                embed.add_field(name="Utilisateur", value=f"<@{user_id}>", inline=False)
                
            embed.add_field(name="Action", value=event_type, inline=False)
            embed.add_field(name="Détails", value=content, inline=False)
            embed.add_field(name="Date", value=now, inline=False)
            
            await log_channel.send(embed=embed)
        else:
            print(f"[ERROR] Log channel avec ID {log_channel_id} non trouvé dans guild '{guild.name}'")
            
    except Exception as e:
        print(f"[ERROR] Erreur lors du log vocal: {e}")


# New function for role assignment logging
async def log_role_assignment(member, role_name, log_channel_id=None):
    """Log l'attribution de rôles"""
    try:
        guild = member.guild
        
        if log_channel_id is None:
            role_log_id = get_env_var('ROLE_LOG_CHANNEL_ID', required=False)
            cleaned = clean_id(role_log_id)
            if cleaned and cleaned.isdigit():
                log_channel_id = int(cleaned)
            else:
                log_channel_id = None
        if log_channel_id is None:
            fallback = get_env_var('LOG_CHANNEL_ID', required=True)
            cleaned = clean_id(fallback)
            if cleaned and cleaned.isdigit():
                log_channel_id = int(cleaned)
            else:
                print(f"[ERROR] log_role_assignment: ID de salon invalide")
                return
        log_channel = guild.get_channel(log_channel_id)
        
        if log_channel:
            now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            embed = discord.Embed(
                title="Rôle Attribué",
                color=discord.Color.purple(),
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=member.avatar.url)
            embed.add_field(name="Utilisateur", value=member.mention, inline=False)
            embed.add_field(name="Rôle Attribué", value=role_name, inline=False)
            embed.add_field(name="Date", value=now, inline=False)
            await log_channel.send(embed=embed)
        else:
            print(f"[ERROR] Log channel avec ID {log_channel_id} non trouvé dans guild '{guild.name}'")
            
    except Exception as e:
        print(f"[ERROR] Erreur lors du log d'attribution de rôle: {e}")


async def log_sanction(member, action, reason=None, log_channel_id=None, action_taken_by=None):
    """Log les sanctions"""
    try:
        guild = member.guild
        
        if log_channel_id is None:
            sanction_log_id = get_env_var('SANCTION_LOG_CHANNEL_ID', required=False)
            cleaned = clean_id(sanction_log_id)
            if cleaned and cleaned.isdigit():
                log_channel_id = int(cleaned)
            else:
                log_channel_id = None
        if log_channel_id is None:
            fallback = get_env_var('LOG_CHANNEL_ID', required=True)
            cleaned = clean_id(fallback)
            if cleaned and cleaned.isdigit():
                log_channel_id = int(cleaned)
            else:
                print(f"[ERROR] log_sanction: ID de salon invalide")
                return
        log_channel = guild.get_channel(log_channel_id)
        
        if log_channel:
            now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            embed = discord.Embed(
                title="Sanction Appliquée",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=member.avatar.url)
            embed.add_field(name="Utilisateur", value=member.mention, inline=False)
            embed.add_field(name="Action", value=action, inline=False)
            if action_taken_by:
                embed.add_field(name="Commandé par", value=action_taken_by, inline=False)
            if reason:
                embed.add_field(name="Raison", value=reason, inline=False)
            embed.add_field(name="Date", value=now, inline=False)
            await log_channel.send(embed=embed)
        else:
            print(f"[ERROR] Log channel avec ID {log_channel_id} non trouvé dans guild '{guild.name}'")
            
    except Exception as e:
        print(f"[ERROR] Erreur lors du log de sanction: {e}")


async def log_confession(user, confession_message, log_channel_id=None):
    """Log les confessions"""
    try:
        # Récupérer le GUILD_ID depuis les variables d'environnement
        GUILD_ID = int(get_env_var('GUILD_ID', required=True))
        guild = user.guild
        
        if not guild:
            print(f"[ERROR] Guild non trouvé pour l'utilisateur")
            return
        
        if log_channel_id is None:
            confession_log_id = get_env_var('CONFESSION_LOG_CHANNEL_ID', required=False)
            cleaned = clean_id(confession_log_id)
            if cleaned and cleaned.isdigit():
                log_channel_id = int(cleaned)
            else:
                log_channel_id = None
        if log_channel_id is None:
            fallback = get_env_var('LOG_CHANNEL_ID', required=True)
            cleaned = clean_id(fallback)
            if cleaned and cleaned.isdigit():
                log_channel_id = int(cleaned)
            else:
                print(f"[ERROR] log_confession: ID de salon invalide")
                return
        log_channel = guild.get_channel(log_channel_id)
        
        if log_channel:
            now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            embed = discord.Embed(
                title="Nouvelle Confession",
                color=discord.Color.purple(),
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
            embed.add_field(name="Utilisateur", value=user.mention, inline=False)
            embed.add_field(name="Confession", value=confession_message, inline=False)
            embed.add_field(name="Date", value=now, inline=False)
            await log_channel.send(embed=embed)
        else:
            print(f"[ERROR] Log channel avec ID {log_channel_id} non trouvé dans guild '{guild.name}'")
            
    except Exception as e:
        print(f"[ERROR] Erreur lors du log de confession: {e}")

async def log_all_commands(interaction_or_ctx):
    """Log automatiquement toutes les commandes utilisées (slash ou préfixées)"""
    try:
        # Détection du type d'objet
        if hasattr(interaction_or_ctx, 'command') and hasattr(interaction_or_ctx, 'user'):
            # Slash command (discord.Interaction)
            interaction = interaction_or_ctx
            guild = interaction.guild
            user = interaction.user
            channel = interaction.channel
            command_name = interaction.command.name if interaction.command else "commande_inconnue"
            is_slash = True
        elif hasattr(interaction_or_ctx, 'command') and hasattr(interaction_or_ctx, 'author'):
            # Commande préfixée (commands.Context)
            ctx = interaction_or_ctx
            guild = ctx.guild
            user = ctx.author
            channel = ctx.channel
            command_name = ctx.command.name if ctx.command else "commande_inconnue"
            is_slash = False
        else:
            print("[ERROR] log_all_commands: Type d'objet non supporté")
            return

        if not guild:
            return  # Pas de guild, on ne log pas

        # Récupérer l'ID du canal de log
        command_log_id = get_env_var('COMMAND_LOG_CHANNEL_ID', required=False)
        log_channel_id = None
        if command_log_id is not None:
            cleaned = clean_id(command_log_id)
            if cleaned is not None and cleaned.isdigit():
                log_channel_id = int(cleaned)
            else:
                print(f"[ERROR] log_all_commands: ID de salon invalide: {command_log_id}")
                return
        else:
            fallback_log_id = get_env_var('LOG_CHANNEL_ID', required=True)
            if fallback_log_id is not None:
                cleaned = clean_id(fallback_log_id)
                if cleaned is not None and cleaned.isdigit():
                    log_channel_id = int(cleaned)
                else:
                    print(f"[ERROR] log_all_commands: ID de fallback invalide: {fallback_log_id}")
                    return
            else:
                print("[ERROR] log_all_commands: Aucun ID de salon de log défini")
                return
        if log_channel_id is None:
            print("[ERROR] log_all_commands: log_channel_id est None")
            return
        log_channel = guild.get_channel(log_channel_id)

        if log_channel:
            now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            # Déterminer la couleur selon le type de commande
            if command_name in ["warn", "kick", "ban", "mute", "tempban", "tempmute", "clear", "unmute"]:
                color = discord.Color.red()
                title = "🛡️ Action Administrative"
                category = "Modération"
            elif command_name in ["blague", "anime", "confess", "ping", "games"]:
                color = discord.Color.green()
                title = "🎮 Commande Fun"
                category = "Divertissement"
            elif command_name in ["reload", "shutdown", "status", "help"]:
                color = discord.Color.blue()
                title = "⚙️ Commande Système"
                category = "Système"
            else:
                color = discord.Color.light_grey()
                title = "📝 Commande Utilisée"
                category = "Autre"

            embed = discord.Embed(
                title=title,
                description=f'{user.mention} a utilisé la commande **/{command_name}**' if is_slash else f'{user.mention} a utilisé la commande `{command_name}`',
                color=color,
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=user.avatar.url if hasattr(user, 'avatar') and user.avatar else getattr(user, 'default_avatar', None))

            # Ajouter des informations sur la commande
            embed.add_field(name="📝 Commande", value=f"`/{command_name}`" if is_slash else f"`{command_name}`", inline=True)
            embed.add_field(name="🏷️ Catégorie", value=category, inline=True)
            embed.add_field(name="👤 Utilisateur", value=user.mention, inline=True)

            # Ajouter des informations sur les arguments si disponibles
            if is_slash and hasattr(interaction, 'data') and interaction.data and 'options' in interaction.data:
                options = interaction.data['options']
                if options:
                    args_info = []
                    for option in options:
                        if 'value' in option:
                            value = str(option['value'])
                            if len(value) > 50:
                                value = value[:47] + "..."
                            args_info.append(f"`{option['name']}: {value}`")
                    if args_info:
                        embed.add_field(name="📋 Arguments", value="\n".join(args_info), inline=False)
            elif not is_slash and hasattr(interaction_or_ctx, 'kwargs'):
                args_info = [f"`{k}: {v}`" for k, v in interaction_or_ctx.kwargs.items()]
                if args_info:
                    embed.add_field(name="📋 Arguments", value="\n".join(args_info), inline=False)

            embed.add_field(name="📅 Date", value=now, inline=False)
            embed.add_field(name="📍 Canal", value=channel.mention, inline=True)

            # Ajouter des informations sur les permissions de l'utilisateur
            if hasattr(user, 'guild_permissions'):
                permissions = []
                if user.guild_permissions.administrator:
                    permissions.append("👑 Admin")
                if user.guild_permissions.manage_messages:
                    permissions.append("🛡️ Modérateur")
                if user.guild_permissions.manage_roles:
                    permissions.append("🔑 Gestionnaire Rôles")
                if permissions:
                    embed.add_field(name="🔐 Permissions", value=", ".join(permissions), inline=True)

            await log_channel.send(embed=embed)
    except Exception as e:
        print(f"[ERROR] Erreur lors du log automatique de commande: {e}")

async def log_command_disabled_attempt(interaction, command_name, arguments=None, log_channel_id=None):
    """Log toute tentative d'utilisation d'une commande désactivée"""
    try:
        guild = interaction.guild
        if arguments is None:
            arguments = {}
        if log_channel_id is None:
            command_log_id = get_env_var('COMMAND_LOG_CHANNEL_ID', required=False)
            cleaned = clean_id(command_log_id)
            if cleaned and cleaned.isdigit():
                log_channel_id = int(cleaned)
            else:
                log_channel_id = None
        if log_channel_id is None:
            fallback = get_env_var('LOG_CHANNEL_ID', required=True)
            cleaned = clean_id(fallback)
            if cleaned and cleaned.isdigit():
                log_channel_id = int(cleaned)
            else:
                print(f"[ERROR] log_command_disabled_attempt: ID de salon invalide")
                return
        log_channel = guild.get_channel(log_channel_id)
        if log_channel:
            now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            embed = discord.Embed(
                title="❌ Tentative d'utilisation d'une commande désactivée",
                description=f"{interaction.user.mention} a tenté d'utiliser la commande **/{command_name}**",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Commande", value=f"`/{command_name}`", inline=True)
            embed.add_field(name="Utilisateur", value=interaction.user.mention, inline=True)
            embed.add_field(name="Salon", value=interaction.channel.mention, inline=True)
            if arguments:
                args_str = "\n".join([f"`{k}`: {v}" for k, v in arguments.items()])
                embed.add_field(name="Arguments", value=args_str, inline=False)
            embed.add_field(name="Date", value=now, inline=False)
            await log_channel.send(embed=embed)
        else:
            print(f"[ERROR] Log channel avec ID {log_channel_id} non trouvé dans guild '{guild.name}'")
    except Exception as e:
        print(f"[ERROR] Erreur lors du log de tentative de commande désactivée: {e}")

# Set global pour éviter le double log
ALREADY_LOGGED_INTERACTIONS = weakref.WeakSet()

def log_command():
    """
    Décorateur pour logger automatiquement toutes les commandes.
    
    Usage:
        @app_commands.command()
        @log_command()
        async def ma_commande(self, interaction):
            # code de la commande
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, interaction_or_ctx, *args, **kwargs):
            # Exécuter la commande d'abord
            result = await func(self, interaction_or_ctx, *args, **kwargs)
            
            # Logger après l'exécution réussie (un seul log)
            try:
                await log_all_commands(interaction_or_ctx)
            except Exception as log_error:
                print(f"[ERROR] Erreur lors du log de la commande {func.__name__}: {log_error}")
            
            return result
        return wrapper
    return decorator