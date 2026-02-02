
import os
from sqlalchemy import text
from app import create_app, db

app = create_app(os.getenv('FLASK_ENV', 'development'))

def apply_indexes():
    with app.app_context():
        print("Applying database indexes for performance...")
        
        # Connection
        conn = db.session.connection()
        
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_services_price ON services(price);",
            "CREATE INDEX IF NOT EXISTS idx_services_is_active ON services(is_active);"
        ]
        
        for sql in indexes:
            try:
                print(f"Executing: {sql}")
                db.session.execute(text(sql))
                db.session.commit()
                print("Success.")
            except Exception as e:
                print(f"Error executing {sql}: {e}")
                db.session.rollback()

if __name__ == '__main__':
    apply_indexes()
