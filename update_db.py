import sqlite3

# Connect to the database
conn = sqlite3.connect('menfess.db')
cursor = conn.cursor()

# Check if profile_picture column exists in user table
cursor.execute("PRAGMA table_info(user)")
columns = cursor.fetchall()
column_names = [column[1] for column in columns]

# Add profile_picture column if it doesn't exist
if 'profile_picture' not in column_names:
    print("Adding profile_picture column to user table...")
    cursor.execute("ALTER TABLE user ADD COLUMN profile_picture TEXT DEFAULT 'default.png'")
    conn.commit()
    print("Column added successfully!")
else:
    print("profile_picture column already exists.")

# Check if comment table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='comment'")
if not cursor.fetchone():
    print("Creating comment table...")
    cursor.execute('''
    CREATE TABLE comment (
        id INTEGER PRIMARY KEY,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        user_id INTEGER NOT NULL,
        menfess_id INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES user (id),
        FOREIGN KEY (menfess_id) REFERENCES menfess (id) ON DELETE CASCADE
    )
    ''')
    conn.commit()
    print("Comment table created successfully!")
else:
    print("Comment table already exists.")

# Check if voice_note column exists in menfess table
cursor.execute("PRAGMA table_info(menfess)")
columns = cursor.fetchall()
column_names = [column[1] for column in columns]

# Add voice_note column if it doesn't exist
if 'voice_note' not in column_names:
    print("Adding voice_note column to menfess table...")
    cursor.execute("ALTER TABLE menfess ADD COLUMN voice_note TEXT")
    conn.commit()
    print("Column added successfully!")
else:
    print("voice_note column already exists.")

# Create uploads directories
import os
upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/uploads')
profile_pics_folder = os.path.join(upload_folder, 'profile_pics')
voice_notes_folder = os.path.join(upload_folder, 'voice_notes')

os.makedirs(profile_pics_folder, exist_ok=True)
os.makedirs(voice_notes_folder, exist_ok=True)
print(f"Created upload directories at {upload_folder}")

# Close the connection
conn.close()
print("Database update completed!")
