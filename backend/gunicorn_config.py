#!/usr/bin/env python3
"""
Simplified Gunicorn Configuration for GermanATO 
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
workers = 4
worker_class = "gevent"
worker_connections = 100
max_requests = 1000
max_requests_jitter = 50
preload_app = True

# Timeout settings
timeout = 30
keepalive = 2
graceful_timeout = 30

# Logging
accesslog = "/opt/germanato/logs/gunicorn_access.log"
errorlog = "/opt/germanato/logs/gunicorn_error.log"
loglevel = "info"

# Process naming
proc_name = "germanato"

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Performance
worker_tmp_dir = "/dev/shm"
worker_exit_on_app_exit = True

def when_ready(server):
    """Called just after the server is started."""
    server.log.info("🚀 GermanATO server is ready!")

def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("🔄 Starting GermanATO server...")

def on_exit(server):
    """Called just before exiting Gunicorn."""
    server.log.info("👋 GermanATO server shutting down...") 