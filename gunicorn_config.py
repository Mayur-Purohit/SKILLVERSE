import multiprocessing

# Gunicorn Configuration for Render

# Bind to the port provided by Render
bind = "0.0.0.0:10000"

# Worker Class (REQUIRED for Flask-SocketIO)
# Using 'eventlet' allows handling thousands of concurrent connections asynchronously.
worker_class = 'eventlet'

# Number of worker processes
# MUST be 1 because we are not using Redis for message queue.
# With eventlet, 1 worker is sufficient for 1000+ concurrent users.
workers = 1

# Threads are not used with eventlet worker class
# threads = 4

# Timeout for workers (Prevent killing slow requests too early)
timeout = 120

# Preload app optimization
# (Loads app code into memory before forking workers = faster startup)
preload_app = True
