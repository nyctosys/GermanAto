# Safe Database Migration Script

This script provides safe database schema changes for the Germanato App with backup, validation, and rollback capabilities.

## Features

- ✅ **Automatic Backup**: Creates full database backup before any changes
- ✅ **Schema Validation**: Validates current schema and new changes
- ✅ **Rollback Support**: Can restore database to previous state
- ✅ **Error Handling**: Comprehensive error checking and logging
- ✅ **Non-destructive**: Uses `IF NOT EXISTS` and safe ALTER statements
- ✅ **Performance Indexes**: Adds optimized indexes for better performance

## Prerequisites

- MySQL/MariaDB server running
- Database user with appropriate permissions
- `mysqldump` and `mysql` command-line tools installed

## Quick Start

1. **Make the script executable** (if not already):
   ```bash
   chmod +x safe_db_migration.sh
   ```

2. **Run the migration**:
   ```bash
   ./safe_db_migration.sh migrate
   ```

3. **Enter your MySQL password** when prompted

## Usage Options

### Apply Schema Changes (Default)
```bash
./safe_db_migration.sh migrate
```
- Creates backup
- Applies schema changes
- Validates changes
- Safe to run multiple times

### Create Backup Only
```bash
./safe_db_migration.sh backup
```
- Creates database backup without making changes
- Useful for regular backups

### Validate Current Schema
```bash
./safe_db_migration.sh validate
```
- Checks current database schema
- Reports missing columns/tables
- No changes made

### Rollback Changes
```bash
./safe_db_migration.sh rollback
```
- Restores database to state before last migration
- Requires confirmation
- Uses most recent backup

### Show Help
```bash
./safe_db_migration.sh help
```

## What the Migration Does

### 1. Adds Missing Columns
- `invoice.paid_amount` - Track payments received
- `inventory.image_path` - Store item images
- `repair_order.worker_id` - Link to worker records

### 2. Sets Safe Defaults
- `repair_order_part.price` - Default 0
- `repair_order_labour.rate` - Default 0

### 3. Adds Performance Indexes
- Invoice queries by type, status, date
- Inventory lookups by name
- Repair order status and date queries
- Expense and customer date filters

### 4. Creates Optional Tables
- `vendors` - Vendor management
- `vendor_ledger` - Financial tracking
- `vendor_consignments` - Goods received
- `workers` - HR management

## Safety Features

### Automatic Backup
- Full database backup before any changes
- Timestamped backup files
- Backup validation before proceeding

### Error Handling
- MySQL connection verification
- Schema validation before and after
- Rollback capability if issues occur
- Comprehensive logging

### Non-destructive Changes
- Uses `IF NOT EXISTS` for columns
- Safe ALTER statements
- No data loss
- Can be run multiple times safely

## File Structure

```
├── safe_db_migration.sh      # Main migration script
├── db_config.env.example     # Configuration template
├── db_backups/               # Backup directory (created automatically)
├── migration.log             # Migration log file
└── .last_backup              # Points to most recent backup
```

## Configuration

### Database Settings
Edit the script variables at the top:
```bash
DB_NAME="germanato_db"
DB_USER="root"
DB_HOST="localhost"
DB_PORT="3306"
```

### Backup Location
```bash
BACKUP_DIR="./db_backups"
```

## Troubleshooting

### Connection Issues
- Verify MySQL is running
- Check database credentials
- Ensure user has required permissions

### Permission Errors
- Grant necessary privileges to database user:
  ```sql
  GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, INDEX, ALTER ON germanato_db.* TO 'your_user'@'localhost';
  ```

### Backup Issues
- Ensure sufficient disk space
- Check write permissions to backup directory
- Verify mysqldump is installed

### Rollback Issues
- Check if backup file exists
- Verify backup file is not corrupted
- Ensure sufficient disk space for restore

## Log Files

All operations are logged to `migration.log`:
- Timestamps for all operations
- Success/error messages
- Validation results
- Backup file locations

## Best Practices

1. **Always backup before migration** (script does this automatically)
2. **Test on development environment first**
3. **Run during maintenance windows**
4. **Monitor application after migration**
5. **Keep backup files for at least 30 days**

## Support

If you encounter issues:
1. Check the migration log file
2. Verify database connectivity
3. Ensure proper permissions
4. Test with a small dataset first

## Example Output

```
[2024-01-15 10:30:00] Checking MySQL connection...
[SUCCESS] MySQL connection successful
[2024-01-15 10:30:01] Checking current database schema...
[SUCCESS] All critical tables exist
[2024-01-15 10:30:02] Creating database backup...
[SUCCESS] Backup created successfully: ./db_backups/germanato_db_backup_20240115_103002.sql
[2024-01-15 10:30:05] Applying schema changes...
[SUCCESS] Schema changes applied successfully
[2024-01-15 10:30:07] Validating schema changes...
[SUCCESS] invoice.paid_amount column added
[SUCCESS] inventory.image_path column added
[SUCCESS] repair_order.worker_id column added
[SUCCESS] Migration completed successfully!
```
