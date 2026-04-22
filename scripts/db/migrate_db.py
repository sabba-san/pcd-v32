import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/home/abbas/development/pcd-v32/.env')

db_url = os.getenv('DATABASE_URL')
# For running from the host machine, we might need to replace 'flask_db' with 'localhost'
if 'flask_db' in db_url:
    db_url = db_url.replace('flask_db', 'localhost')

print(f"Connecting to database: {db_url}")

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    # Check if column exists
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'profile_picture'
    """)
    
    if cur.fetchone():
        print("Column 'profile_picture' already exists in 'users' table.")
    else:
        print("Adding column 'profile_picture' to 'users' table...")
        cur.execute("ALTER TABLE users ADD COLUMN profile_picture VARCHAR(500);")
        conn.commit()
        print("Column added successfully.")
        
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error during migration: {str(e)}")
