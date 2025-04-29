import sqlite3

# Connect to the database
conn = sqlite3.connect('menfess.db')
cursor = conn.cursor()

# Check if display_name column exists in menfess table
cursor.execute("PRAGMA table_info(menfess)")
columns = cursor.fetchall()
column_names = [column[1] for column in columns]

# Add display_name column if it doesn't exist
if 'display_name' not  for column in columns]

# Add display_name column if it doesn't exist
if 'display_name' not in column_names:
    print("Adding display_name column to menfess table...")
    cursor.execute("ALTER TABLE menfess ADD COLUMN display_name TEXT")
    conn.commit()
    print("Column added successfully!")
else:
    print("display_name column already exists.")

# Close the connection
conn.close()
print("Database update completed!")
