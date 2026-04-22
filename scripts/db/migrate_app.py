import os
from app import create_app, db
from sqlalchemy import text

# Override DATABASE_URL for host access
os.environ['DATABASE_URL'] = 'postgresql://user:password@localhost:5432/flaskdb'

app = create_app()
with app.app_context():
    try:
        # Check if column exists
        result = db.session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'profile_picture'
        """))
        
        if result.fetchone():
            print("Column 'profile_picture' already exists in 'users' table.")
        else:
            print("Adding column 'profile_picture' to 'users' table...")
            db.session.execute(text("ALTER TABLE users ADD COLUMN profile_picture VARCHAR(500);"))
            db.session.commit()
            print("Column added successfully.")
    except Exception as e:
        print(f"Error during migration: {str(e)}")
