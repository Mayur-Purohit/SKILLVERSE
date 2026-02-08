"""
Initialize PostgreSQL Database for StudyVerse
Drops all existing tables and recreates them with the current schema.
Run this script after switching to PostgreSQL to set up the database.
"""

from app import app, db
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

def init_database():
    with app.app_context():
        print("🔄 Dropping all existing tables...")
        db.drop_all()
        
        print("🏗️  Creating all tables from models...")
        db.create_all()
        
        print("✅ Database initialized successfully!")
        print(f"📊 Database: {os.getenv('DATABASE_URL', 'Not set').split('@')[-1] if '@' in os.getenv('DATABASE_URL', '') else os.getenv('DATABASE_URL', 'Not set')}")

if __name__ == "__main__":
    print("=" * 60)
    print("  PostgreSQL Database Initialization for StudyVerse")
    print("=" * 60)
    print("\n⚠️  WARNING: This will DROP all existing tables and data!")
    
    database_url = os.getenv('DATABASE_URL', 'Not set')
    
    if 'postgresql' not in database_url:
        print(f"\n❌ Error: DATABASE_URL is not set to PostgreSQL")
        print(f"Current: {database_url}")
        print("\nPlease update your .env file to use PostgreSQL")
        exit(1)
        
    confirm = input("\nType 'yes' to continue: ")
    
    if confirm.lower() == 'yes':
        try:
            init_database()
        except Exception as e:
            print(f"\n❌ Error initializing database: {e}")
            print("\nMake sure:")
            print("1. PostgreSQL is installed and running")
            print("2. The database 'StudyVerse_Final' exists")
            print("3. The credentials in .env are correct")
            exit(1)
    else:
        print("\n❌ Initialization cancelled")
