import multiprocessing

# Gunicorn Configuration for Render

# Bind to the port provided by Render
bind = "0.0.0.0:10000"

# Number of worker processes (Optimized for Render Free/Starter tiers)
# Using too many workers on free tier causes memory crashes.
# 2 workers is the sweet spot.
workers = 2

# Threads per worker (Best for database-heavy apps)
threads = 4

# Timeout for workers (Prevent killing slow requests too early)
timeout = 120

# Preload app optimization
# (Loads app code into memory before forking workers = faster startup)
preload_app = True
