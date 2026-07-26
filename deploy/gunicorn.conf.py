"""Gunicorn production config, sized for a 2-core / 2 GB host.

2 processes x 4 threads = 8 concurrent requests while keeping only two
Python interpreters in memory. gthread workers release the GIL during DB
and file I/O, which is where this app spends its time. Do not raise
`workers` on the 2 GB host — add threads instead if more concurrency is
needed.
"""

bind = '127.0.0.1:5000'
workers = 2
worker_class = 'gthread'
threads = 4

timeout = 30
graceful_timeout = 20
keepalive = 5

# Recycle workers periodically so slow leaks can't accumulate on a small host.
max_requests = 1000
max_requests_jitter = 100

accesslog = '-'
access_log_format = '%(t)s "%(r)s" %(s)s %(B)s %(M)sms'
errorlog = '-'
