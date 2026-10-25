#!/bin/bash
# Production Database Migration Script for HR Management
# Fixes missing 'notes' column in workers table

echo "🚀 Starting HR Database Migration..."
echo "Timestamp: $(date)"
echo "----------------------------------------"

# Check if we're in the right directory
if [ ! -f "backend/models.py" ]; then
    echo "❌ Please run this script from the project root directory"
    exit 1
fi

# Check if Python virtual environment exists
if [ ! -d "backend/env" ]; then
    echo "❌ Python virtual environment not found at backend/env"
    echo "Please run: cd backend && python3 -m venv env && source env/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment and run migration
echo "📦 Activating virtual environment..."
cd backend
source env/bin/activate

# Install pymysql if not already installed
echo "🔧 Installing required packages..."
pip install pymysql > /dev/null 2>&1

# Run the migration script
echo "🔄 Running database migration..."
python3 ../fix_hr_database_migration.py

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Migration completed successfully!"
    echo "🔄 Restarting Gunicorn to apply changes..."
    
    # Restart gunicorn if it's running
    if pgrep -f "gunicorn.*app:app" > /dev/null; then
        echo "🔄 Restarting Gunicorn process..."
        pkill -f "gunicorn.*app:app"
        sleep 2
        
        # Start gunicorn in background
        nohup gunicorn --bind 0.0.0.0:5001 --workers 4 --timeout 120 app:app > /var/log/gunicorn.log 2>&1 &
        echo "✅ Gunicorn restarted successfully"
    else
        echo "ℹ️  Gunicorn not running, you may need to start it manually"
    fi
    
    echo ""
    echo "🎉 HR Management should now work properly!"
    echo "You can test by accessing the HR management page."
    
else
    echo ""
    echo "❌ Migration failed! Please check the error messages above."
    echo "You may need to manually add the 'notes' column to the workers table:"
    echo "ALTER TABLE workers ADD COLUMN notes TEXT NULL AFTER emergency_contact_phone;"
    exit 1
fi

echo ""
echo "Migration completed at: $(date)"
