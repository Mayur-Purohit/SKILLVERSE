from flask_login import LoginManager
from authlib.integrations.flask_client import OAuth
from flask_socketio import SocketIO
from flask_caching import Cache
from flask_compress import Compress

# Initialize extensions
login_manager = LoginManager()
oauth = OAuth()
socketio = SocketIO(cors_allowed_origins="*")
cache = Cache()
compress = Compress()
