"""
Script de test — inspecte le message carl.gg bump pour identifier comment récupérer l'auteur.
Usage: python test_carlgg_bump.py
"""
import os
import asyncio
import discord
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID      = 768885611091984384
CHANNEL_ID    = 1068608173310754886
MESSAGE_ID    = 1517136482576367658

CARLGG_BOT_ID = 235148962103951360


def dump_message(msg: discord.Message):
    print(f"\n{'='*60}")
    print(f"Message ID   : {msg.id}")
    print(f"Author       : {msg.author} (ID={msg.author.id})")
    print(f"Content      : {msg.content!r}")
    print(f"Type         : {msg.type}")

    # interaction_metadata (discord.py 2.5+)
    meta = getattr(msg, 'interaction_metadata', None)
    print(f"\n--- interaction_metadata ---")
    if meta is None:
        print("  None")
    else:
        print(f"  type: {type(meta)}")
        for attr in ('user', 'user_id', 'id', 'type', 'name'):
            val = getattr(meta, attr, '(absent)')
            print(f"  .{attr} = {val!r}")

    # message.interaction (deprecated)
    intr = getattr(msg, 'interaction', None)
    print(f"\n--- message.interaction (deprecated) ---")
    if intr is None:
        print("  None")
    else:
        print(f"  type: {type(intr)}")
        for attr in ('user', 'id', 'type', 'name'):
            val = getattr(intr, attr, '(absent)')
            print(f"  .{attr} = {val!r}")

    # Embeds
    print(f"\n--- Embeds ({len(msg.embeds)}) ---")
    for i, embed in enumerate(msg.embeds):
        print(f"  Embed #{i}: title={embed.title!r} desc={embed.description!r}")
        for f in embed.fields:
            print(f"    field: {f.name!r} = {f.value!r}")

    # Components (buttons, etc.)
    components = getattr(msg, 'components', [])
    print(f"\n--- Components ({len(components)}) ---")
    for c in components:
        print(f"  {c}")

    # Raw message flags
    print(f"\n--- Flags ---")
    print(f"  {msg.flags}")

    # Mentions
    print(f"\n--- Mentions ({len(msg.mentions)}) ---")
    for m in msg.mentions:
        print(f"  {m} (ID={m.id})")

    print('='*60)


class TestClient(discord.Client):
    async def on_ready(self):
        print(f"Connecté en tant que {self.user}")

        channel = self.get_channel(CHANNEL_ID)
        if channel is None:
            guild = self.get_guild(GUILD_ID)
            channel = guild.get_channel(CHANNEL_ID) if guild else None

        if channel is None:
            print(f"Canal {CHANNEL_ID} introuvable")
            await self.close()
            return

        try:
            msg = await channel.fetch_message(MESSAGE_ID)
        except discord.NotFound:
            print(f"Message {MESSAGE_ID} introuvable")
            await self.close()
            return

        dump_message(msg)

        # Verdict
        print("\n=== VERDICT ===")
        meta = getattr(msg, 'interaction_metadata', None)
        if meta and (getattr(meta, 'user', None) or getattr(meta, 'user_id', None)):
            user = getattr(meta, 'user', None)
            uid = user.id if user else getattr(meta, 'user_id', None)
            print(f"✓ interaction_metadata → bumper_id = {uid}")
        else:
            intr = getattr(msg, 'interaction', None)
            if intr and getattr(intr, 'user', None):
                print(f"✓ message.interaction → bumper_id = {intr.user.id}")
            else:
                import re
                text = msg.content
                for embed in msg.embeds:
                    text += ' ' + ' '.join(filter(None, [
                        embed.description, embed.title,
                        *(f.name for f in embed.fields),
                        *(f.value for f in embed.fields),
                    ]))
                m = re.search(r'<@!?(\d+)>', text)
                if m:
                    print(f"✓ mention embed/content → bumper_id = {m.group(1)}")
                else:
                    print("✗ Impossible de déterminer l'auteur — nouvelle stratégie nécessaire")

        await self.close()


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = TestClient(intents=intents)
asyncio.run(client.start(DISCORD_TOKEN))
