import multiprocessing

# ==========================================
# Gunicorn Configuration for Render (Optimized)
# ==========================================

# Bind to the port provided by Render
bind = "0.0.0.0:10000"

# Worker Class
# KEY DECISION: Use 'eventlet' for Flask-SocketIO support
worker_class = 'eventlet'

# Number of worker processes
# increased to 2 to handle concurrent requests (e.g. Chat + Browsing)
# 2 workers * 1 thread each is usually safe for 512MB RAM
workers = 2

# Threads are not used with eventlet workers
threads = 1

# ==========================================
# PERFORMANCE OPTIMIZATIONS
# ==========================================

# Timeout: Allow longer processing for AI/DB operations
# Render recommends 120s for slow starts, but we want faster fail-recovery
timeout = 120

# Keep-alive: Reduce overhead for sequential requests
keepalive = 5

# Restart workers periodically to prevent memory leaks
max_requests = 500
max_requests_jitter = 50

# Preload app: True to use Copy-on-Write memory sharing (saves RAM with multiple workers)
# This is CRITICAL for running 2 workers on 512MB RAM
preload_app = True

# ==========================================
# LOGGING
# ==========================================
accesslog = '-'
errorlog = '-'
loglevel = 'info'
