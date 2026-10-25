#!/bin/bash

# Migration script to remove price-related fields from repair_order table
# This script drops the columns: parts_total, labour_total, tax_amount, total_estimate

set -e

# Database configuration - UPDATE THESE VALUES
DB_NAME="germanato_db"
DB_USER="root"
DB_HOST="localhost"
DB_PORT="3306"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[INFO]${NC} $1"
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

# Function to check if column exists
column_exists() {
    local column_name=$1
    mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -e "SHOW COLUMNS FROM repair_order LIKE '$column_name';" 2>/dev/null | grep -q "$column_name"
}

# Main migration function
migrate() {
    log "Starting migration to remove price-related fields from repair_order table..."
    
    # Prompt for database password if not set
    if [ -z "$DB_PASSWORD" ]; then
        read -sp "Enter MySQL password for user '$DB_USER': " DB_PASSWORD
        echo
    fi
    
    # Check database connection
    log "Checking database connection..."
    if ! mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" -e "USE $DB_NAME;" 2>/dev/null; then
        error "Cannot connect to database. Please check your credentials."
        exit 1
    fi
    success "Database connection successful"
    
    # Drop columns if they exist
    log "Dropping price-related columns..."
    
    if column_exists "total_estimate"; then
        log "Dropping column: total_estimate"
        mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -e "ALTER TABLE repair_order DROP COLUMN total_estimate;" 2>/dev/null
        success "Dropped column: total_estimate"
    else
        warning "Column 'total_estimate' does not exist, skipping..."
    fi
    
    if column_exists "parts_total"; then
        log "Dropping column: parts_total"
        mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -e "ALTER TABLE repair_order DROP COLUMN parts_total;" 2>/dev/null
        success "Dropped column: parts_total"
    else
        warning "Column 'parts_total' does not exist, skipping..."
    fi
    
    if column_exists "labour_total"; then
        log "Dropping column: labour_total"
        mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -e "ALTER TABLE repair_order DROP COLUMN labour_total;" 2>/dev/null
        success "Dropped column: labour_total"
    else
        warning "Column 'labour_total' does not exist, skipping..."
    fi
    
    if column_exists "tax_amount"; then
        log "Dropping column: tax_amount"
        mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -e "ALTER TABLE repair_order DROP COLUMN tax_amount;" 2>/dev/null
        success "Dropped column: tax_amount"
    else
        warning "Column 'tax_amount' does not exist, skipping..."
    fi
    
    success "Migration completed successfully!"
    log "All price-related fields have been removed from the repair_order table."
}

# Show help
show_help() {
    echo "Remove Price Fields Migration Script"
    echo ""
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  migrate    Run the migration (default)"
    echo "  help       Show this help message"
    echo ""
    echo "This script removes the following columns from repair_order table:"
    echo "  - parts_total"
    echo "  - labour_total"
    echo "  - tax_amount"
    echo "  - total_estimate"
    echo ""
    echo "IMPORTANT: Make sure to backup your database before running this migration!"
}

# Main script logic
main() {
    case "${1:-migrate}" in
        "migrate")
            migrate
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

