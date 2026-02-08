"""
Add missing columns and tables to PostgreSQL database
This script adds any missing columns to existing tables and creates new tables
"""

from app import app, db
from sqlalchemy import text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def migrate_database():
    with app.app_context():
        print("🔄 Adding missing columns and tables...")
        
        # Get connection
        connection = db.engine.connect()
        
        try:
            # 1. Add syllabus_id column to todo table if it doesn't exist
            print("\n1. Checking todo table for syllabus_id column...")
            try:
                result = connection.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='todo' AND column_name='syllabus_id'
                """))
                if result.rowcount == 0:
                    print("   ➕ Adding syllabus_id column to todo table...")
                    connection.execute(text("""
                        ALTER TABLE todo 
                        ADD COLUMN syllabus_id INTEGER REFERENCES syllabus_document(id)
                    """))
                    connection.commit()
                    print("   ✅ Added syllabus_id column")
                else:
                    print("   ✓ syllabus_id column already exists")
            except Exception as e:
                print(f"   ⚠️  Error with syllabus_id: {e}")
                connection.rollback()
            
            # 2. Create user_item table if it doesn't exist
            print("\n2. Checking for user_item table...")
            try:
                result = connection.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_name='user_item'
                """))
                if result.rowcount == 0:
                    print("   ➕ Creating user_item table...")
                    connection.execute(text("""
                        CREATE TABLE user_item (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER NOT NULL REFERENCES "user"(id),
                            item_id VARCHAR(50) NOT NULL,
                            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            is_active BOOLEAN DEFAULT FALSE
                        )
                    """))
                    connection.commit()
                    print("   ✅ Created user_item table")
                else:
                    print("   ✓ user_item table already exists")
            except Exception as e:
                print(f"   ⚠️  Error with user_item: {e}")
                connection.rollback()
            
            # 3. Create active_power_up table if it doesn't exist
            print("\n3. Checking for active_power_up table...")
            try:
                result = connection.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_name='active_power_up'
                """))
                if result.rowcount == 0:
                    print("   ➕ Creating active_power_up table...")
                    connection.execute(text("""
                        CREATE TABLE active_power_up (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER NOT NULL REFERENCES "user"(id),
                            power_up_id VARCHAR(50) NOT NULL,
                            activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            expires_at TIMESTAMP,
                            multiplier FLOAT DEFAULT 1.0,
                            is_active BOOLEAN DEFAULT TRUE
                        )
                    """))
                    connection.commit()
                    print("   ✅ Created active_power_up table")
                else:
                    print("   ✓ active_power_up table already exists")
            except Exception as e:
                print(f"   ⚠️  Error with active_power_up: {e}")
                connection.rollback()
            
            # 4. Create event table if it doesn't exist  
            print("\n4. Checking for event table...")
            try:
                result = connection.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_name='event'
                """))
                if result.rowcount == 0:
                    print("   ➕ Creating event table...")
                    connection.execute(text("""
                        CREATE TABLE event (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER NOT NULL REFERENCES "user"(id),
                            title VARCHAR(200) NOT NULL,
                            description TEXT,
                            date VARCHAR(50) NOT NULL,
                            time VARCHAR(50),
                            is_notified BOOLEAN DEFAULT FALSE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                    connection.commit()
                    print("   ✅ Created event table")
                else:
                    print("   ✓ event table already exists")
            except Exception as e:
                print(f"   ⚠️  Error with event: {e}")
                connection.rollback()
            
            print("\n" + "=" * 60)
            print("✅ Database migration completed!")
            print("=" * 60)
            
        finally:
            connection.close()

if __name__ == "__main__":
    print("=" * 60)
    print("  PostgreSQL Database Migration")
    print("=" * 60)
    print("\nThis will add missing columns and tables to your database.")
    print("\n⚠️  Make sure the app is NOT running before proceeding!")
    
    confirm = input("\nType 'yes' to continue: ")
    
    if confirm.lower() == 'yes':
        try:
            migrate_database()
        except Exception as e:
            print(f"\n❌ Error during migration: {e}")
            import traceback
            traceback.print_exc()
            exit(1)
    else:
        print("\n❌ Migration cancelled")
