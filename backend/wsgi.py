#!/usr/bin/env python3
"""
WSGI Entry Point for GermanATO Auto Trader
Production WSGI application for Gunicorn
"""

import os
import sys
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

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    # Import the Flask app
    from app import app, db
    
    # Configure for production
    app.config['ENV'] = 'production'
    app.config['DEBUG'] = False
    
    logger.info("✅ Flask app imported successfully")
    
    # Test database connection
    with app.app_context():
        try:
            # Use the newer SQLAlchemy syntax
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            db.session.commit()
            logger.info("✅ Database connection successful")
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
    
except Exception as e:
    logger.error(f"❌ Error importing Flask app: {e}")
    raise

if __name__ == "__main__":
    # For development only
    app.run(host='0.0.0.0', port=5000, debug=False) 