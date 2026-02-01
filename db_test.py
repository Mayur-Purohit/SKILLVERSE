
import sys
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

# Try default postgres DB
url_default = "postgresql://postgres:8791@localhost/postgres"
print(f"Testing connection to: {url_default}")

try:
    engine = create_engine(url_default)
    with engine.connect() as conn:
        print("Connected to 'postgres' successfully!")
except Exception as e:
    print("Failed to connect to 'postgres'.")
    # minimal error print
    err = str(e)
    if "password authentication failed" in err:
        print("Error: Password authentication failed.")
    elif "does not exist" in err:
        print("Error: Database does not exist.")
    elif "Connection refused" in err:
        print("Error: Connection refused (Port/Host issue).")
    else:
        print(f"Error: {str(e)[:100]}...")

# If that worked, try skillverse_pg
url_target = "postgresql://postgres:8791@localhost/skillverse_pg"
print(f"Testing connection to: {url_target}")
try:
    engine = create_engine(url_target)
    with engine.connect() as conn:
        print("Connected to 'skillverse_pg' successfully!")
except Exception as e:
    print("Failed to connect to 'skillverse_pg'.")
    err = str(e)
    if "does not exist" in err:
        print("Error: Database 'skillverse_pg' does not exist.")
    else:
        print(f"Error: {str(e)[:100]}...")
