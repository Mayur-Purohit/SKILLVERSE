import sqlite3
import os

DB_PATH = 'instance/studyverse.db'

def run_migration():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Check if column exists
    try:
        cursor.execute("SELECT syllabus_id FROM todo LIMIT 1")
        print("Column 'syllabus_id' already exists in 'todo'.")
    except sqlite3.OperationalError:
        print("Adding 'syllabus_id' column to 'todo' table...")
        # Add column
        try:
            cursor.execute("ALTER TABLE todo ADD COLUMN syllabus_id INTEGER REFERENCES syllabus_document(id)")
            conn.commit()
            print("Column added successfully.")
        except Exception as e:
            print(f"Error adding column: {e}")
            return

    # 2. Backfill Data
    print("Backfilling syllabus_id for existing todos...")
    try:
        # Get all users
        cursor.execute("SELECT id FROM user")
        users = cursor.fetchall()
        
        for (user_id,) in users:
            # Get latest syllabus for this user
            # We assume the most recent one is the 'owner' of current tasks
            cursor.execute("SELECT id FROM syllabus_document WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,))
            res = cursor.fetchone()
            
            if res:
                syl_id = res[0]
                print(f"Linking todos for User {user_id} to Syllabus {syl_id}")
                # Update all todos for this user that don't have a syllabus_id
                cursor.execute("UPDATE todo SET syllabus_id = ? WHERE user_id = ? AND syllabus_id IS NULL", (syl_id, user_id))
        
        conn.commit()
        print("Backfill complete.")
        
    except Exception as e:
        print(f"Error during backfill: {e}")

    conn.close()

if __name__ == "__main__":
    run_migration()
