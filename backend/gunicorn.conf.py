import os

wsgi_app = "tabby.wsgi:application"
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = int(os.getenv("WEB_CONCURRENCY", "4"))
preload_app = True
sendfile = True

max_requests = 1000
max_requests_jitter = 100
