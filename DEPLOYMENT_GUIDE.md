# GermanATO Code Changes Deployment Guide

This guide will help you deploy the recent code changes to your Ubuntu server to fix the duplicate plate number issue and make all fields optional.

## What We Fixed

1.  **Removed duplicate plate number validation** from `car_routes.py`
2.  **Made customer and car fields truly optional** in the backend
3.  **Updated database models** to allow nullable fields
4.  **Fixed phone number validation** to only validate when values are provided
5.  **Restricted accountant role access** to reports and analytics (admin only)

## Files Modified

- `backend/car_routes.py` - Removed duplicate plate number checks
- `backend/routes.py` - Fixed phone validation for optional fields
- `backend/models.py` - Made fields nullable
- `backend/static/js/auth.js` - Restricted accountant access to reports
- `backend/frontend/home.html` - Removed reports button for accountants
- `backend/reports_routes.py` - Added admin-only access control
- Frontend files - Made fields optional and added "N/A" defaults

## Deployment Steps

### Option 1: Using the Deployment Script (Recommended)

1.  **Copy the deployment script to your Ubuntu server:**

    ```bash
    scp deploy_code_changes.sh user@your-server-ip:/tmp/
    ```

2.  **SSH into your Ubuntu server:**

    ```bash
    ssh user@your-server-ip
    ```

3.  **Run the deployment script:**
    ```bash
    sudo bash /tmp/deploy_code_changes.sh
    ```

### Option 2: Manual Deployment

1.  **SSH into your Ubuntu server:**

    ```bash
    ssh user@your-server-ip
    ```

2.  **Create a backup:**

    ```bash
    sudo cp -r /opt/germanato/backend /opt/germanato/backups/$(date +%Y%m%d_%H%M%S)
    ```

3.  **Copy the updated backend files:**

    ```bash
    # From your local machine, copy the backend directory
    scp -r backend/* user@your-server-ip:/tmp/backend-update/

    # On the server, copy the files
    sudo cp -r /tmp/backend-update/* /opt/germanato/backend/
    ```

4.  **Set proper permissions:**

    ```bash
    sudo chown -R germanato:germanato /opt/germanato
    sudo chmod -R 755 /opt/germanato
    ```

5.  **Restart the service:**
    ```bash
    sudo systemctl restart germanato
    sudo systemctl restart nginx
    ```

## Database Schema Changes

**Important:** After deploying the code changes, you must also apply database schema changes to make fields nullable and remove unique constraints.

### Option 1: Using the Database Script (Recommended)

1.  **Copy the database script to your Ubuntu server:**

    ```bash
    scp apply_database_changes.sh user@your-server-ip:/tmp/
    ```

2.  **SSH into your Ubuntu server:**

    ```bash
    ssh user@your-server-ip
    ```

3.  **Run the database script:**
    ```bash
    sudo bash /tmp/apply_database_changes.sh
    ```

### Option 2: Manual Database Changes

If you prefer to run the database changes manually:

1.  **SSH into your Ubuntu server and access MySQL:**

    ```bash
    ssh user@your-server-ip
    sudo mysql -u root -p
    ```

2.  **Select your database:**

    ```sql
    USE your_database_name;
    ```

3.  **Run the schema changes:**

    ```sql
    -- Make customer fields nullable
    ALTER TABLE customer MODIFY COLUMN name VARCHAR(255) NULL;
    ALTER TABLE customer MODIFY COLUMN phone VARCHAR(20) NULL;
    ALTER TABLE customer MODIFY COLUMN address VARCHAR(255) NULL;

    -- Make car fields nullable
    ALTER TABLE car MODIFY COLUMN customer_id INT NULL;
    ALTER TABLE car MODIFY COLUMN make VARCHAR(100) NULL;
    ALTER TABLE car MODIFY COLUMN model VARCHAR(100) NULL;
    ALTER TABLE car MODIFY COLUMN plate_no VARCHAR(20) NULL;
    ALTER TABLE car MODIFY COLUMN mileage VARCHAR(50) NULL;
    ALTER TABLE car MODIFY COLUMN vin VARCHAR(100) NULL;
    ALTER TABLE car MODIFY COLUMN color VARCHAR(50) NULL;
    ALTER TABLE car MODIFY COLUMN chasis_no VARCHAR(100) NULL;

    -- Remove unique constraint on plate_no (if it exists)
    -- First, find the constraint name
    SET @constraint_name = (
        SELECT CONSTRAINT_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'car'
        AND COLUMN_NAME = 'plate_no'
        AND CONSTRAINT_NAME != 'PRIMARY'
        LIMIT 1
    );

    -- Drop the constraint if found
    SET @sql = IF(@constraint_name IS NOT NULL,
        CONCAT('ALTER TABLE car DROP INDEX ', @constraint_name),
        'SELECT "No unique constraint found on plate_no" as message'
    );
    PREPARE stmt FROM @sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
    ```

## Complete Deployment Process

For a complete deployment, follow these steps in order:

1.  **Deploy code changes:**

    ```bash
    sudo bash /tmp/deploy_code_changes.sh
    ```

2.  **Apply database schema changes:**

    ```bash
    sudo bash /tmp/apply_database_changes.sh
    ```

3.  **Verify everything is working:**
    - Check service status
    - Test the application
    - Monitor logs

## Verification

After deployment, verify that:

1.  **The service is running:**

    ```bash
    sudo systemctl status germanato
    ```

2.  **Check the logs for any errors:**

    ```bash
    sudo journalctl -u germanato -f
    ```

3.  **Test the application:**
    - Try to create a car with a duplicate plate number
    - Try to create a customer with empty fields
    - Verify that "N/A" values are accepted

## Testing the Fixes

1.  **Test Duplicate Plate Numbers:**

    - Create a car with plate number "ABC123"
    - Try to create another car with the same plate number "ABC123"
    - It should now succeed instead of giving the "already exists" error

2.  **Test Optional Fields:**

    - Create a customer with only a name (leave phone and address empty)
    - Create a car with only a make and model (leave other fields empty)
    - These should now succeed

3.  **Test Phone Validation:**

    - Try to create an invoice with empty phone number
    - It should now accept "N/A" or empty values

4.  **Test Role-Based Access Control:**
    - Login as an accountant user
    - Verify that the "Reports & Analytics" button is not visible on the home page
    - Try to access reports.html directly - it should show an access denied message
    - Login as an admin user and verify that reports are accessible

## Rollback (If Needed)

If something goes wrong, you can rollback:

```bash
# List available backups
ls -la /opt/germanato/backups/

# Restore from backup
sudo cp -r /opt/germanato/backups/YYYYMMDD_HHMMSS/* /opt/germanato/backend/
sudo chown -R germanato:germanato /opt/germanato
sudo systemctl restart germanato
```

**For database rollback:**

```bash
# Restore database from backup
sudo mysql -u root -p your_database_name < /opt/germanato/backups/database_backup_YYYYMMDD_HHMMSS.sql
```

## Troubleshooting

### Service Won't Start

```bash
# Check service status
sudo systemctl status germanato

# Check logs
sudo journalctl -u germanato -f

# Check file permissions
ls -la /opt/germanato/backend/
```

### Permission Issues

```bash
# Fix ownership
sudo chown -R germanato:germanato /opt/germanato

# Fix permissions
sudo chmod -R 755 /opt/germanato
```

### Database Connection Issues

```bash
# Check if MySQL is running
sudo systemctl status mysql

# Check database connection
sudo -u germanato bash -c "cd /opt/germanato/backend && source env/bin/activate && python -c 'from app import app; print(\"App imported successfully\")'"
```

### Database Schema Issues

```bash
# Check table structure
sudo mysql -u root -p -e "DESCRIBE your_database_name.customer; DESCRIBE your_database_name.car;"

# Check for unique constraints
sudo mysql -u root -p -e "SELECT CONSTRAINT_NAME, TABLE_NAME, COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA = 'your_database_name' AND TABLE_NAME IN ('customer', 'car');"
```

## Summary of Changes

The main changes deployed are:

1.  **Backend Validation:** Removed duplicate plate number checks
2.  **Database Models:** Made fields nullable (already done via database scripts)
3.  **Frontend:** Made all fields optional with "N/A" defaults
4.  **Phone Validation:** Only validates when actual values are provided
5.  **Database Schema:** Made customer and car fields nullable, removed unique constraints
6.  **Role-Based Access Control:** Restricted accountant role from accessing reports and analytics

After deployment, your application should:

- Allow duplicate plate numbers
- Accept empty fields (stored as "N/A")
- Handle optional customer and car creation
- Work without strict phone number format requirements for empty fields
- Restrict accountants from viewing business reports and analytics (admin only)

## Next Steps

1.  Deploy the changes using one of the methods above
2.  Apply the database schema changes
3.  Test the application thoroughly
4.  Monitor logs for any new issues
5.  Update your team about the changes

If you encounter any issues during deployment, check the logs and refer to the troubleshooting section above.
