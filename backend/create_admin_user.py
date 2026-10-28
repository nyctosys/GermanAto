#!/usr/bin/env python3
"""
Create Admin User Script for GermanATO Auto Trader
Creates the initial admin user during deployment
"""

import os
import sys
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

# Load environment variables
load_dotenv()

def create_admin_user():
    """Create the initial admin user"""
    
    print("👤 Creating Admin User for GermanATO")
    print("=" * 40)
    
    try:
        # Import after environment is loaded
        from models import db, User
        from app import app
        
        with app.app_context():
            # Check if admin user already exists
            existing_admin = User.query.filter_by(username='admin').first()
            if existing_admin:
                print("✅ Admin user already exists")
                return True
            
            # Create admin user
            admin_user = User(
                username='admin',
                email='admin@germanato.com',
                password_hash=generate_password_hash('admin123', method='pbkdf2:sha256'),
                role='admin',
                is_active=True
            )
            
            db.session.add(admin_user)
            db.session.commit()
            
            print("✅ Admin user created successfully!")
            print("📋 Login Credentials:")
            print("   Username: admin")
            print("   Password: admin123")
            print("   Role: Administrator")
            print()
            print("⚠️  IMPORTANT: Change the password after first login!")
            
            return True
            
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        return False

def create_default_roles():
    """Create default user roles if they don't exist"""
    
    try:
        from models import db, User
        from app import app
        
        with app.app_context():
            # Create accountant user if it doesn't exist
            accountant = User.query.filter_by(username='accountant').first()
            if not accountant:
                accountant_user = User(
                    username='accountant',
                    email='accountant@germanato.com',
                    password_hash=generate_password_hash('accountant123', method='pbkdf2:sha256'),
                    role='accountant',
                    is_active=True
                )
                db.session.add(accountant_user)
                print("✅ Accountant user created")
            
            # Create inventory manager if it doesn't exist
            inventory = User.query.filter_by(username='inventory').first()
            if not inventory:
                inventory_user = User(
                    username='inventory',
                    email='inventory@germanato.com',
                    password_hash=generate_password_hash('inventory123', method='pbkdf2:sha256'),
                    role='inventory_manager',
                    is_active=True
                )
                db.session.add(inventory_user)
                print("✅ Inventory manager user created")
            
            db.session.commit()
            print("✅ Default users setup completed")
            
    except Exception as e:
        print(f"⚠️  Warning: Could not create default users: {e}")

if __name__ == "__main__":
    print("🚀 GermanATO User Setup")
    print("=" * 30)
    
    # Create admin user
    if create_admin_user():
        # Create default roles
        create_default_roles()
        print("\n🎉 User setup completed successfully!")
        print("📝 You can now log in with the admin credentials")
    else:
        print("\n❌ User setup failed!")
        sys.exit(1) 