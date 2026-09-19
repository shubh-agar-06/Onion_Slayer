# gunicorn.conf.py — Render deployment configuration
# Single worker with 4 threads to keep RAM under 512 MB on Render free tier

workers = 1          # DO NOT increase — each worker duplicates RAM usage
threads = 4          # Handles concurrent requests without forking new processes
timeout = 120        # Allow longer for first-request ML model load
worker_class = "gthread"
bind = "0.0.0.0:10000"  # Render assigns $PORT; this is the default
accesslog = "-"
errorlog = "-"
loglevel = "info"
