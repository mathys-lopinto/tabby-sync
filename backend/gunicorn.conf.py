import os

wsgi_app = "tabby.wsgi:application"
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = int(os.getenv("WEB_CONCURRENCY", "4"))
preload_app = True
sendfile = True

# Kill workers that are stuck waiting on a connection that never sends
# a valid HTTP request (common with internet scanners sending SSH/RDP
# probes or opening connections without data). The default is 30s which
# ties up a sync worker for too long under background scan noise.
timeout = 10
graceful_timeout = 5

max_requests = 1000
max_requests_jitter = 100
