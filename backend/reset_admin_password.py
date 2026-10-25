#!/usr/bin/env python3
"""
Reset Admin Password Script
This script resets the admin password to use the new pbkdf2:sha256 hashing method
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
    from app import app, db
    from models import User
    
    with app.app_context():
        print("🔄 Resetting admin password with new hashing method...")
        
        # Find admin user
        admin_user = User.query.filter_by(username='admin').first()
        
        if admin_user:
            print(f"✅ Found admin user: {admin_user.username}")
            
            # Reset password with new hashing method
            admin_user.set_password('admin123')  # Default password
            db.session.commit()
            
            print("✅ Admin password reset successfully!")
            print("📝 Login credentials:")
            print("   Username: admin")
            print("   Password: admin123")
        else:
            print("❌ Admin user not found. Creating new admin user...")
            
            # Create new admin user
            admin_user = User(
                username='admin',
                email='admin@germanato.com',
                role='admin',
                is_active=True
            )
            admin_user.set_password('admin123')
            
            db.session.add(admin_user)
            db.session.commit()
            
            print("✅ New admin user created successfully!")
            print("📝 Login credentials:")
            print("   Username: admin")
            print("   Password: admin123")
            
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
