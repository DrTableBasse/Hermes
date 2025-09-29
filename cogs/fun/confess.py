import discord
from discord import app_commands
from discord.ext import commands
from utils.logging import log_confession, log_command
from utils.command_manager import CommandStatusManager, command_enabled
import logging
import os
import re
from config import CONFESSION_CHANNEL_ID

logger = logging.getLogger("fun_commands")

class ConfessionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    def validate_confession_message(self, message: str) -> tuple[bool, str]:
        """
        Valide et nettoie un message de confession pour éviter les hyperliens et injections.
        Retourne (is_valid, cleaned_message)
        """
        # Limite de longueur
        if len(message) > 2000:
            return False, "Le message est trop long (maximum 2000 caractères)"
        
        if len(message.strip()) < 3:
            return False, "Le message doit contenir au moins 3 caractères"
        
        # Vérifier les caractères dangereux et d'injection
        dangerous_chars = ['\x00', '\x01', '\x02', '\x03', '\x04', '\x05', '\x06', '\x07', '\x08', '\x0b', '\x0c', '\x0e', '\x0f', '\x10', '\x11', '\x12', '\x13', '\x14', '\x15', '\x16', '\x17', '\x18', '\x19', '\x1a', '\x1b', '\x1c', '\x1d', '\x1e', '\x1f', '\x7f', '\x80', '\x81', '\x82', '\x83', '\x84', '\x85', '\x86', '\x87', '\x88', '\x89', '\x8a', '\x8b', '\x8c', '\x8d', '\x8e', '\x8f', '\x90', '\x91', '\x92', '\x93', '\x94', '\x95', '\x96', '\x97', '\x98', '\x99', '\x9a', '\x9b', '\x9c', '\x9d', '\x9e', '\x9f']
        
        for char in dangerous_chars:
            if char in message:
                return False, "Caractères non autorisés détectés"
        
        # Regex améliorées pour détecter les URLs/hyperliens (plus robustes)
        url_patterns = [
            r'https?://[^\s<>"\']+',           # http/https URLs
            r'ftp://[^\s<>"\']+',              # ftp URLs
            r'www\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*[^\s<>"\']*',  # www URLs
            r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+\.[a-zA-Z]{2,}[^\s<>"\']*',  # domaines avec TLD
            r'mailto:[^\s<>"\']+',             # mailto links
            r'tel:[^\s<>"\']+',                # tel links
        ]
        
        for pattern in url_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return False, "Les liens ne sont pas autorisés dans les confessions"
        
        # Détecter les tentatives d'échappement de code et d'injection (améliorées)
        dangerous_patterns = [
            r'<[^>]*>',                        # balises HTML/XML
            r'```[\s\S]*?```',                 # blocs de code
            r'`[^`\n]+`',                      # code inline (amélioré)
            r'@(everyone|here)',               # mentions spéciales
            r'<@[!&]?\d{17,19}>',             # mentions d'utilisateurs (IDs Discord)
            r'<#[^\s>]+>',                     # mentions de channels
            r'<@&[^\s>]+>',                    # mentions de rôles
            r'<a:[^\s>]+>',                    # emojis animés
            r'<:[^\s>]+:\d+>',                 # emojis personnalisés
            r'\\[\\`*_~|\[\](){}]',           # échappements markdown
            r'[#*_~|]{2,}',                    # multiples caractères de formatage
            r'javascript:',                    # javascript: protocol
            r'data:',                          # data: protocol
            r'vbscript:',                      # vbscript: protocol
            r'<script[^>]*>[\s\S]*?</script>', # script tags
            r'<iframe[^>]*>[\s\S]*?</iframe>', # iframe tags
            r'<object[^>]*>[\s\S]*?</object>', # object tags
            r'<embed[^>]*>',                   # embed tags
            r'<link[^>]*>',                    # link tags
            r'<meta[^>]*>',                    # meta tags
            r'<style[^>]*>[\s\S]*?</style>',   # style tags
            r'<form[^>]*>[\s\S]*?</form>',     # form tags
            r'<input[^>]*>',                   # input tags
            r'<textarea[^>]*>[\s\S]*?</textarea>', # textarea tags
            r'<select[^>]*>[\s\S]*?</select>', # select tags
            r'<button[^>]*>[\s\S]*?</button>', # button tags
            r'<marquee[^>]*>[\s\S]*?</marquee>', # marquee tags
            r'<blink[^>]*>[\s\S]*?</blink>',   # blink tags
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return False, "Formatage, mentions ou contenu non autorisé détecté"
        
        # Détecter les tentatives d'injection SQL basiques
        sql_patterns = [
            r'(?i)(union|select|insert|update|delete|drop|create|alter|exec|execute|script|javascript)',
            r'(?i)(or|and)\s+\d+\s*=\s*\d+',
            r'(?i)(or|and)\s+\'\s*=\s*\'',
            r'(?i)(or|and)\s+"\s*=\s*"',
            r'(?i);\s*(drop|delete|insert|update|create|alter)',
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, message):
                return False, "Contenu suspect détecté"
        
        # Nettoyer le message (supprimer les caractères de contrôle et normaliser)
        cleaned_message = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', message)
        cleaned_message = re.sub(r'\s+', ' ', cleaned_message)  # Normaliser les espaces
        cleaned_message = cleaned_message.strip()
        
        # Vérifier que le message nettoyé n'est pas vide
        if not cleaned_message:
            return False, "Le message est vide après nettoyage"
        
        return True, cleaned_message

    @app_commands.command(name="confession", description="Faites une confession anonyme")
    @command_enabled(guild_specific=True)
    @log_command()
    async def confession(self, interaction: discord.Interaction, message: str):
        command_name = interaction.command.name
        is_enabled = await CommandStatusManager.get_command_status(command_name, guild_id=interaction.guild_id, use_cache=False)
        logger.info(f"[{command_name}] Appel de la commande par {interaction.user} (id={interaction.user.id}). Statut: {'activée' if is_enabled else 'désactivée'}")
        
        if not is_enabled:
            logger.warning(f"[{command_name}] Commande désactivée, accès refusé à {interaction.user} (id={interaction.user.id})")
            await interaction.response.send_message(
                f"❌ La commande `/{command_name}` est actuellement désactivée.",
                ephemeral=True
            )
            return
        
        # Validation préliminaire de l'utilisateur et du serveur
        if not interaction.user or not interaction.guild:
            logger.error(f"[{command_name}] Interaction invalide - utilisateur ou serveur manquant")
            await interaction.response.send_message(
                "❌ Erreur de contexte. Veuillez réessayer.",
                ephemeral=True
            )
            return
        
        # Vérifier que l'utilisateur n'est pas un bot
        if interaction.user.bot:
            logger.warning(f"[{command_name}] Tentative d'utilisation par un bot: {interaction.user}")
            await interaction.response.send_message(
                "❌ Les bots ne peuvent pas utiliser cette commande.",
                ephemeral=True
            )
            return
        
        try:
            # Validation et nettoyage du message
            is_valid, cleaned_message = self.validate_confession_message(message)
            if not is_valid:
                await interaction.response.send_message(
                    f"❌ {cleaned_message}",
                    ephemeral=True
                )
                return
            
            # Déterminer l'ID du salon de confessions depuis la configuration
            confession_channel_id = CONFESSION_CHANNEL_ID
            logger.info(f"[{command_name}] Canal de confession configuré: {confession_channel_id}")
            
            # Vérifier que le canal de confession est configuré
            if not confession_channel_id or confession_channel_id == 0:
                await interaction.response.send_message(
                    "❌ Le salon de confession n'est pas configuré. Contactez un administrateur.",
                    ephemeral=True
                )
                logger.error(f"[{command_name}] CONFESSION_CHANNEL_ID non configuré ou invalide: {confession_channel_id}")
                return

            # Récupérer le salon et envoyer la confession anonymisée
            guild = interaction.guild
            if not guild:
                await interaction.response.send_message(
                    "❌ Erreur de récupération du serveur.",
                    ephemeral=True
                )
                logger.error(f"[{command_name}] Guild non disponible pour l'utilisateur {interaction.user.id}")
                return

            # Essayer de récupérer le canal
            logger.info(f"[{command_name}] Tentative de récupération du canal {confession_channel_id} depuis le serveur {guild.name} (ID: {guild.id})")
            channel = guild.get_channel(confession_channel_id)
            
            if channel is None:
                logger.warning(f"[{command_name}] Canal {confession_channel_id} non trouvé dans le cache du serveur, tentative de fetch...")
                try:
                    channel = await self.bot.fetch_channel(confession_channel_id)
                    logger.info(f"[{command_name}] Canal fetché avec succès: {channel.name if channel else 'None'}")
                    
                    # Vérifier que le canal appartient bien au serveur
                    if channel and channel.guild and channel.guild.id != guild.id:
                        logger.error(f"[{command_name}] Canal {confession_channel_id} appartient à un autre serveur ({channel.guild.id}) que le serveur actuel ({guild.id})")
                        channel = None
                    elif channel:
                        logger.info(f"[{command_name}] Canal validé: {channel.name} dans le serveur {channel.guild.name}")
                        
                except Exception as e:
                    channel = None
                    logger.error(f"[{command_name}] Erreur lors de la récupération du canal {confession_channel_id}: {e}")

            if channel is None:
                await interaction.response.send_message(
                    "❌ Salon de confession introuvable ou inaccessible. Vérifiez la configuration.",
                    ephemeral=True
                )
                logger.error(f"[{command_name}] Canal de confession {confession_channel_id} introuvable ou inaccessible")
                return
            
            logger.info(f"[{command_name}] Canal de confession trouvé: {channel.name} (ID: {channel.id})")

            # Vérifier les permissions du bot sur le canal
            bot_permissions = channel.permissions_for(interaction.guild.me)
            logger.info(f"[{command_name}] Permissions du bot sur le canal {channel.name}: Send={bot_permissions.send_messages}, Embed={bot_permissions.embed_links}")
            
            if not bot_permissions.send_messages or not bot_permissions.embed_links:
                await interaction.response.send_message(
                    "❌ Le bot n'a pas les permissions nécessaires pour envoyer des messages dans le salon de confession.",
                    ephemeral=True
                )
                logger.error(f"[{command_name}] Permissions insuffisantes sur le canal {confession_channel_id}. Send: {bot_permissions.send_messages}, Embed: {bot_permissions.embed_links}")
                return

            # Créer et envoyer l'embed de confession
            embed = discord.Embed(
                title="💭 Confession anonyme",
                description=cleaned_message,
                color=discord.Color.purple(),
                timestamp=interaction.created_at
            )
            embed.set_footer(text="Confession anonyme • Utilisez /confession pour partager la vôtre")
            
            # Répondre d'abord à l'interaction pour éviter le timeout
            await interaction.response.send_message(
                "✅ Votre confession a été envoyée anonymement ! 🙏",
                ephemeral=True
            )

            try:
                await channel.send(embed=embed)
                logger.info(f"[{command_name}] Confession envoyée avec succès dans le canal {confession_channel_id} par l'utilisateur {interaction.user.id}")
            except discord.Forbidden:
                # Envoyer un message de suivi si l'envoi échoue
                await interaction.followup.send(
                    "❌ Le bot n'a pas les permissions nécessaires pour envoyer des messages dans le salon de confession.",
                    ephemeral=True
                )
                logger.error(f"[{command_name}] Permission refusée lors de l'envoi dans le canal {confession_channel_id}")
                return
            except discord.HTTPException as e:
                # Envoyer un message de suivi si l'envoi échoue
                await interaction.followup.send(
                    "❌ Erreur lors de l'envoi de la confession. Veuillez réessayer.",
                    ephemeral=True
                )
                logger.error(f"[{command_name}] Erreur HTTP lors de l'envoi de la confession: {e}")
                return

            # Log métier séparé (utilise CONFESSION_LOG_CHANNEL_ID ou LOG_CHANNEL_ID via fallback interne)
            try:
                await log_confession(interaction.user, cleaned_message, log_channel_id=None)
                logger.info(f"[{command_name}] Log de confession créé avec succès pour l'utilisateur {interaction.user.id}")
            except Exception as e:
                logger.warning(f"[{command_name}] Échec de la création du log de confession pour l'utilisateur {interaction.user.id}: {e}")
                # Ne pas faire échouer la commande si le log échoue
                
        except Exception as e:
            logger.error(f"[{command_name}] Erreur inattendue lors de l'envoi de la confession par l'utilisateur {interaction.user.id}: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "❌ Une erreur inattendue est survenue. Veuillez réessayer plus tard.",
                    ephemeral=True
                )
            except:
                # Si on ne peut même pas répondre, c'est un problème sérieux
                logger.critical(f"[{command_name}] Impossible de répondre à l'interaction après erreur pour l'utilisateur {interaction.user.id}")

async def setup(bot):
    await bot.add_cog(ConfessionCog(bot))
