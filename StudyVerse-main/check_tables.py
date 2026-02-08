"""
Check which tables exist in PostgreSQL
"""
from app import app, db
from sqlalchemy import inspect

with app.app_context():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    print("=" * 60)
    print("Tables in PostgreSQL database:")
    print("=" * 60)
    for table in sorted(tables):
        print(f"  - {table}")
    print("=" * 60)
    print(f"Total tables: {len(tables)}")
