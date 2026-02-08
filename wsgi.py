from gevent import monkey
monkey.patch_all()

try:
    from psycogreen.gevent import patch_psycopg
    patch_psycopg()
except ImportError:
    pass

import os
from app import create_app

app = create_app(os.getenv('FLASK_CONFIG', 'production'))

if __name__ == "__main__":
    app.run()
