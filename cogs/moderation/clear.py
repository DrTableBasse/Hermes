import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from utils.command_manager import command_enabled
from utils.logging import log_command

class ClearCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="clear", description="Supprimer un nombre spécifié de messages")
    @command_enabled(guild_specific=True)
    @log_command()
    async def clear(self, interaction: discord.Interaction, amount: int):
        # Vérifier que l'utilisateur est bien un membre du serveur
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("Vous n'avez pas les permissions nécessaires pour utiliser cette commande.", ephemeral=True)
            return  # Ajout de return pour clarifier le flow

        # Vérifier que le salon est bien un salon textuel
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ Cette commande ne peut être utilisée que dans un salon textuel.", ephemeral=True)
            return

        # Limiter le nombre de messages à supprimer (max 100 par requête)
        if amount > 100:
            await interaction.response.send_message("❌ Le nombre maximum de messages à supprimer est 100.", ephemeral=True)
            return

        if amount < 1:
            await interaction.response.send_message("❌ Le nombre de messages doit être supérieur à 0.", ephemeral=True)
            return

        try:
            # Différer la réponse pour éviter l'expiration de l'interaction
            await interaction.response.defer(ephemeral=True)
            
            # Récupérer les messages récents
            messages = []
            async for message in interaction.channel.history(limit=amount):
                # Vérifier que le message n'est pas plus vieux que 14 jours
                message_age = (datetime.utcnow() - message.created_at.replace(tzinfo=None)).days
                if message_age > 14:
                    break
                messages.append(message)
            
            if not messages:
                await interaction.followup.send("❌ Aucun message récent trouvé à supprimer (les messages doivent être de moins de 14 jours).", ephemeral=True)
                return
            
            # Supprimer les messages en masse
            await interaction.channel.delete_messages(messages)
            
            # Envoyer la réponse via followup
            await interaction.followup.send(f"✅ {len(messages)} messages ont été supprimés avec succès.", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("❌ Je n'ai pas les permissions nécessaires pour supprimer des messages dans ce canal.", ephemeral=True)
        except discord.HTTPException as e:
            if e.status == 400:
                await interaction.followup.send("❌ Impossible de supprimer certains messages (trop anciens ou déjà supprimés).", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Erreur HTTP lors de la suppression des messages", ephemeral=True)
        except Exception as e:
            try:
                await interaction.followup.send(f"❌ Une erreur est survenue lors de la suppression des messages", ephemeral=True)
            except:
                print(f"Erreur dans la commande clear")

async def setup(bot):
    await bot.add_cog(ClearCog(bot))
