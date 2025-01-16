import sqlite3

def setup_database():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()

    # Create user_voice_data table if it does not exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_voice_data (
            user_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            total_time INTEGER DEFAULT 0
        )
    ''')

    # Create warn table 
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS warn (
            user_id INTEGER,
            reason TEXT,
            create_time INTEGER,
            FOREIGN KEY (user_id) REFERENCES user_voice_data(user_id)
        )
    ''')

    conn.commit()
    conn.close()
    print("Database setup complete.")

if __name__ == "__main__":
    setup_database()
