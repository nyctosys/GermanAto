#!/usr/bin/env python3
"""
Fix CashReceived table by dropping and recreating it with correct structure
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, CashReceived

def fix_cash_received_table():
    """Drop and recreate CashReceived table with correct structure"""
    with app.app_context():
        try:
            # Drop the existing CashReceived table
            db.session.execute(db.text("DROP TABLE IF EXISTS cash_received"))
            db.session.commit()
            print("✅ Dropped existing cash_received table")
            
            # Create the table with correct structure
            db.create_all()
            print("✅ Created cash_received table with correct structure")
            
            # Verify the table was created correctly
            result = db.session.execute(db.text("SHOW TABLES LIKE 'cash_received'"))
            if result.fetchone():
                print("✅ CashReceived table verified in database")
                
                # Check table structure
                result = db.session.execute(db.text("DESCRIBE cash_received"))
                columns = result.fetchall()
                print("📋 Table structure:")
                for column in columns:
                    print(f"   - {column[0]} ({column[1]})")
            else:
                print("❌ CashReceived table not found in database")
                return False
                
        except Exception as e:
            print(f"❌ Error fixing CashReceived table: {e}")
            db.session.rollback()
            return False
    
    return True

if __name__ == "__main__":
    print("🔄 Fixing CashReceived table structure...")
    if fix_cash_received_table():
        print("🎉 Table fix completed successfully!")
    else:
        print("💥 Table fix failed!")
        sys.exit(1)
