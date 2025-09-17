# Gunicorn configuration for production Flask app
import multiprocessing

# Application module
wsgi_module = "web_app_flask:app"

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
workers = max(2, multiprocessing.cpu_count())
worker_class = "gthread"
worker_connections = 1000
threads = 4
max_requests = 1000
max_requests_jitter = 100

# Timeout settings
timeout = 300
keepalive = 2
graceful_timeout = 30

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'busqa_flask_app'

# Server mechanics
daemon = False
pidfile = '/tmp/gunicorn.pid'
user = None
group = None
tmp_upload_dir = '/tmp'

# SSL (if needed)
# keyfile = None
# certfile = None

# Application
wsgi_module = "web_app_flask:app"
reload = False
preload_app = True

# Worker recycling
max_worker_memory = 300  # MB
memory_monitor_interval = 10  # seconds
