#!/usr/bin/env python3
"""
Database Migration Script for Production
Adds missing 'notes' column to workers table
"""

import os
import sys
import pymysql
from datetime import datetime

def get_db_connection():
    """Get database connection using environment variables"""
    try:
        # Try to get database config from environment
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = int(os.getenv('DB_PORT', 3306))
        db_user = os.getenv('DB_USER', 'root')
        db_password = os.getenv('DB_PASSWORD', '')
        db_name = os.getenv('DB_NAME', 'germanato')
        
        print(f"Connecting to database: {db_host}:{db_port}/{db_name}")
        
        connection = pymysql.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database=db_name,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        
        return connection
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def check_column_exists(connection, table_name, column_name):
    """Check if a column exists in a table"""
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = '{table_name}' 
                AND COLUMN_NAME = '{column_name}'
            """)
            result = cursor.fetchone()
            return result is not None
    except Exception as e:
        print(f"Error checking column existence: {e}")
        return False

def add_notes_column(connection):
    """Add the missing notes column to workers table"""
    try:
        with connection.cursor() as cursor:
            # Check if notes column already exists
            if check_column_exists(connection, 'workers', 'notes'):
                print("✅ 'notes' column already exists in workers table")
                return True
            
            print("Adding 'notes' column to workers table...")
            
            # Add the notes column
            cursor.execute("""
                ALTER TABLE workers 
                ADD COLUMN notes TEXT NULL 
                AFTER emergency_contact_phone
            """)
            
            connection.commit()
            print("✅ Successfully added 'notes' column to workers table")
            return True
            
    except Exception as e:
        print(f"❌ Error adding notes column: {e}")
        connection.rollback()
        return False

def verify_migration(connection):
    """Verify that the migration was successful"""
    try:
        with connection.cursor() as cursor:
            # Check if notes column exists
            if check_column_exists(connection, 'workers', 'notes'):
                print("✅ Migration verification successful: 'notes' column exists")
                
                # Test a simple query to make sure it works
                cursor.execute("SELECT id, employee_id, first_name, last_name, notes FROM workers LIMIT 1")
                result = cursor.fetchone()
                print("✅ Test query successful - HR management should now work")
                return True
            else:
                print("❌ Migration verification failed: 'notes' column not found")
                return False
                
    except Exception as e:
        print(f"❌ Migration verification error: {e}")
        return False

def main():
    """Main migration function"""
    print("🚀 Starting database migration for HR management...")
    print(f"Timestamp: {datetime.now()}")
    print("-" * 50)
    
    # Get database connection
    connection = get_db_connection()
    if not connection:
        print("❌ Failed to connect to database. Please check your database configuration.")
        sys.exit(1)
    
    try:
        # Add the missing notes column
        if add_notes_column(connection):
            # Verify the migration
            if verify_migration(connection):
                print("\n🎉 Migration completed successfully!")
                print("HR management should now work properly in production.")
            else:
                print("\n❌ Migration verification failed!")
                sys.exit(1)
        else:
            print("\n❌ Migration failed!")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Unexpected error during migration: {e}")
        sys.exit(1)
    finally:
        connection.close()

if __name__ == "__main__":
    main()
