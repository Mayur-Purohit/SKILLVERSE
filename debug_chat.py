
from app import create_app
from chat_manager import chat_manager
import os
from dotenv import load_dotenv

load_dotenv()

app = create_app()
with app.app_context():
    print(f"Config Key: {app.config.get('GEMINI_API_KEY')[:10]}...")
    print(f"Env Key: {os.environ.get('GEMINI_API_KEY')[:10]}...")
    
    try:
        chat_manager.setup()
        print("Setup done.")
        response = chat_manager.get_response("Hello", {}, "test_user")
        print(f"Response: {response}")
    except Exception as e:
        print(f"Error: {e}")
