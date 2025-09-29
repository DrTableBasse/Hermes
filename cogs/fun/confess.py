import discord
from discord import app_commands
from discord.ext import commands
from utils.logging import log_confession, log_command
from utils.command_manager import CommandStatusManager, command_enabled
import logging
import os
import re

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
        
        # Regex pour détecter les URLs/hyperliens
        url_patterns = [
            r'https?://[^\s]+',  # http/https URLs
            r'www\.[^\s]+',      # www URLs
            r'[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',  # domaines simples
            r'ftp://[^\s]+',     # ftp URLs
        ]
        
        for pattern in url_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return False, "Les liens ne sont pas autorisés dans les confessions"
        
        # Détecter les tentatives d'échappement de code
        dangerous_patterns = [
            r'<[^>]*>',          # balises HTML/XML
            r'```[\s\S]*?```',   # blocs de code
            r'`[^`]+`',          # code inline
            r'@(everyone|here)', # mentions
            r'<@[!&]?\d+>',      # mentions d'utilisateurs
            r'<#[^\s>]+>',       # mentions de channels
            r'<@&[^\s>]+>',      # mentions de rôles
            r'\\[\\`*_~|]',      # échappements markdown
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return False, "Formatage et mentions non autorisés"
        
        # Nettoyer le message (supprimer les caractères de contrôle)
        cleaned_message = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', message)
        cleaned_message = cleaned_message.strip()
        
        return True, cleaned_message

    @app_commands.command(name="confession", description="Faites une confession anonyme")
    @command_enabled(guild_specific=True)
    @log_command()
    async def confession(self, interaction: discord.Interaction, message: str):
        command_name = interaction.command.name
        is_enabled = await CommandStatusManager.get_command_status(command_name, guild_id=interaction.guild_id, use_cache=False)
        logger.info(f"[{command_name}] Appel de la commande. Statut: {'activée' if is_enabled else 'désactivée'}")
        if not is_enabled:
            logger.warning(f"[{command_name}] Commande désactivée, accès refusé à {interaction.user} (id={interaction.user.id})")
            await interaction.response.send_message(
                f"❌ La commande `/{command_name}` est actuellement désactivée.",
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
            
            # Déterminer l'ID du salon depuis les variables d'environnement si disponible
            env_confession_id = os.getenv('CONFESSION_CHANNEL_ID')
            log_channel_id = None
            if env_confession_id:
                cleaned = env_confession_id.split('#')[0].split()[0].strip()
                if cleaned.isdigit():
                    log_channel_id = int(cleaned)

            # Log métier : si log_channel_id est None, log_confession appliquera ses fallbacks (.env CONFESSION_LOG_CHANNEL_ID puis LOG_CHANNEL_ID)
            await log_confession(interaction.user, cleaned_message, log_channel_id=log_channel_id)
            await interaction.response.send_message(
                "✅ Votre confession a bien été envoyée anonymement !",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"[{command_name}] Erreur lors de l'envoi de la confession anonyme")
            await interaction.response.send_message(
                "❌ Une erreur est survenue lors de l'envoi de la confession. Veuillez réessayer plus tard.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ConfessionCog(bot))
