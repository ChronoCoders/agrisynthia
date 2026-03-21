import multiprocessing
import os

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes - Optimized for ML workloads
workers = min(
    4, multiprocessing.cpu_count()
)  # Limit to 4 workers max for GPU/ML models
worker_class = "gevent"  # Use gevent for better concurrency with I/O-bound ML tasks
threads = 2  # Threads per worker for parallel request handling
worker_connections = 1000
max_requests = 500  # Restart workers after 500 requests to prevent memory leaks
max_requests_jitter = (
    50  # Add randomness to prevent all workers restarting simultaneously
)
timeout = 120
keepalive = 5

# Memory management - Use RAM disk for temp files (faster I/O)
worker_tmp_dir = "/dev/shm" if os.path.exists("/dev/shm") else None

# Graceful timeout
graceful_timeout = 30

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "farmvision"

# Server mechanics
daemon = False
pidfile = None
user = None
group = None
tmp_upload_dir = None


# Worker lifecycle hooks for memory monitoring
def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("Gunicorn server starting...")


def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    server.log.info("Gunicorn server reloading...")


def when_ready(server):
    """Called just after the server is started."""
    server.log.info("Gunicorn server is ready. Workers: %s", workers)


def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)


def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT."""
    worker.log.info("Worker received INT or QUIT signal")


def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    worker.log.info("Worker received SIGABRT signal")
