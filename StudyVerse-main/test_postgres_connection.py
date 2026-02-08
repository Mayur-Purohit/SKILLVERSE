"""
Test PostgreSQL Connection
Quick script to verify that PostgreSQL is accessible with the credentials in .env
"""

import os
from dotenv import load_dotenv
import psycopg2
from urllib.parse import urlparse

# Load environment variables
load_dotenv()

def test_connection():
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("❌ DATABASE_URL not found in .env file")
        return False
    
    if 'postgresql' not in database_url:
        print(f"❌ DATABASE_URL is not PostgreSQL: {database_url}")
        return False
    
    # Parse the database URL
    result = urlparse(database_url)
    
    print("🔍 Testing PostgreSQL connection...")
    print(f"   Host: {result.hostname}")
    print(f"   Port: {result.port}")
    print(f"   Database: {result.path[1:]}")
    print(f"   User: {result.username}")
    print()
    
    try:
        # Attempt to connect
        conn = psycopg2.connect(
            host=result.hostname,
            port=result.port,
            database=result.path[1:],
            user=result.username,
            password=result.password
        )
        
        # Test with a simple query
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        
        print("✅ Connection successful!")
        print(f"📊 PostgreSQL version: {version[0]}")
        
        cursor.close()
        conn.close()
        return True
        
    except psycopg2.OperationalError as e:
        error_msg = str(e)
        print("❌ Connection failed!")
        print(f"   Error: {error_msg}")
        print()
        
        if "password authentication failed" in error_msg:
            print("💡 Suggestions:")
            print("   - Check the password in your .env file")
            print("   - Make sure special characters are URL-encoded")
            print("   - Verify the postgres user password")
        elif "connection refused" in error_msg or "could not connect" in error_msg:
            print("💡 Suggestions:")
            print("   - Make sure PostgreSQL is installed")
            print("   - Check if PostgreSQL service is running")
            print("   - Verify port 5432 is not blocked")
        elif "database" in error_msg and "does not exist" in error_msg:
            print("💡 Suggestions:")
            print("   - Create the database using pgAdmin or psql")
            print("   - Run: CREATE DATABASE StudyVerse_Final;")
        else:
            print("💡 Check your PostgreSQL installation and configuration")
        
        return False
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("  PostgreSQL Connection Test")
    print("=" * 60)
    print()
    
    if test_connection():
        print()
        print("🎉 Ready to run: python init_postgres_db.py")
    else:
        print()
        print("⚠️  Fix the connection issues before proceeding")
        print("📖 See POSTGRES_MIGRATION_GUIDE.md for help")
