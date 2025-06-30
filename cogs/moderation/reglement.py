import discord
from discord import app_commands
from discord.ext import commands
import json
import asyncio
from datetime import datetime
from utils.command_manager import command_enabled

class ReglementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.disabled_commands_file = "disabled_commands.json"
        self.disabled_commands = self.load_disabled_commands()

    def load_disabled_commands(self):
        """Charge les commandes désactivées depuis un fichier JSON."""
        try:
            with open(self.disabled_commands_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_disabled_commands(self):
        """Sauvegarde les commandes désactivées dans un fichier JSON."""
        with open(self.disabled_commands_file, "w") as f:
            json.dump(self.disabled_commands, f, indent=4)

    @app_commands.command(name="reglement", description="Afficher le règlement du serveur")
    @command_enabled(guild_specific=True)
    async def reglement(self, interaction: discord.Interaction):
        """Vérifie si la commande 'reglement' est désactivée dans le fichier et l'exécute si elle est activée."""
        if "reglement" in self.disabled_commands:
            embed = discord.Embed(
                title="Erreur",
                description="La commande 'reglement' est actuellement désactivée.",
                color=discord.Color.red()  # Couleur rouge pour l'embed
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Répondre à l'interaction avec un message initial
        await interaction.response.send_message("Voici le règlement du serveur. Je vais vous envoyer les règles en plusieurs messages.")

        regles = [
            {
                "title": "1- Respect mutuel et envers la modération du serveur",
                "description": "Le respect d'autrui est obligatoire. Aucun jugement, harcèlement ou chasse aux sorcières, quel que soit le moyen utilisé, ne sera toléré, sous peine de sanctions par la modération."
            }
        ]

        # Envoyer chaque règle comme un message distinct
        for regle in regles:
            embed = discord.Embed(title=regle["title"], description=regle["description"], color=0x00ff00)
            await interaction.channel.send(embed=embed)
            await asyncio.sleep(1)  # Ajustez la durée du délai selon vos besoins

async def setup(bot):
    await bot.add_cog(ReglementCog(bot))
