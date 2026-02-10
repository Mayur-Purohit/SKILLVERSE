from flask_login import LoginManager
from authlib.integrations.flask_client import OAuth
from flask_socketio import SocketIO

# Initialize extensions
login_manager = LoginManager()
oauth = OAuth()
# Robust SocketIO configuration for Render deployment
# ping_timeout=60: Wait 60s before considering client disconnected (fixes slow network issues)
# async_mode='eventlet': Explicitly set async mode for Gunicorn worker
socketio = SocketIO(cors_allowed_origins="*", async_mode='eventlet', ping_timeout=60, ping_interval=25)
