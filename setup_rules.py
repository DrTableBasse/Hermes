"""
Script ponctuel — publie les règles du serveur sous forme d'embeds verts
dans le salon règlement.

Usage :
    python setup_rules.py
"""

import asyncio
import os
import sys
from datetime import datetime

import discord
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
RULES_CHANNEL_ID = 1273011273113669632

C_GREEN = 0x57F287
C_GOLD  = 0xF5A623
FOOTER  = "Hermes · SaucisseLand"


def _embed(title: str, description: str, color: int) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now())
    e.set_footer(text=FOOTER)
    return e


HEADER = _embed(
    title="📜  Règlement du serveur",
    description=(
        "Bienvenue sur **SaucisseLand** !\n"
        "Merci de lire et respecter les règles ci-dessous.\n"
        "Toute infraction peut entraîner des sanctions.\n​"
    ),
    color=C_GOLD,
)

RULES = [
    _embed(
        title="Règle 1 — Respect mutuel",
        description=(
            "Le respect d'autrui est obligatoire. Aucun jugement, harcèlement ou chasse aux "
            "sorcières, quel que soit le moyen utilisé, ne sera toléré, sous peine de sanctions "
            "par la modération."
        ),
        color=C_GREEN,
    ),
    _embed(
        title="Règle 2 — Tickets, avertissements et sanctions",
        description=(
            "En cas de problème, contactez la modération via la commande **!newticket** en "
            "précisant la raison dans l'intitulé.\n\n"
            "Tout avertissement et toute sanction doivent rester **privés**. "
            "Toute décision doit être respectée, sous peine de sanctions plus graves."
        ),
        color=C_GREEN,
    ),
    _embed(
        title="Règle 3 — Salons de discussion et vocaux",
        description=(
            "Respectez l'intitulé de chaque salon. Tout contenu **NSFW** sera supprimé et "
            "sanctionné.\n\n"
            "Ne coupez pas la parole aux autres membres et faites preuve de politesse "
            "en utilisant *Bonjour* et *Au revoir*."
        ),
        color=C_GREEN,
    ),
    _embed(
        title="Règle 4 — Français correct et compréhensible",
        description=(
            "Le langage SMS à outrance est interdit. Nous vous demandons d'utiliser des termes "
            "français et de faire attention à votre orthographe."
        ),
        color=C_GREEN,
    ),
    _embed(
        title="Règle 5 — Application de la loi française",
        description=(
            "Le piratage, le reverse engineering, le hacking ou tout autre sujet illégal sont "
            "interdits. Les sujets borderline — dont la légalité ou l'usage ne sont pas clairement "
            "définis — sont également interdits.\n\n"
            "Si un modérateur tombe sur ce genre de discussion, des **sanctions graves** seront appliquées."
        ),
        color=C_GREEN,
    ),
    _embed(
        title="Règle 6 — Ce qui ne concerne pas le serveur",
        description=(
            "Les dramas d'autres serveurs ne nous concernent en rien. Laissez le serveur et ses "
            "membres en dehors de cela.\n\n"
            "Nous ne sommes pas psychologues : ne donnez aucun conseil sur la vie amoureuse ou "
            "privée d'autrui. Pour les sujets sensibles, utilisez un ticket privé."
        ),
        color=C_GREEN,
    ),
    _embed(
        title="Règle 7 — Pas de publicité",
        description=(
            "La publicité pour d'autres serveurs, produits ou services à des fins lucratives "
            "(chaînes YouTube, boutiques, etc.) est interdite.\n\n"
            "Les annonces concernant du **développement pur** sont autorisées."
        ),
        color=C_GREEN,
    ),
    _embed(
        title="Règle 8 — Ne pas abuser des mentions (@)",
        description=(
            "Toute mention inutile et/ou abusive est interdite, sous peine de **mute sans "
            "avertissement**."
        ),
        color=C_GREEN,
    ),
]


class RulesClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        super().__init__(intents=intents)

    async def on_ready(self):
        print(f"✅ Connecté en tant que {self.user}", flush=True)
        try:
            await self.post_rules()
        except Exception as e:
            print(f"❌ Erreur inattendue : {e}", flush=True)
            import traceback; traceback.print_exc()
        finally:
            await self.close()

    async def post_rules(self):
        print(f"🔍 Récupération du salon {RULES_CHANNEL_ID}...", flush=True)
        try:
            channel = await self.fetch_channel(RULES_CHANNEL_ID)
            print(f"✅ Salon trouvé : #{channel.name}", flush=True)
        except discord.NotFound:
            print(f"❌ Salon {RULES_CHANNEL_ID} introuvable", flush=True)
            return
        except discord.Forbidden:
            print(f"❌ Pas la permission d'accéder au salon", flush=True)
            return
        except Exception as e:
            print(f"❌ Erreur fetch_channel : {e}", flush=True)
            return

        await channel.send(embed=HEADER)
        print("📌 Header envoyé", flush=True)

        for i, embed in enumerate(RULES, start=1):
            await channel.send(embed=embed)
            print(f"   ✅ Règle {i}/8 envoyée", flush=True)
            await asyncio.sleep(0.5)

        print("\n🎉 Règlement publié !", flush=True)


async def main():
    if not DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN manquant dans .env")
        sys.exit(1)

    client = RulesClient()
    await client.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
