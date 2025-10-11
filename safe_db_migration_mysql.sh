#!/bin/bash

# Safe Database Migration Script for Germanato App - MySQL 8.0 Compatible
# This script provides safe database schema changes with backup, validation, and rollback capabilities

set -e  # Exit on any error

# Configuration
DB_NAME="germanato_db"
DB_USER="root"
DB_HOST="localhost"
DB_PORT="3306"
BACKUP_DIR="./db_backups"
LOG_FILE="./migration.log"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/germanato_db_backup_${TIMESTAMP}.sql"

# MySQL connection options
MYSQL_OPTS="-h $DB_HOST -P $DB_PORT -u $DB_USER"
MYSQLDUMP_OPTS="-h $DB_HOST -P $DB_PORT -u $DB_USER --single-transaction --routines --triggers --add-drop-database"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

# Function to check if MySQL is running
check_mysql() {
    log "Checking MySQL connection..."
    if ! mysql $MYSQL_OPTS -p -e "SELECT 1;" > /dev/null 2>&1; then
        error "Cannot connect to MySQL. Please check your credentials and ensure MySQL is running."
        exit 1
    fi
    success "MySQL connection successful"
}

# Function to create backup directory
create_backup_dir() {
    if [ ! -d "$BACKUP_DIR" ]; then
        mkdir -p "$BACKUP_DIR"
        log "Created backup directory: $BACKUP_DIR"
    fi
}

# Function to create database backup
create_backup() {
    log "Creating database backup..."
    create_backup_dir
    
    if mysqldump $MYSQLDUMP_OPTS --databases "$DB_NAME" > "$BACKUP_FILE" 2>/dev/null; then
        success "Backup created successfully: $BACKUP_FILE"
        echo "$BACKUP_FILE" > .last_backup
    else
        error "Failed to create backup. Aborting migration."
        exit 1
    fi
}

# Function to validate backup
validate_backup() {
    log "Validating backup file..."
    if [ ! -f "$BACKUP_FILE" ]; then
        error "Backup file not found: $BACKUP_FILE"
        exit 1
    fi
    
    if [ ! -s "$BACKUP_FILE" ]; then
        error "Backup file is empty: $BACKUP_FILE"
        exit 1
    fi
    
    # Check if backup contains expected tables
    if grep -q "CREATE TABLE.*invoice" "$BACKUP_FILE" && \
       grep -q "CREATE TABLE.*inventory" "$BACKUP_FILE" && \
       grep -q "CREATE TABLE.*repair_order" "$BACKUP_FILE"; then
        success "Backup validation successful"
    else
        error "Backup validation failed - missing critical tables"
        exit 1
    fi
}

# Function to check current database schema
check_current_schema() {
    log "Checking current database schema..."
    
    # Check if required tables exist
    local tables=("invoice" "inventory" "repair_order" "customer" "car" "expense" "cash_received" "user" "whats_app_notification")
    local missing_tables=()
    
    for table in "${tables[@]}"; do
        if ! mysql $MYSQL_OPTS -p -e "USE $DB_NAME; DESCRIBE $table;" > /dev/null 2>&1; then
            missing_tables+=("$table")
        fi
    done
    
    if [ ${#missing_tables[@]} -gt 0 ]; then
        error "Missing critical tables: ${missing_tables[*]}"
        exit 1
    fi
    
    success "All critical tables exist"
}

# Function to apply schema changes
apply_schema_changes() {
    log "Applying schema changes..."
    
    # Create temporary SQL file for all changes
    local sql_file="/tmp/migration_${TIMESTAMP}.sql"
    
    cat > "$sql_file" << 'EOF'
-- Safe Database Migration for Germanato App - MySQL 8.0 Compatible
-- Adding missing columns and indexes

-- 1) Add missing columns expected by the app (with error handling)
SET @sql = 'ALTER TABLE invoice ADD COLUMN paid_amount FLOAT NULL DEFAULT 0 AFTER tax_amount';
SET @sql_check = 'SELECT COUNT(*) INTO @col_exists FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ''invoice'' AND COLUMN_NAME = ''paid_amount''';
PREPARE stmt FROM @sql_check;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(@col_exists = 0, @sql, 'SELECT ''Column paid_amount already exists'' as message');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = 'ALTER TABLE inventory ADD COLUMN image_path VARCHAR(255) NULL AFTER reorder_quantity';
SET @sql_check = 'SELECT COUNT(*) INTO @col_exists FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ''inventory'' AND COLUMN_NAME = ''image_path''';
PREPARE stmt FROM @sql_check;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(@col_exists = 0, @sql, 'SELECT ''Column image_path already exists'' as message');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = 'ALTER TABLE repair_order ADD COLUMN worker_id INT NULL AFTER diagnosis_plan';
SET @sql_check = 'SELECT COUNT(*) INTO @col_exists FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ''repair_order'' AND COLUMN_NAME = ''worker_id''';
PREPARE stmt FROM @sql_check;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(@col_exists = 0, @sql, 'SELECT ''Column worker_id already exists'' as message');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2) Make columns safe to omit on insert (set defaults)
ALTER TABLE repair_order_part MODIFY COLUMN price FLOAT NOT NULL DEFAULT 0;
ALTER TABLE repair_order_labour MODIFY COLUMN rate FLOAT NOT NULL DEFAULT 0;

-- 3) Add performance indexes (with error handling)
SET @sql = 'CREATE INDEX idx_invoice_type_status_date ON invoice (type_of, status, created_at)';
SET @sql_check = 'SELECT COUNT(*) INTO @idx_exists FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ''invoice'' AND INDEX_NAME = ''idx_invoice_type_status_date''';
PREPARE stmt FROM @sql_check;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(@idx_exists = 0, @sql, 'SELECT ''Index idx_invoice_type_status_date already exists'' as message');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = 'CREATE INDEX idx_invoice_created_at ON invoice (created_at)';
SET @sql_check = 'SELECT COUNT(*) INTO @idx_exists FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ''invoice'' AND INDEX_NAME = ''idx_invoice_created_at''';
PREPARE stmt FROM @sql_check;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(@idx_exists = 0, @sql, 'SELECT ''Index idx_invoice_created_at already exists'' as message');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = 'CREATE INDEX idx_inventory_name ON inventory (name)';
SET @sql_check = 'SELECT COUNT(*) INTO @idx_exists FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ''inventory'' AND INDEX_NAME = ''idx_inventory_name''';
PREPARE stmt FROM @sql_check;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(@idx_exists = 0, @sql, 'SELECT ''Index idx_inventory_name already exists'' as message');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = 'CREATE INDEX idx_repair_order_status ON repair_order (current_status)';
SET @sql_check = 'SELECT COUNT(*) INTO @idx_exists FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ''repair_order'' AND INDEX_NAME = ''idx_repair_order_status''';
PREPARE stmt FROM @sql_check;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(@idx_exists = 0, @sql, 'SELECT ''Index idx_repair_order_status already exists'' as message');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = 'CREATE INDEX idx_repair_order_created_at ON repair_order (created_at)';
SET @sql_check = 'SELECT COUNT(*) INTO @idx_exists FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ''repair_order'' AND INDEX_NAME = ''idx_repair_order_created_at''';
PREPARE stmt FROM @sql_check;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(@idx_exists = 0, @sql, 'SELECT ''Index idx_repair_order_created_at already exists'' as message');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = 'CREATE INDEX idx_expense_date ON expense (date)';
SET @sql_check = 'SELECT COUNT(*) INTO @idx_exists FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ''expense'' AND INDEX_NAME = ''idx_expense_date''';
PREPARE stmt FROM @sql_check;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(@idx_exists = 0, @sql, 'SELECT ''Index idx_expense_date already exists'' as message');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = 'CREATE INDEX idx_customer_created_at ON customer (created_at)';
SET @sql_check = 'SELECT COUNT(*) INTO @idx_exists FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ''customer'' AND INDEX_NAME = ''idx_customer_created_at''';
PREPARE stmt FROM @sql_check;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(@idx_exists = 0, @sql, 'SELECT ''Index idx_customer_created_at already exists'' as message');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = 'CREATE INDEX idx_car_created_at ON car (created_at)';
SET @sql_check = 'SELECT COUNT(*) INTO @idx_exists FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ''car'' AND INDEX_NAME = ''idx_car_created_at''';
PREPARE stmt FROM @sql_check;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(@idx_exists = 0, @sql, 'SELECT ''Index idx_car_created_at already exists'' as message');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 4) Create optional tables for Vendors/HR features (with error handling)
SET @sql = 'CREATE TABLE vendors (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL,
  company_name VARCHAR(255) NOT NULL,
  contact_person VARCHAR(255) NOT NULL,
  phone VARCHAR(20) NOT NULL,
  email VARCHAR(255) NULL,
  address TEXT NOT NULL,
  cnic VARCHAR(20) NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)';
SET @sql_check = 'SELECT COUNT(*) INTO @table_exists FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ''vendors''';
PREPARE stmt FROM @sql_check;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(@table_exists = 0, @sql, 'SELECT ''Table vendors already exists'' as message');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = 'CREATE TABLE vendor_ledger (
  id INT PRIMARY KEY AUTO_INCREMENT,
  vendor_id INT NOT NULL,
  date DATE NOT NULL,
  description VARCHAR(500) NOT NULL,
  folio VARCHAR(100) NULL,
  debit DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  credit DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  balance DECIMAL(10,2) NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX (vendor_id),
  CONSTRAINT fk_vendor_ledger_vendor FOREIGN KEY (vendor_id) REFERENCES vendors(id)
)';
SET @sql_check = 'SELECT COUNT(*) INTO @table_exists FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ''vendor_ledger''';
PREPARE stmt FROM @sql_check;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(@table_exists = 0, @sql, 'SELECT ''Table vendor_ledger already exists'' as message');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = 'CREATE TABLE vendor_consignments (
  id INT PRIMARY KEY AUTO_INCREMENT,
  vendor_id INT NOT NULL,
  date DATE NOT NULL,
  invoice_no VARCHAR(100) NOT NULL,
  item_name VARCHAR(255) NOT NULL,
  quantity INT NOT NULL,
  rate DECIMAL(10,2) NOT NULL,
  amount DECIMAL(10,2) NOT NULL,
  remarks TEXT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX (vendor_id),
  CONSTRAINT fk_vendor_consignments_vendor FOREIGN KEY (vendor_id) REFERENCES vendors(id)
)';
SET @sql_check = 'SELECT COUNT(*) INTO @table_exists FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ''vendor_consignments''';
PREPARE stmt FROM @sql_check;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(@table_exists = 0, @sql, 'SELECT ''Table vendor_consignments already exists'' as message');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = 'CREATE TABLE workers (
  id INT PRIMARY KEY AUTO_INCREMENT,
  employee_id VARCHAR(20) NOT NULL UNIQUE,
  first_name VARCHAR(100) NOT NULL,
  last_name VARCHAR(100) NOT NULL,
  email VARCHAR(255) NULL,
  phone VARCHAR(20) NOT NULL,
  address TEXT NOT NULL,
  cnic VARCHAR(20) NOT NULL UNIQUE,
  date_of_birth DATE NOT NULL,
  hire_date DATE NOT NULL,
  position VARCHAR(100) NOT NULL,
  department VARCHAR(100) NOT NULL,
  salary DECIMAL(10,2) NULL,
  status VARCHAR(20) NOT NULL DEFAULT ''active'',
  emergency_contact_name VARCHAR(100) NULL,
  emergency_contact_phone VARCHAR(20) NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)';
SET @sql_check = 'SELECT COUNT(*) INTO @table_exists FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ''workers''';
PREPARE stmt FROM @sql_check;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(@table_exists = 0, @sql, 'SELECT ''Table workers already exists'' as message');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 5) Verify changes
SELECT 'Migration completed successfully' as status;
EOF

    # Execute the migration
    if mysql $MYSQL_OPTS -p "$DB_NAME" < "$sql_file"; then
        success "Schema changes applied successfully"
        rm -f "$sql_file"
    else
        error "Failed to apply schema changes"
        rm -f "$sql_file"
        exit 1
    fi
}

# Function to validate schema changes
validate_schema_changes() {
    log "Validating schema changes..."
    
    # Check if new columns were added
    if mysql $MYSQL_OPTS -p -e "USE $DB_NAME; DESCRIBE invoice;" | grep -q "paid_amount"; then
        success "invoice.paid_amount column added"
    else
        error "invoice.paid_amount column not found"
        return 1
    fi
    
    if mysql $MYSQL_OPTS -p -e "USE $DB_NAME; DESCRIBE inventory;" | grep -q "image_path"; then
        success "inventory.image_path column added"
    else
        error "inventory.image_path column not found"
        return 1
    fi
    
    if mysql $MYSQL_OPTS -p -e "USE $DB_NAME; DESCRIBE repair_order;" | grep -q "worker_id"; then
        success "repair_order.worker_id column added"
    else
        error "repair_order.worker_id column not found"
        return 1
    fi
    
    # Check if new tables were created
    if mysql $MYSQL_OPTS -p -e "USE $DB_NAME; SHOW TABLES LIKE 'vendors';" | grep -q "vendors"; then
        success "vendors table created"
    else
        warning "vendors table not created (optional)"
    fi
    
    if mysql $MYSQL_OPTS -p -e "USE $DB_NAME; SHOW TABLES LIKE 'workers';" | grep -q "workers"; then
        success "workers table created"
    else
        warning "workers table not created (optional)"
    fi
    
    success "Schema validation completed"
}

# Function to rollback changes
rollback() {
    log "Rolling back changes..."
    
    if [ ! -f ".last_backup" ]; then
        error "No backup file found for rollback"
        exit 1
    fi
    
    local backup_file=$(cat .last_backup)
    
    if [ ! -f "$backup_file" ]; then
        error "Backup file not found: $backup_file"
        exit 1
    fi
    
    warning "This will restore the database to the state before migration."
    read -p "Are you sure you want to rollback? (yes/no): " confirm
    
    if [ "$confirm" = "yes" ]; then
        if mysql $MYSQL_OPTS -p < "$backup_file"; then
            success "Database rollback completed successfully"
        else
            error "Database rollback failed"
            exit 1
        fi
    else
        log "Rollback cancelled by user"
    fi
}

# Function to show help
show_help() {
    echo "Safe Database Migration Script for Germanato App - MySQL 8.0 Compatible"
    echo ""
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  migrate    Apply database schema changes (default)"
    echo "  rollback   Rollback to previous state"
    echo "  validate   Validate current schema"
    echo "  backup     Create backup only"
    echo "  help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 migrate    # Apply schema changes"
    echo "  $0 rollback    # Rollback changes"
    echo "  $0 validate    # Validate schema"
    echo "  $0 backup      # Create backup only"
}

# Function to run migration
run_migration() {
    log "Starting safe database migration..."
    
    check_mysql
    check_current_schema
    create_backup
    validate_backup
    apply_schema_changes
    validate_schema_changes
    
    success "Migration completed successfully!"
    log "Backup file: $BACKUP_FILE"
    log "Log file: $LOG_FILE"
}

# Function to validate current schema
run_validation() {
    log "Validating current database schema..."
    
    check_mysql
    check_current_schema
    
    # Check for expected columns
    log "Checking for expected columns..."
    
    if mysql $MYSQL_OPTS -p -e "USE $DB_NAME; DESCRIBE invoice;" | grep -q "paid_amount"; then
        success "invoice.paid_amount exists"
    else
        warning "invoice.paid_amount missing"
    fi
    
    if mysql $MYSQL_OPTS -p -e "USE $DB_NAME; DESCRIBE inventory;" | grep -q "image_path"; then
        success "inventory.image_path exists"
    else
        warning "inventory.image_path missing"
    fi
    
    if mysql $MYSQL_OPTS -p -e "USE $DB_NAME; DESCRIBE repair_order;" | grep -q "worker_id"; then
        success "repair_order.worker_id exists"
    else
        warning "repair_order.worker_id missing"
    fi
    
    success "Schema validation completed"
}

# Main script logic
main() {
    case "${1:-migrate}" in
        "migrate")
            run_migration
            ;;
        "rollback")
            rollback
            ;;
        "validate")
            run_validation
            ;;
        "backup")
            check_mysql
            create_backup
            validate_backup
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
