from app import app, db
from sqlalchemy import text

def migrate():
    with app.app_context():
        print("Starting PostgreSQL migration...")
        
        # 1. Add Column
        try:
            # Check if column exists logic is obscure in raw SQL across versions, 
            # simplest way is often to try adding it and catch existing error, 
            # or query information_schema.
            # Let's try the safe 'IF NOT EXISTS' approach if supported, otherwise catch specific error.
            
            print("Adding syllabus_id column to todo table...")
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE todo ADD COLUMN IF NOT EXISTS syllabus_id INTEGER REFERENCES syllabus_document(id)"))
                conn.commit()
            print("Column added (or already existed).")
            
        except Exception as e:
            print(f"Error adding column (might already exist): {e}")

        # 2. Backfill
        print("Backfilling data...")
        try:
             with db.engine.connect() as conn:
                # Find users with docs
                result = conn.execute(text("SELECT id FROM user_account")) # Try user_account or user? Model is 'User' -> table 'user' usually
                # Wait, let's check the table name. In app.py User model table name defaults to 'user' usually.
                # However, Postgres 'user' is a reserved keyword. SQLAlchemy usually quotes it "user".
                # Let's rely on the ORM for the backfill logic to be safe.
                pass
        except Exception as e:
            print(f"Error connecting: {e}")

        # ORM Backfill Safe Mode
        from app import User, SyllabusDocument, Todo
        
        users = User.query.all()
        count = 0
        for user in users:
            # Get latest doc
            latest_doc = SyllabusDocument.query.filter_by(user_id=user.id).order_by(SyllabusDocument.created_at.desc()).first()
            
            if latest_doc:
                # Find orphan todos (those with no syllabus_id)
                orphans = Todo.query.filter_by(user_id=user.id, syllabus_id=None).all()
                for t in orphans:
                    t.syllabus_id = latest_doc.id
                count += len(orphans)
        
        db.session.commit()
        print(f"Backfilled {count} tasks to their latest syllabus.")
        print("Migration complete.")

if __name__ == "__main__":
    migrate()
