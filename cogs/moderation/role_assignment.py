import discord
from discord.ext import commands, tasks
import os
from utils.logging import log_voice_event
from utils.database import voice_manager
from utils.constants import ROLE_BATMAN, VOICE_HOURS_FOR_ROLE
from discord import app_commands
from datetime import datetime
from utils.command_manager import command_enabled
from utils.logging import log_command
import logging

logger = logging.getLogger(__name__)

class RoleAssignmentCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.role_batman = ROLE_BATMAN
        self.voice_hours_for_role = VOICE_HOURS_FOR_ROLE
        self.check_voice_times.start()

    def cog_unload(self):
        self.check_voice_times.cancel()

    @tasks.loop(hours=1)
    async def check_voice_times(self):
        try:
            # Utiliser le gestionnaire PostgreSQL
            users = await voice_manager.get_top_voice_users(100)  # Récupérer plus d'utilisateurs pour filtrer
            
            # Filtrer les utilisateurs qui ont plus d'heures que la limite configurée
            eligible_users = [user for user in users if user['total_time'] >= self.voice_hours_for_role * 3600]
            
            if not eligible_users:
                print(f"Aucun utilisateur éligible pour le rôle {ROLE_BATMAN} trouvé.")
                return

            guild_id = os.getenv('GUILD_ID')
            if not guild_id:
                print("❌ Variable d'environnement GUILD_ID manquante dans le fichier .env")
                return
                
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                print("❌ Serveur non trouvé.")
                return

            role = discord.utils.get(guild.roles, name=ROLE_BATMAN)
            if not role:
                print(f"Rôle '{ROLE_BATMAN}' non trouvé.")
                return

            for user_data in eligible_users:
                user_id = user_data['user_id']
                member = guild.get_member(user_id)
                
                if member and role not in member.roles:
                    try:
                        await member.add_roles(role)
                        print(f"Rôle {ROLE_BATMAN} attribué à {member.display_name} ({user_id})")
                        
                        # Log l'événement
                        await log_voice_event(
                            self.bot,
                            "role_assigned",
                            user_id,
                            f"Rôle {ROLE_BATMAN} attribué automatiquement"
                        )
                    except discord.Forbidden:
                        print(f"Impossible d'attribuer le rôle {ROLE_BATMAN} à {member.display_name} - permissions insuffisantes")
                    except Exception as e:
                        print(f"Erreur lors de l'attribution du rôle {ROLE_BATMAN} à {member.display_name}: {e}")

        except Exception as e:
            print(f"[ERROR] Erreur lors de la vérification des temps vocaux: {e}")

    @check_voice_times.before_loop
    async def before_check_voice_times(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="role", description="Attribuer un rôle à un utilisateur")
    @command_enabled(guild_specific=True)
    async def role(self, interaction: discord.Interaction, user: discord.Member, role_name: str):
        try:
            # Vérifier les permissions
            if not interaction.user.guild_permissions.manage_roles:
                await interaction.response.send_message("❌ Vous n'avez pas la permission de gérer les rôles.", ephemeral=True)
                return

            # Trouver le rôle
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if not role:
                await interaction.response.send_message(f"❌ Le rôle '{role_name}' n'existe pas.", ephemeral=True)
                return

            # Vérifier si l'utilisateur a déjà le rôle
            if role in user.roles:
                await interaction.response.send_message(f"❌ {user.mention} a déjà le rôle {role.mention}.", ephemeral=True)
                return

            # Attribuer le rôle
            await user.add_roles(role)
            await interaction.response.send_message(f"✅ Le rôle {role.mention} a été attribué à {user.mention}.", ephemeral=True)

        except discord.Forbidden:
            await interaction.response.send_message("❌ Je n'ai pas la permission d'attribuer ce rôle.", ephemeral=True)
        except Exception as e:
            logger.error(f"[role] Erreur lors de l'exécution: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"❌ Une erreur s'est produite : {str(e)}", ephemeral=True)
                else:
                    await interaction.followup.send(f"❌ Une erreur s'est produite : {str(e)}", ephemeral=True)
            except Exception as send_err:
                logger.error(f"[role] Impossible d'envoyer le message d'erreur : {send_err}")

async def setup(bot):
    await bot.add_cog(RoleAssignmentCog(bot))
