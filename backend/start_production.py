#!/usr/bin/env python3
"""
Production Startup Script for GermanATO Auto Trader
Starts the application with Gunicorn in production mode
"""

import os
import sys
import subprocess
import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def check_dependencies():
    """Check if required dependencies are available"""
    try:
        import flask
        import gunicorn
        import psycopg
        logger.info("✅ All required dependencies are available")
        return True
    except ImportError as e:
        logger.error(f"❌ Missing dependency: {e}")
        return False

def check_environment():
    """Check if environment is properly configured"""
    required_vars = ['DATABASE_URL', 'SECRET_KEY', 'JWT_SECRET_KEY']  # FLASK_APP is optional for local dev
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ Missing required environment variables: {missing_vars}")
        return False
    
    # Check optional FLASK_APP
    if not os.getenv('FLASK_APP'):
        logger.warning("⚠️  FLASK_APP not set, using default 'app.py'")
        os.environ['FLASK_APP'] = 'app.py'
    
    logger.info("✅ Environment variables are configured")
    return True

def start_gunicorn():
    """Start the application with Gunicorn"""
    
    # Get the current directory
    app_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(app_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    # Gunicorn command with fallback options
    cmd = [
        sys.executable, "-m", "gunicorn",
        "--bind", "0.0.0.0:5000",
        "--workers", "4",
        "--timeout", "30",
        "--access-logfile", os.path.join(logs_dir, "gunicorn_access.log"),
        "--error-logfile", os.path.join(logs_dir, "gunicorn_error.log"),
        "--log-level", "info",
        "wsgi:app"
    ]
    
    logger.info("🚀 Starting GermanATO with Gunicorn...")
    logger.info(f"📁 Working Directory: {app_dir}")
    logger.info(f"🔧 Command: {' '.join(cmd)}")
    logger.info("=" * 50)
    
    try:
        # Change to app directory
        os.chdir(app_dir)
        
        # Check dependencies
        if not check_dependencies():
            sys.exit(1)
        
        # Check environment
        if not check_environment():
            sys.exit(1)
        
        # Start Gunicorn
        subprocess.run(cmd, check=True)
        
    except KeyboardInterrupt:
        logger.info("👋 Shutting down GermanATO server...")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Error starting Gunicorn: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    start_gunicorn() 