import discord
from discord.ext import commands, tasks
import sqlite3
import os
from utils.logging import log_voice_event  # Import the logging functions

ROLE_NAME = 'Batman'  # Replace with the actual role name
DB_PATH = 'data.db'  # Path to your SQLite database

class RoleAssignmentCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_voice_times.start()

    def cog_unload(self):
        self.check_voice_times.cancel()

    def get_db_connection(self):
        return sqlite3.connect(DB_PATH)

    @tasks.loop(hours=1)
    async def check_voice_times(self):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Select users who have more than or equal to 100 hours (360000 seconds)
            cursor.execute('SELECT user_id, username, total_time FROM user_voice_data WHERE total_time >= ?', (100 * 3600,))
            users = cursor.fetchall()
            
            for user_id, username, total_time in users:
                for guild in self.bot.guilds:
                    member = guild.get_member(user_id)
                    if member:
                        role = discord.utils.get(guild.roles, name=ROLE_NAME)
                        if role and role not in member.roles:
                            try:
                                await member.add_roles(role)
                                print(f"[DEBUG] Successfully assigned role '{ROLE_NAME}' to user {user_id} ({username}).")
                                
                                # Log role assignment
                                log_channel_name = "role-assignments"  # Define the log channel name
                                embed_description = f"Role '{ROLE_NAME}' has been assigned to {member.mention} ({username})."
                                await log_voice_event(
                                    member=member,
                                    action="Role Assigned",
                                    duration=None,
                                    from_channel=None,
                                    to_channel=None,
                                    log_channel_name=log_channel_name
                                )
                            except discord.Forbidden:
                                print(f"[ERROR] Missing permissions to assign role '{ROLE_NAME}' to user {user_id} ({username}).")
                            except discord.HTTPException as e:
                                print(f"[ERROR] Failed to assign role '{ROLE_NAME}' to user {user_id} ({username}): {e}")
                        else:
                            print(f"[DEBUG] User {user_id} ({username}) already has the role '{ROLE_NAME}' or role not found.")
                    else:
                        print(f"[DEBUG] Member with ID {user_id} not found in guild {guild.name}.")
        except sqlite3.Error as e:
            print(f"[ERROR] SQLite error: {e}")
        finally:
            conn.close()

    @check_voice_times.before_loop
    async def before_check_voice_times(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(RoleAssignmentCog(bot))
