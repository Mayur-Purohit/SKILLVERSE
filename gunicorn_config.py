import multiprocessing

# ==========================================
# Gunicorn Configuration for Render (Optimized)
# ==========================================

# Bind to the port provided by Render
bind = "0.0.0.0:10000"

# Worker Class (REQUIRED for Flask-SocketIO)
# Using 'eventlet' allows handling thousands of concurrent connections asynchronously.
worker_class = 'eventlet'

# Number of worker processes
# MUST be 1 because we are not using Redis for message queue.
# With eventlet, 1 worker is sufficient for 1000+ concurrent users.
workers = 1

# ==========================================
# PERFORMANCE OPTIMIZATIONS
# ==========================================

# Timeout for workers (Prevent killing slow requests too early)
timeout = 120

# Keep-alive connections (reduces connection overhead)
# This significantly improves TTFB for subsequent requests
keepalive = 5

# Graceful timeout (how long to wait for workers to finish)
graceful_timeout = 30

# Preload app optimization
# (Loads app code into memory before forking workers = faster startup)
preload_app = True

# ==========================================
# LOGGING (Production-grade)
# ==========================================
accesslog = '-'  # Log to stdout
errorlog = '-'   # Log to stderr
loglevel = 'warning'  # Only log warnings and errors (less I/O overhead)

# Reduce logging overhead (improves performance)
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# ==========================================
# CONNECTION SETTINGS
# ==========================================

# Maximum pending connections
backlog = 2048

# Worker connections (max simultaneous clients per worker)
worker_connections = 1000
