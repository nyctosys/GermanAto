#!/bin/bash

# GermanATO Database Optimization Script
# Ubuntu 24.04 LTS - 16GB RAM, 12 cores, MySQL optimization

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration variables
MYSQL_CONF="/etc/mysql/mysql.conf.d/mysqld.cnf"
MYSQL_CONF_DIR="/etc/mysql/mysql.conf.d"
BACKUP_DIR="/opt/germanato/backups"
DB_NAME="germanato_db"
DB_USER="germanato_user"
DB_PASS="germanato_password_2024"

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use sudo)"
    fi
}

# Check system requirements
check_system() {
    log "Checking system requirements..."
    
    # Check if MySQL is installed
    if ! command -v mysql &> /dev/null; then
        error "MySQL is not installed. Please install it first: sudo apt install mysql-server"
    fi
    
    # Check MySQL version
    MYSQL_VERSION=$(mysql --version | awk '{print $5}' | cut -d',' -f1)
    log "MySQL version: $MYSQL_VERSION"
    
    # Check available RAM
    RAM_GB=$(free -g | awk '/^Mem:/{print $2}')
    log "Available RAM: ${RAM_GB}GB"
    
    # Check CPU cores
    CPU_CORES=$(nproc)
    log "CPU cores: $CPU_CORES"
    
    # Check if MySQL is running
    if ! sudo systemctl is-active --quiet mysql; then
        error "MySQL service is not running. Please start it first: sudo systemctl start mysql"
    fi
    
    log "System requirements check completed"
}

# Backup current MySQL configuration
backup_config() {
    log "Backing up current MySQL configuration..."
    
    # Create backup directory
    sudo mkdir -p "$BACKUP_DIR"
    
    # Backup MySQL configuration
    if [ -f "$MYSQL_CONF" ]; then
        sudo cp "$MYSQL_CONF" "$BACKUP_DIR/mysqld.cnf.backup.$(date +%Y%m%d_%H%M%S)"
        log "MySQL configuration backed up"
    else
        warning "MySQL configuration file not found at $MYSQL_CONF"
    fi
    
    # Backup all MySQL config files
    sudo cp -r "$MYSQL_CONF_DIR" "$BACKUP_DIR/mysql.conf.backup.$(date +%Y%m%d_%H%M%S)"
    
    log "Configuration backup completed"
}

# Create optimized MySQL configuration
create_optimized_config() {
    log "Creating optimized MySQL configuration..."
    
    # Calculate optimal settings based on 16GB RAM
    INNODB_BUFFER_POOL_SIZE="8G"  # 50% of RAM
    INNODB_LOG_FILE_SIZE="256M"
    QUERY_CACHE_SIZE="128M"
    MAX_CONNECTIONS="200"
    THREAD_CACHE_SIZE="16"
    TABLE_OPEN_CACHE="4000"
    SORT_BUFFER_SIZE="2M"
    READ_BUFFER_SIZE="2M"
    READ_RND_BUFFER_SIZE="8M"
    MYISAM_SORT_BUFFER_SIZE="64M"
    KEY_BUFFER_SIZE="256M"
    
    # Create optimized mysqld.cnf
    cat > /tmp/mysqld.cnf << EOF
[mysqld]
# Basic Settings
pid-file = /var/run/mysqld/mysqld.pid
socket = /var/run/mysqld/mysqld.sock
datadir = /var/lib/mysql
log-error = /var/log/mysql/error.log

# Character Set
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci

# Connection Settings
max_connections = $MAX_CONNECTIONS
max_connect_errors = 1000000
thread_cache_size = $THREAD_CACHE_SIZE
table_open_cache = $TABLE_OPEN_CACHE
table_definition_cache = 2000

# Buffer Settings
sort_buffer_size = $SORT_BUFFER_SIZE
read_buffer_size = $READ_BUFFER_SIZE
read_rnd_buffer_size = $READ_RND_BUFFER_SIZE
myisam_sort_buffer_size = $MYISAM_SORT_BUFFER_SIZE
key_buffer_size = $KEY_BUFFER_SIZE

# InnoDB Settings (Primary Storage Engine)
default_storage_engine = InnoDB
innodb_buffer_pool_size = $INNODB_BUFFER_POOL_SIZE
innodb_log_file_size = $INNODB_LOG_FILE_SIZE
innodb_log_buffer_size = 64M
innodb_flush_log_at_trx_commit = 2
innodb_flush_method = O_DIRECT
innodb_file_per_table = 1
innodb_open_files = 4000
innodb_io_capacity = 2000
innodb_io_capacity_max = 4000
innodb_read_io_threads = 8
innodb_write_io_threads = 8
innodb_thread_concurrency = 0
innodb_adaptive_hash_index = 1
innodb_change_buffering = all
innodb_autoinc_lock_mode = 2

# Query Cache (if available)
query_cache_type = 1
query_cache_size = $QUERY_CACHE_SIZE
query_cache_limit = 2M
query_cache_min_res_unit = 4096

# Binary Logging
log-bin = mysql-bin
binlog_format = ROW
expire_logs_days = 7
max_binlog_size = 100M

# Slow Query Log
slow_query_log = 1
slow_query_log_file = /var/log/mysql/slow.log
long_query_time = 2
log_queries_not_using_indexes = 1

# Performance Schema
performance_schema = ON
performance_schema_max_table_instances = 12500
performance_schema_max_table_handles = 4000

# Temporary Tables
tmp_table_size = 64M
max_heap_table_size = 64M

# Network Settings
max_allowed_packet = 64M
net_buffer_length = 8192

# Security Settings
local_infile = 0
sql_mode = STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO

# Replication Settings (if needed)
server-id = 1
auto_increment_increment = 1
auto_increment_offset = 1

# Logging
general_log = 0
general_log_file = /var/log/mysql/general.log
log_error_verbosity = 2

# Timezone
default-time-zone = '+00:00'

[mysql]
default-character-set = utf8mb4

[client]
default-character-set = utf8mb4
socket = /var/run/mysqld/mysqld.sock
EOF

    sudo cp /tmp/mysqld.cnf "$MYSQL_CONF"
    sudo chown mysql:mysql "$MYSQL_CONF"
    sudo chmod 644 "$MYSQL_CONF"
    
    log "Optimized MySQL configuration created"
}

# Create MySQL optimization script
create_optimization_script() {
    log "Creating MySQL optimization script..."
    
    cat > /tmp/optimize_mysql.sql << 'EOF'
-- GermanATO Database Optimization Script
-- Run this after configuration changes

-- Set global variables for current session
SET GLOBAL innodb_buffer_pool_size = 8589934592;  -- 8GB
SET GLOBAL query_cache_size = 134217728;          -- 128MB
SET GLOBAL max_connections = 200;
SET GLOBAL thread_cache_size = 16;
SET GLOBAL table_open_cache = 4000;

-- Analyze and optimize tables
ANALYZE TABLE customers;
ANALYZE TABLE cars;
ANALYZE TABLE invoices;
ANALYZE TABLE invoice_items;
ANALYZE TABLE invoice_labour;
ANALYZE TABLE repair_orders;
ANALYZE TABLE repair_order_parts;
ANALYZE TABLE repair_order_labour;
ANALYZE TABLE inventory;
ANALYZE TABLE expenses;
ANALYZE TABLE users;

-- Show current status
SHOW VARIABLES LIKE 'innodb_buffer_pool_size';
SHOW VARIABLES LIKE 'query_cache_size';
SHOW VARIABLES LIKE 'max_connections';
SHOW STATUS LIKE 'Threads_connected';
SHOW STATUS LIKE 'Queries';
SHOW STATUS LIKE 'Slow_queries';
EOF

    sudo cp /tmp/optimize_mysql.sql /usr/local/bin/optimize_mysql.sql
    sudo chown root:root /usr/local/bin/optimize_mysql.sql
    sudo chmod 644 /usr/local/bin/optimize_mysql.sql
    
    log "MySQL optimization script created"
}

# Create database monitoring script
create_monitoring_script() {
    log "Creating database monitoring script..."
    
    cat > /tmp/mysql-monitor.sh << 'EOF'
#!/bin/bash

# GermanATO MySQL Performance Monitor
# Run with: sudo /usr/local/bin/mysql-monitor.sh

echo "=== GermanATO MySQL Performance Monitor ==="
echo "Date: $(date)"
echo ""

# MySQL status
echo "MySQL Status:"
if sudo systemctl is-active --quiet mysql; then
    echo "✓ MySQL is running"
else
    echo "✗ MySQL is not running"
    exit 1
fi
echo ""

# Connection status
echo "Connection Status:"
mysql -u germanato_user -p'germanato_password_2024' -e "SHOW STATUS LIKE 'Threads_connected';" 2>/dev/null || echo "Failed to connect to MySQL"
echo ""

# Performance metrics
echo "Performance Metrics:"
mysql -u germanato_user -p'germanato_password_2024' -e "
SELECT 
    'Queries per second' as Metric,
    ROUND(VARIABLE_VALUE / (SELECT VARIABLE_VALUE FROM performance_schema.global_status WHERE VARIABLE_NAME = 'Uptime'), 2) as Value
FROM performance_schema.global_status 
WHERE VARIABLE_NAME = 'Questions'
UNION ALL
SELECT 
    'Slow queries' as Metric,
    VARIABLE_VALUE as Value
FROM performance_schema.global_status 
WHERE VARIABLE_NAME = 'Slow_queries'
UNION ALL
SELECT 
    'Open tables' as Metric,
    VARIABLE_VALUE as Value
FROM performance_schema.global_status 
WHERE VARIABLE_NAME = 'Open_tables'
UNION ALL
SELECT 
    'Table locks waited' as Metric,
    VARIABLE_VALUE as Value
FROM performance_schema.global_status 
WHERE VARIABLE_NAME = 'Table_locks_waited';
" 2>/dev/null || echo "Failed to get performance metrics"
echo ""

# InnoDB status
echo "InnoDB Status:"
mysql -u germanato_user -p'germanato_password_2024' -e "
SELECT 
    'Buffer pool size' as Metric,
    CONCAT(ROUND(VARIABLE_VALUE/1024/1024/1024, 2), ' GB') as Value
FROM performance_schema.global_variables 
WHERE VARIABLE_NAME = 'innodb_buffer_pool_size'
UNION ALL
SELECT 
    'Buffer pool hit rate' as Metric,
    CONCAT(ROUND((1 - VARIABLE_VALUE / (
        SELECT VARIABLE_VALUE 
        FROM performance_schema.global_status 
        WHERE VARIABLE_NAME = 'Innodb_buffer_pool_read_requests'
    )) * 100, 2), '%') as Value
FROM performance_schema.global_status 
WHERE VARIABLE_NAME = 'Innodb_buffer_pool_reads';
" 2>/dev/null || echo "Failed to get InnoDB status"
echo ""

# Table sizes
echo "Database Table Sizes:"
mysql -u germanato_user -p'germanato_password_2024' -e "
SELECT 
    table_name as 'Table',
    ROUND(((data_length + index_length) / 1024 / 1024), 2) as 'Size (MB)',
    table_rows as 'Rows'
FROM information_schema.tables 
WHERE table_schema = 'germanato_db'
ORDER BY (data_length + index_length) DESC;
" 2>/dev/null || echo "Failed to get table sizes"
echo ""

# Recent slow queries
echo "Recent Slow Queries (last 10):"
sudo tail -10 /var/log/mysql/slow.log 2>/dev/null || echo "No slow query log found"
echo ""

echo "=== End of Report ==="
EOF

    sudo cp /tmp/mysql-monitor.sh /usr/local/bin/mysql-monitor.sh
    sudo chown root:root /usr/local/bin/mysql-monitor.sh
    sudo chmod +x /usr/local/bin/mysql-monitor.sh
    
    log "Database monitoring script created"
}

# Optimize database tables
optimize_database() {
    log "Optimizing database tables..."
    
    # Create optimization SQL
    cat > /tmp/optimize_tables.sql << 'EOF'
-- Optimize all tables in germanato_db
OPTIMIZE TABLE customers;
OPTIMIZE TABLE cars;
OPTIMIZE TABLE invoices;
OPTIMIZE TABLE invoice_items;
OPTIMIZE TABLE invoice_labour;
OPTIMIZE TABLE repair_orders;
OPTIMIZE TABLE repair_order_parts;
OPTIMIZE TABLE repair_order_labour;
OPTIMIZE TABLE inventory;
OPTIMIZE TABLE expenses;
OPTIMIZE TABLE users;

-- Analyze tables for better query planning
ANALYZE TABLE customers;
ANALYZE TABLE cars;
ANALYZE TABLE invoices;
ANALYZE TABLE invoice_items;
ANALYZE TABLE invoice_labour;
ANALYZE TABLE repair_orders;
ANALYZE TABLE repair_order_parts;
ANALYZE TABLE repair_order_labour;
ANALYZE TABLE inventory;
ANALYZE TABLE expenses;
ANALYZE TABLE users;

-- Show optimization results
SHOW TABLE STATUS FROM germanato_db;
EOF

    # Run optimization
    if mysql -u germanato_user -p"$DB_PASS" "$DB_NAME" < /tmp/optimize_tables.sql; then
        log "Database tables optimized successfully"
    else
        warning "Some table optimizations may have failed"
    fi
    
    log "Database optimization completed"
}

# Create indexes for better performance
create_indexes() {
    log "Creating performance indexes..."
    
    cat > /tmp/create_indexes.sql << 'EOF'
-- Create indexes for better query performance

-- Customer indexes
CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);
CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);

-- Car indexes
CREATE INDEX IF NOT EXISTS idx_cars_plate_no ON cars(plate_no);
CREATE INDEX IF NOT EXISTS idx_cars_customer_id ON cars(customer_id);
CREATE INDEX IF NOT EXISTS idx_cars_make_model ON cars(make, model);

-- Invoice indexes
CREATE INDEX IF NOT EXISTS idx_invoices_customer_name ON invoices(customer_name);
CREATE INDEX IF NOT EXISTS idx_invoices_created_at ON invoices(created_at);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_type ON invoices(type_of);

-- Invoice items indexes
CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice_id ON invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_invoice_items_product_name ON invoice_items(product_name);

-- Repair order indexes
CREATE INDEX IF NOT EXISTS idx_repair_orders_customer_name ON repair_orders(customer_name);
CREATE INDEX IF NOT EXISTS idx_repair_orders_created_at ON repair_orders(created_at);
CREATE INDEX IF NOT EXISTS idx_repair_orders_status ON repair_orders(current_status);

-- Inventory indexes
CREATE INDEX IF NOT EXISTS idx_inventory_part_number ON inventory(part_number);
CREATE INDEX IF NOT EXISTS idx_inventory_category ON inventory(category);
CREATE INDEX IF NOT EXISTS idx_inventory_name ON inventory(name);

-- Expense indexes
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category);

-- User indexes
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
EOF

    # Run index creation
    if mysql -u germanato_user -p"$DB_PASS" "$DB_NAME" < /tmp/create_indexes.sql; then
        log "Performance indexes created successfully"
    else
        warning "Some indexes may already exist or failed to create"
    fi
    
    log "Index creation completed"
}

# Restart MySQL service
restart_mysql() {
    log "Restarting MySQL service..."
    
    # Stop MySQL
    sudo systemctl stop mysql
    
    # Wait a moment
    sleep 3
    
    # Start MySQL
    sudo systemctl start mysql
    
    # Wait for MySQL to be ready
    sleep 10
    
    # Check if MySQL is running
    if sudo systemctl is-active --quiet mysql; then
        log "✓ MySQL restarted successfully"
    else
        error "✗ MySQL failed to restart"
    fi
}

# Test database performance
test_performance() {
    log "Testing database performance..."
    
    # Test connection
    if mysql -u germanato_user -p"$DB_PASS" -e "SELECT 1;" > /dev/null 2>&1; then
        log "✓ Database connection successful"
    else
        error "✗ Database connection failed"
    fi
    
    # Test basic queries
    log "Testing basic queries..."
    
    # Test customer count
    CUSTOMER_COUNT=$(mysql -u germanato_user -p"$DB_PASS" "$DB_NAME" -e "SELECT COUNT(*) FROM customers;" -s -N)
    log "Customer count: $CUSTOMER_COUNT"
    
    # Test invoice count
    INVOICE_COUNT=$(mysql -u germanato_user -p"$DB_PASS" "$DB_NAME" -e "SELECT COUNT(*) FROM invoices;" -s -N)
    log "Invoice count: $INVOICE_COUNT"
    
    # Test inventory count
    INVENTORY_COUNT=$(mysql -u germanato_user -p"$DB_PASS" "$DB_NAME" -e "SELECT COUNT(*) FROM inventory;" -s -N)
    log "Inventory count: $INVENTORY_COUNT"
    
    log "Database performance testing completed"
}

# Display final information
show_final_info() {
    echo ""
    echo "=========================================="
    echo "GermanATO Database Optimization Complete"
    echo "=========================================="
    echo ""
    echo "MySQL Status:"
    echo "  - Service: $(sudo systemctl is-active mysql)"
    echo "  - Version: $(mysql --version | awk '{print $5}' | cut -d',' -f1)"
    echo ""
    echo "Configuration Files:"
    echo "  - Main config: $MYSQL_CONF"
    echo "  - Backup location: $BACKUP_DIR"
    echo ""
    echo "Optimization Applied:"
    echo "  ✓ InnoDB Buffer Pool: 8GB (50% of RAM)"
    echo "  ✓ Query Cache: 128MB"
    echo "  ✓ Max Connections: 200"
    echo "  ✓ Thread Cache: 16"
    echo "  ✓ Table Open Cache: 4000"
    echo "  ✓ Performance indexes created"
    echo "  ✓ Tables optimized"
    echo ""
    echo "Useful Commands:"
    echo "  - Monitor performance: sudo /usr/local/bin/mysql-monitor.sh"
    echo "  - Check MySQL status: sudo systemctl status mysql"
    echo "  - View slow queries: sudo tail -f /var/log/mysql/slow.log"
    echo "  - Connect to database: mysql -u germanato_user -p germanato_db"
    echo ""
    echo "Performance Monitoring:"
    echo "  - Run: sudo /usr/local/bin/mysql-monitor.sh"
    echo "  - Check slow queries: sudo tail -f /var/log/mysql/slow.log"
    echo "  - Monitor connections: mysql -u root -p -e 'SHOW PROCESSLIST;'"
    echo ""
}

# Main execution
main() {
    echo "GermanATO Database Optimization Script"
    echo "====================================="
    echo ""
    
    check_root
    check_system
    backup_config
    create_optimized_config
    create_optimization_script
    create_monitoring_script
    restart_mysql
    create_indexes
    optimize_database
    test_performance
    show_final_info
    
    log "Database optimization completed successfully!"
}

# Run main function
main "$@" 