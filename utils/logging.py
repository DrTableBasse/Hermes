import discord
from datetime import datetime


#Logs commandes
async def log_command_usage(interaction, command_name, member=None, reason=None, log_channel_name="all-logs"):
    guild = interaction.guild
    log_channel = discord.utils.get(guild.text_channels, name=log_channel_name)
    if log_channel:
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        embed = discord.Embed(
            title="Commande Utilisée",
            description=f'{interaction.user} a utilisé la commande **/{command_name}**',
            color=discord.Color.green() if command_name in ["blague", "unmute"] else discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=interaction.user.avatar.url)
        if member:
            embed.add_field(name="Utilisateur", value=member.mention, inline=False)
        if reason:
            embed.add_field(name="Raison", value=reason, inline=False)
        embed.add_field(name="Date", value=now, inline=False)
        await log_channel.send(embed=embed)
    else:
        print(f"[ERROR] Log channel '{log_channel_name}' not found in guild '{guild.name}'")




async def log_voice_event(member, action, duration=None, from_channel=None, to_channel=None, log_channel_name="🔗logs-vocal"):
    guild = member.guild
    log_channel = discord.utils.get(guild.text_channels, name=log_channel_name)
    if log_channel:
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        embed = discord.Embed(
            title="Log de Salon Vocal",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=member.avatar.url)
        embed.add_field(name="Utilisateur", value=member.mention, inline=False)
        embed.add_field(name="Action", value=action, inline=False)
        if from_channel:
            embed.add_field(name="De", value=from_channel.name, inline=False)
        if to_channel:
            embed.add_field(name="À", value=to_channel.name, inline=False)
        if duration:
            embed.add_field(name="Durée", value=duration, inline=False)
        embed.add_field(name="Date", value=now, inline=False)
        await log_channel.send(embed=embed)
    else:
        print(f"[ERROR] Log channel '{log_channel_name}' not found in guild '{guild.name}'")



# New function for role assignment logging
async def log_role_assignment(member, role_name, log_channel_name="role-assignments"):
    guild = member.guild
    log_channel = discord.utils.get(guild.text_channels, name=log_channel_name)
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
        print(f"[ERROR] Log channel '{log_channel_name}' not found in guild '{guild.name}'")


async def log_sanction(member, action, reason=None, log_channel_name="sanctions", action_taken_by=None):
    guild = member.guild
    log_channel = discord.utils.get(guild.text_channels, name=log_channel_name)
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
        print(f"[ERROR] Log channel '{log_channel_name}' not found in guild '{guild.name}'")


async def log_confession(user, confession_message, log_channel_name="confessions-log"):
    guild = user.guild
    log_channel = discord.utils.get(guild.text_channels, name=log_channel_name)
    
    if log_channel:
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        log_message = (
            f"**Nouvelle Confession**\n"
            f"**Utilisateur :** {user.name}#{user.discriminator}\n"
            f"**Confession :** {confession_message}\n"
            f"**Date :** {now}"
        )
        await log_channel.send(log_message)
    else:
        print(f"[ERROR] Log channel '{log_channel_name}' not found in guild '{guild.name}'")