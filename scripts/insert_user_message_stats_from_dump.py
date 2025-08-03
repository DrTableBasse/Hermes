import psycopg2
import re

DUMP_FILE = './dump.sql'  # Adapter le chemin si besoin
PG_HOST = 'localhost'
PG_USER = 'hermes_bot'
PG_DB = 'saucisseland'
PG_PASSWORD = 'bot_password_2024'

# Connexion à la base
conn = psycopg2.connect(host=PG_HOST, user=PG_USER, password=PG_PASSWORD, database=PG_DB)
cursor = conn.cursor()

# Extraction des lignes COPY
with open(DUMP_FILE, 'r', encoding='utf-8') as f:
    in_copy = False
    for line in f:
        if line.strip().startswith('COPY public.user_message_stats'):
            in_copy = True
            continue
        if in_copy:
            if line.strip() == '' or line.startswith('\\.'):
                break
            # Format: user_id\tchannel_id\tmessage_count
            parts = line.strip().split('\t')
            if len(parts) != 3:
                continue
            user_id, channel_id, message_count = parts
            cursor.execute('''
                INSERT INTO user_message_stats (user_id, channel_id, message_count)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, channel_id) DO UPDATE SET message_count = EXCLUDED.message_count
            ''', (user_id, channel_id, message_count))

conn.commit()
cursor.close()
conn.close()
print('✅ Insertion terminée !') 