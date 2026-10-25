#!/bin/bash

# Test script for safe database migration
# This script tests the migration process on a test database

set -e

# Test configuration
TEST_DB_NAME="germanato_test_db"
TEST_DB_USER="root"
TEST_DB_HOST="localhost"
TEST_DB_PORT="3306"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to create test database
create_test_db() {
    log "Creating test database..."
    
    mysql -h "$TEST_DB_HOST" -P "$TEST_DB_PORT" -u "$TEST_DB_USER" -p -e "DROP DATABASE IF EXISTS $TEST_DB_NAME;" 2>/dev/null || true
    mysql -h "$TEST_DB_HOST" -P "$TEST_DB_PORT" -u "$TEST_DB_USER" -p -e "CREATE DATABASE $TEST_DB_NAME;" 2>/dev/null
    
    success "Test database created: $TEST_DB_NAME"
}

# Function to create minimal test schema
create_test_schema() {
    log "Creating test schema..."
    
    mysql -h "$TEST_DB_HOST" -P "$TEST_DB_PORT" -u "$TEST_DB_USER" -p "$TEST_DB_NAME" << 'EOF'
-- Create minimal test tables
CREATE TABLE invoice (
    id INT PRIMARY KEY AUTO_INCREMENT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    customer_name VARCHAR(255) NOT NULL,
    customer_address VARCHAR(255) NOT NULL,
    customer_phone VARCHAR(20) NOT NULL,
    customer_reg_no VARCHAR(50) NOT NULL,
    customer_made VARCHAR(100) NOT NULL,
    customer_mileage VARCHAR(100) NOT NULL,
    customer_vin VARCHAR(17),
    customer_color VARCHAR(50),
    customer_chasis VARCHAR(50),
    balance FLOAT NOT NULL,
    advance FLOAT NOT NULL,
    net_total FLOAT NOT NULL,
    discount FLOAT NOT NULL DEFAULT 0,
    type_of VARCHAR(50) NOT NULL,
    include_tax BOOLEAN NOT NULL DEFAULT FALSE,
    tax_amount FLOAT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL
);

CREATE TABLE inventory (
    id INT PRIMARY KEY AUTO_INCREMENT,
    part_number VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    quantity INT NOT NULL,
    price FLOAT NOT NULL,
    description TEXT,
    location VARCHAR(255),
    reorder_level INT NOT NULL DEFAULT 5,
    reorder_quantity INT NOT NULL DEFAULT 10,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE repair_order (
    id INT PRIMARY KEY AUTO_INCREMENT,
    customer_name VARCHAR(255) NOT NULL,
    customer_phone VARCHAR(20) NOT NULL,
    customer_address VARCHAR(255) NOT NULL,
    customer_reg_no VARCHAR(50) NOT NULL,
    customer_made VARCHAR(100) NOT NULL,
    customer_mileage VARCHAR(100) NOT NULL,
    customer_vin VARCHAR(17),
    customer_color VARCHAR(50),
    customer_chasis VARCHAR(50),
    problem_description TEXT,
    diagnosis_plan TEXT,
    worker_name VARCHAR(255),
    current_status VARCHAR(20) NOT NULL DEFAULT 'received',
    status_timeline TEXT,
    vehicle_condition TEXT,
    parts_total FLOAT NOT NULL DEFAULT 0,
    labour_total FLOAT NOT NULL DEFAULT 0,
    tax_amount FLOAT NOT NULL DEFAULT 0,
    total_estimate FLOAT NOT NULL DEFAULT 0,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE repair_order_part (
    id INT PRIMARY KEY AUTO_INCREMENT,
    repair_order_id INT NOT NULL,
    inventory_id INT,
    description VARCHAR(255) NOT NULL,
    part_number VARCHAR(100),
    quantity INT NOT NULL,
    price FLOAT NOT NULL,
    status VARCHAR(20) NOT NULL
);

CREATE TABLE repair_order_labour (
    id INT PRIMARY KEY AUTO_INCREMENT,
    repair_order_id INT NOT NULL,
    description VARCHAR(255) NOT NULL,
    rate FLOAT NOT NULL,
    status VARCHAR(20) NOT NULL
);

CREATE TABLE customer (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255),
    phone VARCHAR(20),
    address VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE car (
    id INT PRIMARY KEY AUTO_INCREMENT,
    make VARCHAR(100),
    model VARCHAR(100),
    plate_no VARCHAR(20),
    mileage VARCHAR(50),
    vin VARCHAR(100),
    color VARCHAR(50),
    chasis_no VARCHAR(100),
    customer_id INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE expense (
    id INT PRIMARY KEY AUTO_INCREMENT,
    date DATE NOT NULL,
    category VARCHAR(100) NOT NULL,
    description VARCHAR(255) NOT NULL,
    amount FLOAT NOT NULL,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE cash_received (
    id INT PRIMARY KEY AUTO_INCREMENT,
    date DATE NOT NULL,
    description VARCHAR(255) NOT NULL,
    amount FLOAT NOT NULL,
    payment_method VARCHAR(50) NOT NULL,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE user (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME
);

CREATE TABLE whats_app_notification (
    id INT PRIMARY KEY AUTO_INCREMENT,
    customer_name VARCHAR(255) NOT NULL,
    customer_phone VARCHAR(20) NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    message_content TEXT NOT NULL,
    related_document_type VARCHAR(50),
    related_document_id INT,
    whatsapp_message_id VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    sent_at DATETIME,
    delivered_at DATETIME
);

-- Insert test data
INSERT INTO invoice (customer_name, customer_address, customer_phone, customer_reg_no, customer_made, customer_mileage, balance, advance, net_total, type_of, status) VALUES
('Test Customer', 'Test Address', '1234567890', 'ABC-123', 'Toyota', '50000', 1000, 200, 1000, 'invoice', 'unpaid');

INSERT INTO inventory (part_number, name, category, quantity, price, description) VALUES
('PN001', 'Test Part', 'Engine', 10, 100.00, 'Test engine part');

INSERT INTO repair_order (customer_name, customer_phone, customer_address, customer_reg_no, customer_made, customer_mileage, current_status) VALUES
('Test Customer', '1234567890', 'Test Address', 'ABC-123', 'Toyota', '50000', 'received');

EOF

    success "Test schema created with sample data"
}

# Function to test migration
test_migration() {
    log "Testing migration on test database..."
    
    # Modify the migration script to use test database
    sed "s/DB_NAME=\"germanato_db\"/DB_NAME=\"$TEST_DB_NAME\"/" safe_db_migration.sh > test_migration.sh
    chmod +x test_migration.sh
    
    # Run migration
    if ./test_migration.sh migrate; then
        success "Migration test completed successfully"
    else
        error "Migration test failed"
        return 1
    fi
    
    # Clean up test script
    rm -f test_migration.sh
}

# Function to verify migration results
verify_migration() {
    log "Verifying migration results..."
    
    # Check if new columns exist
    if mysql -h "$TEST_DB_HOST" -P "$TEST_DB_PORT" -u "$TEST_DB_USER" -p -e "USE $TEST_DB_NAME; DESCRIBE invoice;" | grep -q "paid_amount"; then
        success "invoice.paid_amount column exists"
    else
        error "invoice.paid_amount column missing"
        return 1
    fi
    
    if mysql -h "$TEST_DB_HOST" -P "$TEST_DB_PORT" -u "$TEST_DB_USER" -p -e "USE $TEST_DB_NAME; DESCRIBE inventory;" | grep -q "image_path"; then
        success "inventory.image_path column exists"
    else
        error "inventory.image_path column missing"
        return 1
    fi
    
    if mysql -h "$TEST_DB_HOST" -P "$TEST_DB_PORT" -u "$TEST_DB_USER" -p -e "USE $TEST_DB_NAME; DESCRIBE repair_order;" | grep -q "worker_id"; then
        success "repair_order.worker_id column exists"
    else
        error "repair_order.worker_id column missing"
        return 1
    fi
    
    # Check if new tables exist
    if mysql -h "$TEST_DB_HOST" -P "$TEST_DB_PORT" -u "$TEST_DB_USER" -p -e "USE $TEST_DB_NAME; SHOW TABLES LIKE 'vendors';" | grep -q "vendors"; then
        success "vendors table exists"
    else
        warning "vendors table missing (optional)"
    fi
    
    if mysql -h "$TEST_DB_HOST" -P "$TEST_DB_PORT" -u "$TEST_DB_USER" -p -e "USE $TEST_DB_NAME; SHOW TABLES LIKE 'workers';" | grep -q "workers"; then
        success "workers table exists"
    else
        warning "workers table missing (optional)"
    fi
    
    success "Migration verification completed"
}

# Function to cleanup test database
cleanup_test_db() {
    log "Cleaning up test database..."
    
    mysql -h "$TEST_DB_HOST" -P "$TEST_DB_PORT" -u "$TEST_DB_USER" -p -e "DROP DATABASE IF EXISTS $TEST_DB_NAME;" 2>/dev/null || true
    
    # Clean up test files
    rm -f ./db_backups/germanato_test_db_backup_*.sql
    rm -f .last_backup
    
    success "Test database cleaned up"
}

# Main test function
run_tests() {
    log "Starting migration tests..."
    
    create_test_db
    create_test_schema
    test_migration
    verify_migration
    cleanup_test_db
    
    success "All tests completed successfully!"
    log "The migration script is ready for production use."
}

# Show help
show_help() {
    echo "Database Migration Test Script"
    echo ""
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  test    Run migration tests (default)"
    echo "  help    Show this help message"
    echo ""
    echo "This script tests the migration process on a test database."
}

# Main script logic
main() {
    case "${1:-test}" in
        "test")
            run_tests
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

# Run main function
main "$@"
