import multiprocessing

# ==========================================
# Gunicorn Configuration for Render (Optimized)
# ==========================================

# Bind to the port provided by Render
bind = "0.0.0.0:10000"

# Worker Class
# KEY DECISION: We MUST use 'eventlet' to support Flask-SocketIO (Chat/Notifications).
# The user's snippet suggested 'gthread', but that would break real-time features.
worker_class = 'eventlet'

# Number of worker processes
# User requested 2. With eventlet, even 1 is powerful, but we'll set 2.
workers = 1

# Threads (Not used with eventlet, but kept for reference if switching to gthread)
# threads = 2

# ==========================================
# PERFORMANCE OPTIMIZATIONS (From User Request)
# ==========================================

# Timeout for workers (Prevent killing slow requests too early)
timeout = 120

# Keep-alive connections (reduces connection overhead)
keepalive = 5

# Restart workers after this many requests (prevents memory leaks)
max_requests = 1000
max_requests_jitter = 50

# Preload app optimization
# (Loads app code into memory before forking workers = faster startup)
preload_app = True

# ==========================================
# LOGGING
# ==========================================
accesslog = '-'
errorlog = '-'
loglevel = 'warning'
