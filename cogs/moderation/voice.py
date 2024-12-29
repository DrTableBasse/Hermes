import discord
from discord.ext import commands
from datetime import datetime, timezone
import sqlite3
import os
from utils.constants import VOICE_LOG_CHANNEL_NAME
from utils.logging import log_voice_event
from utils.constants import DB_PATH

ROLE_NAME = 'Batman'  # Replace with the actual role name

class VoiceLoggingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_state = {}  # Dictionary to keep track of members' join times
        self.db_path = DB_PATH  # Path to the database file
        self._print_db_path()  # Print the path to the database file for debugging

    def _get_db_connection(self):
        return sqlite3.connect(self.db_path)

    def _print_db_path(self):
        # Print the absolute path to the database file for debugging
        abs_path = os.path.abspath(self.db_path)
        print(f"[DEBUG] Database file path: {abs_path}")

    async def _update_user_time(self, user_id, time_spent):
        conn = self._get_db_connection()
        cursor = conn.cursor()
        new_total_time = 0
        total_time_before_update = 0

        try:
            # Check if the user already exists
            cursor.execute('SELECT total_time FROM user_voice_data WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()

            if row:
                # Update the existing user's total time
                total_time_before_update = row[0]
                new_total_time = total_time_before_update + time_spent
                cursor.execute('UPDATE user_voice_data SET total_time = ? WHERE user_id = ?', (new_total_time, user_id))
                debug_message = f'[DEBUG] Updated user {user_id} total time to {new_total_time} seconds.'
            else:
                # Insert a new user
                username = (await self.bot.fetch_user(user_id)).name
                new_total_time = time_spent
                cursor.execute('INSERT INTO user_voice_data (user_id, username, total_time) VALUES (?, ?, ?)', (user_id, username, new_total_time))
                debug_message = f'[DEBUG] Inserted new user {user_id} with time {time_spent} seconds.'

            conn.commit()
        except sqlite3.Error as e:
            debug_message = f'[ERROR] SQLite error: {e}'
        finally:
            conn.close()

        # Log the debug message to the console
        print(debug_message)

        # Optionally, send the debug message to a logging channel
        log_channel = discord.utils.get(self.bot.get_all_channels(), name='debug-log')  # Replace with your actual log channel name
        if log_channel:
            await log_channel.send(debug_message)


    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        log_channel = discord.utils.get(member.guild.text_channels, name=VOICE_LOG_CHANNEL_NAME)
        if not log_channel:
            print(f"[ERROR] Log channel '{VOICE_LOG_CHANNEL_NAME}' not found")
            return

        if before.channel is None and after.channel is not None:
            # User joined a voice channel
            join_time = datetime.now(timezone.utc)
            self.voice_state[member.id] = join_time
            await log_voice_event(
                member=member, 
                action='a rejoint le salon vocal', 
                to_channel=after.channel, 
                log_channel_name=VOICE_LOG_CHANNEL_NAME
            )
            print(f"[DEBUG] User {member.id} joined {after.channel.name} at {join_time}")

        elif before.channel is not None and after.channel is None:
            # User left a voice channel
            leave_time = datetime.now(timezone.utc)
            join_time = self.voice_state.pop(member.id, None)
            duration_str = ""
            if join_time:
                duration = leave_time - join_time
                duration_seconds = int(duration.total_seconds())
                await self._update_user_time(member.id, duration_seconds)
                hours, remainder = divmod(duration_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                duration_str = f"{hours}h {minutes}m {seconds}s"
                print(f"[DEBUG] Duration string: {duration_str}")
            await log_voice_event(
                member=member, 
                action='a quitté le salon vocal', 
                from_channel=before.channel, 
                duration=duration_str, 
                log_channel_name=VOICE_LOG_CHANNEL_NAME
            )

        elif before.channel != after.channel:
            # User moved from one voice channel to another
            leave_time = datetime.now(timezone.utc)
            join_time = self.voice_state.pop(member.id, None)
            duration_str = ""
            if join_time:
                duration = leave_time - join_time
                duration_seconds = int(duration.total_seconds())
                await self._update_user_time(member.id, duration_seconds)
                hours, remainder = divmod(duration_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                duration_str = f"{hours}h {minutes}m {seconds}s"
                print(f"[DEBUG] User {member.id} moved from {before.channel.name} to {after.channel.name} after {duration_str}")
            await log_voice_event(
                member=member, 
                action=f'est passé de **{before.channel.name}** à **{after.channel.name}**', 
                duration=duration_str, 
                log_channel_name=VOICE_LOG_CHANNEL_NAME
            )
            self.voice_state[member.id] = datetime.now(timezone.utc)

async def setup(bot):
    await bot.add_cog(VoiceLoggingCog(bot))
