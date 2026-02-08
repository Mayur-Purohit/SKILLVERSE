import eventlet
eventlet.monkey_patch()

import os
from app import create_app

app = create_app(os.getenv('FLASK_CONFIG', 'production'))

if __name__ == "__main__":
    app.run()
