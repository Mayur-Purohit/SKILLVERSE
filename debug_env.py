
import os
from dotenv import load_dotenv

user_env_path = os.path.join(os.getcwd(), '.env')
print(f"Loading .env from: {user_env_path}")
load_dotenv(user_env_path)

db_url = os.environ.get('DATABASE_URL')
print(f"Loaded DATABASE_URL: {db_url}")

# config.py check
try:
    from config import Config
    print(f"Config SQLALCHEMY_DATABASE_URI: {Config.SQLALCHEMY_DATABASE_URI}")
except Exception as e:
    print(f"Error loading config: {e}")
