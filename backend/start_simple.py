#!/usr/bin/env python3
"""
Simple Startup Script for GermanATO Auto Trader
Direct Flask startup without Gunicorn
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    from app import app
    
    print("🚀 Starting GermanATO with Flask...")
    print("📁 Working Directory:", current_dir)
    print("=" * 50)
    
    # Configure for production
    app.config['ENV'] = 'production'
    app.config['DEBUG'] = False
    
    # Start Flask app
    app.run(host='127.0.0.1', port=5000, debug=False)
    
except Exception as e:
    print(f"❌ Error starting Flask app: {e}")
    sys.exit(1) 