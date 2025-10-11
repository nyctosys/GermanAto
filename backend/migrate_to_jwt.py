#!/usr/bin/env python3
"""
Migration script to ensure admin user exists for JWT authentication
"""
import sys
import os

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, User
from werkzeug.security import generate_password_hash

def migrate_to_jwt():
    """Ensure admin user exists for JWT authentication"""
    with app.app_context():
        try:
            # Check if admin user exists
            admin = User.query.filter_by(username='admin').first()
            
            if not admin:
                print("Creating admin user for JWT authentication...")
                
                # Create admin user
                admin = User(
                    username='admin',
                    email='admin@germanato.com',
                    role='admin',
                    is_active=True
                )
                admin.set_password('admin123')
                
                db.session.add(admin)
                db.session.commit()
                
                print("✅ Admin user created successfully!")
                print("   Username: admin")
                print("   Password: admin123")
                print("   Role: admin")
                
            else:
                print("✅ Admin user already exists")
                print(f"   Username: {admin.username}")
                print(f"   Email: {admin.email}")
                print(f"   Role: {admin.role}")
                print(f"   Active: {admin.is_active}")
            
            # Check for other users
            users = User.query.all()
            print(f"\n📊 Total users in database: {len(users)}")
            
            for user in users:
                print(f"   - {user.username} ({user.role}) - {'Active' if user.is_active else 'Inactive'}")
                
        except Exception as e:
            print(f"❌ Error during migration: {e}")
            db.session.rollback()

if __name__ == "__main__":
    migrate_to_jwt()
