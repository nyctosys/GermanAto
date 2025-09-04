#!/usr/bin/env python3
"""
Debug Script for Production Session Issues
Run this to check session configuration and environment
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

def check_environment():
    print("=== GermanATO Production Session Debug ===\n")
    
    print("1. Environment Variables:")
    secret_key = os.getenv('SECRET_KEY')
    if secret_key:
        print(f"   ✅ SECRET_KEY: {'*' * 20} (length: {len(secret_key)})")
    else:
        print("   ❌ SECRET_KEY: Not set!")
    
    flask_env = os.getenv('FLASK_ENV', 'development')
    print(f"   📝 FLASK_ENV: {flask_env}")
    
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        print(f"   ✅ DATABASE_URL: {database_url[:30]}...")
    else:
        print("   ❌ DATABASE_URL: Not set!")
    
    print("\n2. Flask Session Configuration:")
    try:
        from app import app
        with app.app_context():
            print(f"   📝 SESSION_COOKIE_NAME: {app.config.get('SESSION_COOKIE_NAME', 'session')}")
            print(f"   📝 SESSION_COOKIE_SECURE: {app.config.get('SESSION_COOKIE_SECURE', False)}")
            print(f"   📝 SESSION_COOKIE_HTTPONLY: {app.config.get('SESSION_COOKIE_HTTPONLY', True)}")
            print(f"   📝 SESSION_COOKIE_SAMESITE: {app.config.get('SESSION_COOKIE_SAMESITE', 'Lax')}")
            print(f"   📝 SESSION_COOKIE_DOMAIN: {app.config.get('SESSION_COOKIE_DOMAIN', None)}")
            print(f"   📝 SESSION_COOKIE_PATH: {app.config.get('SESSION_COOKIE_PATH', '/')}")
            print(f"   📝 PERMANENT_SESSION_LIFETIME: {app.config.get('PERMANENT_SESSION_LIFETIME', 'Not set')}")
    except Exception as e:
        print(f"   ❌ Error loading Flask app: {e}")
    
    print("\n3. Process Information:")
    print(f"   📝 Python Version: {sys.version}")
    print(f"   📝 Current Working Directory: {os.getcwd()}")
    print(f"   📝 Script Directory: {os.path.dirname(os.path.abspath(__file__))}")
    
    print("\n4. Network Configuration:")
    try:
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        print(f"   📝 Hostname: {hostname}")
        print(f"   📝 Local IP: {local_ip}")
    except Exception as e:
        print(f"   ❌ Error getting network info: {e}")
    
    print("\n5. Gunicorn/Production Checks:")
    if 'gunicorn' in sys.modules:
        print("   ✅ Running under Gunicorn")
    else:
        print("   📝 Not running under Gunicorn (development mode)")
    
    if os.getenv('SERVER_SOFTWARE'):
        print(f"   📝 Server Software: {os.getenv('SERVER_SOFTWARE')}")
    
    print("\n=== Recommendations ===")
    print("If sessions are not working in production:")
    print("1. Ensure SECRET_KEY is set and consistent across restarts")
    print("2. Check if nginx is properly forwarding headers")
    print("3. Verify that 'credentials: include' is added to fetch requests")
    print("4. Restart the application after configuration changes")
    print("5. Clear browser cookies and try again")

if __name__ == "__main__":
    check_environment() 