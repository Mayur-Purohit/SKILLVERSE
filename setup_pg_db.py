
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Connection details
db_user = "postgres"
db_pass = "8791"
db_host = "localhost"
target_db = "skillverse_pg"
default_db = "postgres"

print(f"Connecting to '{default_db}' to check/create '{target_db}'...")

try:
    # Connect to default 'postgres' database
    conn = psycopg2.connect(
        user=db_user,
        password=db_pass,
        host=db_host,
        dbname=default_db
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    
    # Check if target database exists
    cur.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{target_db}'")
    exists = cur.fetchone()
    
    if not exists:
        print(f"Database '{target_db}' does not exist. Creating...")
        cur.execute(f"CREATE DATABASE {target_db}")
        print(f"Database '{target_db}' created successfully.")
    else:
        print(f"Database '{target_db}' already exists.")
        
    cur.close()
    conn.close()
    print("Database check complete.")

except Exception as e:
    print(f"Error: {e}")
