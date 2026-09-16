#!/bin/bash

# GermanATO Auto Trader - Z440 PC Deployment Script
# This script automates the deployment process for the HP Z440 workstation

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="GermanATO"
APP_USER="germanato"
APP_DIR="/opt/germanato"
BACKEND_DIR="$APP_DIR/backend"
LOG_DIR="$APP_DIR/logs"
BACKUP_DIR="$APP_DIR/backups"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root"
        exit 1
    fi
}

# Function to update system
update_system() {
    print_status "Updating system packages..."
    apt update && apt upgrade -y
    apt install -y curl wget git vim htop unzip
    print_success "System updated successfully"
}

# Function to install Python
install_python() {
    print_status "Installing Python..."
    
    # Check Ubuntu version and install appropriate Python version
    UBUNTU_VERSION=$(lsb_release -rs)
    
    if [[ "$UBUNTU_VERSION" == "22.04" ]]; then
        print_status "Ubuntu 22.04 detected, installing Python 3.10..."
        apt install -y python3.10 python3.10-venv python3.10-dev python3-pip
        PYTHON_VERSION="python3.10"
    elif [[ "$UBUNTU_VERSION" == "20.04" ]]; then
        print_status "Ubuntu 20.04 detected, installing Python 3.9..."
        apt install -y python3.9 python3.9-venv python3.9-dev python3-pip
        PYTHON_VERSION="python3.9"
    else
        print_status "Installing default Python 3..."
        apt install -y python3 python3-venv python3-dev python3-pip
        PYTHON_VERSION="python3"
    fi
    
    # Set global variable for Python version
    export PYTHON_VERSION
    
    print_success "Python installed successfully ($PYTHON_VERSION)"
}

# Function to verify MySQL installation (skipped - already configured)
verify_mysql() {
    print_status "MySQL already configured, skipping verification..."
    print_success "MySQL verification skipped"
}

# Function to install Nginx
install_nginx() {
    print_status "Installing Nginx..."
    apt install -y nginx
    systemctl enable nginx
    systemctl start nginx
    print_success "Nginx installed and started"
}

# Function to create application user
create_app_user() {
    print_status "Creating application user..."
    if id "$APP_USER" &>/dev/null; then
        print_warning "User $APP_USER already exists"
    else
        useradd -m -s /bin/bash "$APP_USER"
        usermod -aG sudo "$APP_USER"
        print_success "User $APP_USER created"
    fi
}

# Function to setup application directory
setup_app_directory() {
    print_status "Setting up application directory..."
    
    # Create directories
    mkdir -p "$APP_DIR" "$LOG_DIR" "$BACKUP_DIR"
    
    # Check if backend files are already in the correct location
    if [ -d "$BACKEND_DIR" ] && [ "$(ls -A "$BACKEND_DIR" 2>/dev/null)" ]; then
        print_warning "Backend files already exist in $BACKEND_DIR"
        print_status "Skipping file copy, using existing files"
    else
        # Copy application files only if they don't exist
        if [ -d "backend" ]; then
            print_status "Copying backend files..."
            # Use -f flag to force copy and suppress "same file" messages
            cp -rf backend/* "$BACKEND_DIR/" 2>/dev/null || true
            print_success "Backend files copied"
        else
            print_error "Backend directory not found in current location"
            exit 1
        fi
    fi
    
    # Set permissions
    chown -R "$APP_USER:$APP_USER" "$APP_DIR"
    chmod -R 755 "$APP_DIR"
    
    print_success "Application directory setup complete"
}

# Function to setup Python environment
setup_python_env() {
    print_status "Setting up Python virtual environment..."
    
    cd "$BACKEND_DIR"
    
    # Create virtual environment
    sudo -u "$APP_USER" $PYTHON_VERSION -m venv env
    
    # Activate and install dependencies
    sudo -u "$APP_USER" bash -c "source env/bin/activate && pip install --upgrade pip"
    sudo -u "$APP_USER" bash -c "source env/bin/activate && pip install -r requirements.txt"
    
    print_success "Python environment setup complete"
}

# Function to setup database
setup_database() {
    print_status "Verifying existing database setup..."
    
    # Test database connection with existing credentials
    if mysql -u germanato_user -pgermanato_password_2024 -e "USE germanato_db;" 2>/dev/null; then
        print_success "Database connection verified successfully"
        print_success "Using existing database: germanato_db"
        print_success "Using existing user: germanato_user"
    else
        print_error "Cannot connect to database with existing credentials"
        print_error "Please verify database setup manually"
        print_error "Expected:"
        print_error "  - Database: germanato_db"
        print_error "  - User: germanato_user"
        print_error "  - Password: germanato_password_2024"
        exit 1
    fi
    
    print_success "Database setup verified"
}

# Function to configure environment
configure_environment() {
    print_status "Configuring environment variables..."
    
    cd "$BACKEND_DIR"
    
    # Check if .env file exists
    if [ -f ".env" ]; then
        print_warning "Environment file already exists, preserving existing configuration"
        
        # Backup existing .env
        cp .env .env.backup
        
        # Add Twilio variables if they don't exist
        if ! grep -q "TWILIO_ACCOUNT_SID" .env; then
            echo "" >> .env
            echo "# Twilio WhatsApp API Configuration" >> .env
            echo "TWILIO_ACCOUNT_SID=your_twilio_account_sid_here" >> .env
            echo "TWILIO_AUTH_TOKEN=your_twilio_auth_token_here" >> .env
            echo "TWILIO_WHATSAPP_NUMBER=your_twilio_whatsapp_number_here" >> .env
            echo "WHATSAPP_ENABLED=true" >> .env
            echo "WHATSAPP_TEST_MODE=false" >> .env
        fi
    else
        print_status "Creating new environment file..."
        sudo -u "$APP_USER" tee .env > /dev/null <<EOF
FLASK_APP=app.py
FLASK_ENV=production
SECRET_KEY=germanato_secret_key_2024_change_this_in_production
DATABASE_URL=mysql+pymysql://germanato_user:germanato_password_2024@localhost/germanato_db
# Twilio WhatsApp API Configuration
TWILIO_ACCOUNT_SID=your_twilio_account_sid_here
TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
TWILIO_WHATSAPP_NUMBER=your_twilio_whatsapp_number_here
WHATSAPP_ENABLED=true
WHATSAPP_TEST_MODE=false
EOF
    fi
    
    # Set proper permissions
    chmod 600 .env
    chown "$APP_USER:$APP_USER" .env
    
    print_success "Environment configuration complete"
}

# Function to initialize database tables
initialize_database() {
    print_status "Checking database tables..."
    
    cd "$BACKEND_DIR"
    
    # Check if tables already exist
    TABLE_COUNT=$(mysql -u germanato_user -pgermanato_password_2024 germanato_db -e "SHOW TABLES;" 2>/dev/null | wc -l)
    
    if [ "$TABLE_COUNT" -gt 1 ]; then
        print_warning "Database tables already exist ($TABLE_COUNT tables found), skipping table creation"
        print_warning "Existing data will be preserved"
    else
        print_status "Creating database tables..."
        sudo -u "$APP_USER" bash -c "source env/bin/activate && $PYTHON_VERSION -c \"
from app import app, db
with app.app_context():
    db.create_all()
    print('Database tables created successfully!')
\""
    fi

    print_status "Applying idempotent schema migrations..."
    if [ -f "$APP_DIR/migrate_release_schema.py" ]; then
        sudo -u "$APP_USER" bash -c "cd '$BACKEND_DIR' && source env/bin/activate && $PYTHON_VERSION '$APP_DIR/migrate_release_schema.py'"
    elif [ -f "add_inventory_barcode_fields.py" ]; then
        sudo -u "$APP_USER" bash -c "source env/bin/activate && $PYTHON_VERSION add_inventory_barcode_fields.py"
    else
        print_warning "No schema migration script found"
    fi
    
    print_success "Database initialization complete"
}

# Function to create admin user
create_admin_user() {
    print_status "Creating admin user..."
    
    cd "$BACKEND_DIR"
    
    # Create admin user if script exists
    if [ -f "create_admin_user.py" ]; then
        sudo -u "$APP_USER" bash -c "source env/bin/activate && $PYTHON_VERSION create_admin_user.py"
        print_success "Admin user created"
    else
        print_warning "create_admin_user.py not found, skipping admin user creation"
    fi
}

# Function to create systemd service
create_systemd_service() {
    print_status "Creating systemd service..."
    
    tee /etc/systemd/system/germanato.service > /dev/null <<EOF
[Unit]
Description=GermanATO Auto Trader
After=network.target mysql.service

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$BACKEND_DIR
Environment=PATH=$BACKEND_DIR/env/bin
Environment=FLASK_APP=app.py
Environment=FLASK_ENV=production
ExecStart=$BACKEND_DIR/env/bin/python start_production.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable germanato
    
    print_success "Systemd service created"
}

# Function to configure Nginx
configure_nginx() {
    print_status "Configuring Nginx..."
    
    # Create Nginx configuration
    tee /etc/nginx/sites-available/germanato > /dev/null <<EOF
server {
    listen 80;
    server_name _;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;

    # Static files
    location /static/ {
        alias $BACKEND_DIR/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Frontend files
    location / {
        root $BACKEND_DIR/frontend;
        try_files \$uri \$uri/ @flask;
    }

    # Proxy to Flask app
    location @flask {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied expired no-cache no-store private auth;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/javascript;
}
EOF
    
    # Enable site
    ln -sf /etc/nginx/sites-available/germanato /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    
    # Test and reload Nginx
    nginx -t
    systemctl reload nginx
    
    print_success "Nginx configuration complete"
}

# Function to configure logging
configure_logging() {
    print_status "Configuring logging..."
    
    # Create logrotate configuration
    tee /etc/logrotate.d/germanato > /dev/null <<EOF
$LOG_DIR/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $APP_USER $APP_USER
    postrotate
        systemctl reload germanato
    endscript
}
EOF
    
    print_success "Logging configuration complete"
}

# Function to configure firewall
configure_firewall() {
    print_status "Configuring firewall..."
    
    ufw allow ssh
    ufw allow 'Nginx Full'
    ufw --force enable
    
    print_success "Firewall configured"
}

# Function to create backup script
create_backup_script() {
    print_status "Creating backup script..."
    
    tee "$APP_DIR/backup.sh" > /dev/null <<EOF
#!/bin/bash
DATE=\$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
mysqldump -u germanato_user -p'germanato_password_2024' germanato_db > $BACKUP_DIR/germanato_\$DATE.sql
gzip $BACKUP_DIR/germanato_\$DATE.sql
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
EOF
    
    chmod +x "$APP_DIR/backup.sh"
    chown "$APP_USER:$APP_USER" "$APP_DIR/backup.sh"
    
    # Add to crontab for daily backups
    (crontab -l 2>/dev/null; echo "0 2 * * * $APP_DIR/backup.sh") | crontab -
    
    print_success "Backup script created"
}

# Function to start services
start_services() {
    print_status "Starting services..."
    
    # Start germanato service if it exists
    if systemctl list-unit-files | grep -q "germanato.service"; then
        systemctl start germanato
        
        # Check if service started successfully
        sleep 3
        if systemctl is-active --quiet germanato; then
            print_success "GermanATO service started successfully"
        else
            print_error "GermanATO service failed to start"
            print_status "Checking service logs..."
            journalctl -u germanato --no-pager -n 20
            print_error "Please check the logs above for errors"
        fi
    else
        print_warning "GermanATO service not found, will be created during deployment"
    fi
    
    # Start nginx
    systemctl start nginx
    print_success "Nginx started"
    
    print_success "Services started"
}

# Function to display status
display_status() {
    print_status "Checking service status..."
    
    echo
    echo "=== Service Status ==="
    systemctl status germanato --no-pager -l
    echo
    systemctl status nginx --no-pager -l
    echo
    systemctl status mysql --no-pager -l
    
    echo
    echo "=== Access Information ==="
    echo "Web Interface: http://$(hostname -I | awk '{print $1}')"
    echo "Admin Panel: http://$(hostname -I | awk '{print $1}')/admin.html"
    echo
    echo "=== Default Credentials ==="
    echo "Database User: germanato_user"
    echo "Database Password: germanato_password_2024"
    echo "Database Name: germanato_db"
    echo
    echo "=== Important Notes ==="
    echo "1. Change default passwords in production"
    echo "2. Update .env file with secure SECRET_KEY"
    echo "3. Configure SSL certificate for HTTPS"
    echo "4. Regular backups are scheduled at 2 AM daily"
    echo
}

# Function to show help
show_help() {
    echo "GermanATO Auto Trader - Z440 PC Deployment Script"
    echo
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  --full        Complete deployment (default)"
    echo "  --update      Update existing installation"
    echo "  --status      Show service status"
    echo "  --troubleshoot Troubleshoot service issues"
    echo "  --help        Show this help message"
    echo
    echo "Examples:"
    echo "  $0 --full     # Complete fresh deployment"
    echo "  $0 --update   # Update existing installation"
    echo "  $0 --status   # Check service status"
    echo "  $0 --troubleshoot # Troubleshoot service issues"
}

# Function to troubleshoot service issues
troubleshoot_service() {
    print_status "Troubleshooting GermanATO service..."
    
    echo
    echo "=== Service Status ==="
    systemctl status germanato --no-pager -l
    
    echo
    echo "=== Recent Logs ==="
    journalctl -u germanato --no-pager -n 30
    
    echo
    echo "=== File Permissions ==="
    ls -la /opt/germanato/backend/
    ls -la /opt/germanato/backend/env/bin/
    
    echo
    echo "=== Python Environment ==="
    sudo -u germanato bash -c "cd /opt/germanato/backend && source env/bin/activate && python --version && pip list | grep -E '(gunicorn|flask|pymysql)'"
    
    echo
    echo "=== Manual Test ==="
    echo "Testing if the application can start manually..."
    sudo -u germanato bash -c "cd /opt/germanato/backend && source env/bin/activate && python -c 'from app import app; print(\"App imported successfully\")'"
    
    print_success "Troubleshooting complete"
}

# Main deployment function
main_deployment() {
    print_status "Starting GermanATO deployment for Z440 PC..."
    
    check_root
    update_system
    install_python
    verify_mysql
    install_nginx
    create_app_user
    setup_app_directory
    setup_python_env
    setup_database
    configure_environment
    initialize_database
    create_admin_user
    create_systemd_service
    configure_nginx
    configure_logging
    configure_firewall
    create_backup_script
    start_services
    display_status
    
    print_success "GermanATO deployment completed successfully!"
    print_warning "Please change default passwords and configure SSL for production use."
}

# Update function
update_deployment() {
    print_status "Updating GermanATO installation..."
    
    check_root
    
    # Stop services if they exist
    if systemctl list-unit-files | grep -q "germanato.service"; then
        systemctl stop germanato
        print_success "GermanATO service stopped"
    else
        print_warning "GermanATO service not found, skipping stop"
    fi
    
    # Update application files
    setup_app_directory
    
    # Update Python environment
    setup_python_env
    
    # Restart services
    start_services
    
    print_success "GermanATO update completed successfully!"
}

# Main script logic
case "${1:---full}" in
    --full)
        main_deployment
        ;;
    --update)
        update_deployment
        ;;
    --status)
        display_status
        ;;
    --troubleshoot)
        troubleshoot_service
        ;;
    --help)
        show_help
        ;;
    *)
        print_error "Unknown option: $1"
        show_help
        exit 1
        ;;
esac 