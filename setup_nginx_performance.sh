#!/bin/bash

# GermanATO Nginx Performance Setup Script
# Ubuntu 24.04 LTS - 16GB RAM, 12 cores, 4 gunicorn workers

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration variables
APP_NAME="germanato"
APP_PATH="/opt/germanato/backend"
NGINX_CONF="/etc/nginx/nginx.conf"
SITE_CONF="/etc/nginx/sites-available/germanato-app"
SERVICE_FILE="/etc/systemd/system/germanato.service"
MONITOR_SCRIPT="/usr/local/bin/germanato-monitor.sh"

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
    
    # Check Ubuntu version
    if ! grep -q "Ubuntu 24.04" /etc/os-release; then
        warning "This script is optimized for Ubuntu 24.04. You're running: $(lsb_release -d | cut -f2)"
    fi
    
    # Check RAM
    RAM_GB=$(free -g | awk '/^Mem:/{print $2}')
    if [ "$RAM_GB" -lt 8 ]; then
        warning "System has ${RAM_GB}GB RAM. Recommended: 8GB+ for optimal performance"
    fi
    
    # Check CPU cores
    CPU_CORES=$(nproc)
    log "Detected ${CPU_CORES} CPU cores"
    
    # Check if nginx is installed
    if ! command -v nginx &> /dev/null; then
        error "Nginx is not installed. Please install it first: sudo apt install nginx"
    fi
    
    # Check if app directory exists
    if [ ! -d "$APP_PATH" ]; then
        error "Application directory not found: $APP_PATH"
    fi
    
    log "System requirements check completed"
}

# Stop services
stop_services() {
    log "Stopping services..."
    
    sudo systemctl stop nginx 2>/dev/null || true
    sudo systemctl stop germanato 2>/dev/null || true
    
    log "Services stopped"
}

# Remove existing configurations
remove_existing_config() {
    log "Removing existing nginx configurations..."
    
    # Remove existing site configurations
    sudo rm -rf /etc/nginx/sites-available/*
    sudo rm -rf /etc/nginx/sites-enabled/*
    sudo rm -f /etc/nginx/conf.d/*
    
    # Backup original nginx.conf if it exists
    if [ -f "$NGINX_CONF" ]; then
        sudo cp "$NGINX_CONF" "${NGINX_CONF}.backup.$(date +%Y%m%d_%H%M%S)"
        log "Original nginx.conf backed up"
    fi
    
    log "Existing configurations removed"
}

# Create optimized nginx main configuration
create_nginx_main_config() {
    log "Creating optimized nginx main configuration..."
    
    cat > /tmp/nginx.conf << 'EOF'
user www-data;
worker_processes 12;  # Match your 12 cores
worker_cpu_affinity auto;
pid /run/nginx.pid;
include /etc/nginx/modules-enabled/*.conf;

# Performance optimizations for 16GB RAM system
worker_rlimit_nofile 65536;
worker_connections 4096;  # Optimized for 4 users max
use epoll;
multi_accept on;

events {
    worker_connections 4096;
    use epoll;
    multi_accept on;
    accept_mutex off;
}

http {
    # Basic settings
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    server_tokens off;

    # Performance optimizations for 16GB RAM
    sendfile_max_chunk 1m;
    aio threads;
    directio 512;
    directio_alignment 512;
    
    # Buffer optimizations for mixed traffic
    client_body_buffer_size 256k;
    client_max_body_size 50m;
    client_header_buffer_size 2k;
    large_client_header_buffers 8 4k;
    output_buffers 2 64k;
    postpone_output 1460;

    # Timeout optimizations
    client_body_timeout 30;
    client_header_timeout 30;
    send_timeout 30;

    # Gzip compression for mixed content
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_min_length 1000;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml
        application/x-httpd-php
        application/xml;

    # Logging
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;

    # Include other configs
    include /etc/nginx/conf.d/*.conf;
    include /etc/nginx/sites-enabled/*;
}
EOF

    sudo cp /tmp/nginx.conf "$NGINX_CONF"
    sudo chown root:root "$NGINX_CONF"
    sudo chmod 644 "$NGINX_CONF"
    
    log "Nginx main configuration created"
}

# Create site configuration
create_site_config() {
    log "Creating GermanATO site configuration..."
    
    cat > /tmp/germanato-app << 'EOF'
upstream germanato_backend {
    # Load balancing for 4 gunicorn workers
    server 127.0.0.1:5000;
    server 127.0.0.1:5001;
    server 127.0.0.1:5002;
    server 127.0.0.1:5003;
    
    # Sticky sessions for better performance
    ip_hash;
    
    # Health checks
    keepalive 32;
}

server {
    listen 80;
    server_name localhost;  # Change to your domain if available
    
    # Document root for static files
    root /opt/germanato/backend/frontend;
    index index.html index.htm;
    
    # Performance optimizations for static files
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot|pdf)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
        add_header X-Content-Type-Options nosniff;
    }
    
    # API proxy to gunicorn workers
    location /api/ {
        proxy_pass http://germanato_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        
        # Performance optimizations for API calls
        proxy_buffering on;
        proxy_buffer_size 8k;
        proxy_buffers 16 8k;
        proxy_busy_buffers_size 16k;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Handle large requests (file uploads, etc.)
        proxy_request_buffering off;
        proxy_max_temp_file_size 0;
    }
    
    # Static files from backend
    location /static/ {
        alias /opt/germanato/backend/static/;
        expires 1m;
        add_header Cache-Control "public, immutable";
        access_log off;
        add_header X-Content-Type-Options nosniff;
    }
    
    # Main application routes
    location / {
        try_files $uri $uri/ /index.html;
        
        # Performance headers
        add_header X-Content-Type-Options nosniff;
        add_header X-Frame-Options DENY;
        add_header X-XSS-Protection "1; mode=block";
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
    
    # Nginx status for monitoring
    location /nginx_status {
        stub_status on;
        access_log off;
        allow 127.0.0.1;
        deny all;
    }
    
    # Security headers (minimal for performance)
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
}
EOF

    sudo cp /tmp/germanato-app "$SITE_CONF"
    sudo chown root:root "$SITE_CONF"
    sudo chmod 644 "$SITE_CONF"
    
    log "Site configuration created"
}

# Create systemd service file
create_service_file() {
    log "Creating systemd service file..."
    
    cat > /tmp/germanato.service << EOF
[Unit]
Description=GermanATO Gunicorn Service
After=network.target

[Service]
Type=exec
User=www-data
Group=www-data
WorkingDirectory=$APP_PATH
Environment=PATH=$APP_PATH/env/bin
ExecStart=$APP_PATH/env/bin/gunicorn --bind 0.0.0.0:5000 --workers 4 --worker-class sync --timeout 120 --keep-alive 2 --max-requests 1000 --max-requests-jitter 100 --access-logfile $APP_PATH/logs/gunicorn_access.log --error-logfile $APP_PATH/logs/gunicorn_error.log --log-level info wsgi:app
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

    sudo cp /tmp/germanato.service "$SERVICE_FILE"
    sudo chown root:root "$SERVICE_FILE"
    sudo chmod 644 "$SERVICE_FILE"
    
    log "Systemd service file created"
}

# Create monitoring script
create_monitor_script() {
    log "Creating performance monitoring script..."
    
    cat > /tmp/germanato-monitor.sh << 'EOF'
#!/bin/bash

# GermanATO Performance Monitor
# Run with: sudo /usr/local/bin/germanato-monitor.sh

echo "=== GermanATO Performance Monitor ==="
echo "Date: $(date)"
echo ""

# Nginx status
echo "Nginx Status:"
if curl -s http://localhost/nginx_status > /dev/null 2>&1; then
    curl -s http://localhost/nginx_status
else
    echo "Nginx status not available"
fi
echo ""

# Gunicorn processes
echo "Gunicorn Workers:"
WORKER_COUNT=$(ps aux | grep gunicorn | grep -v grep | wc -l)
echo "Active workers: $WORKER_COUNT"
echo ""

# Memory usage
echo "Memory Usage:"
free -h | grep -E "Mem|Swap"
echo ""

# CPU usage
echo "CPU Usage:"
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//')
echo "CPU: ${CPU_USAGE}%"
echo ""

# Disk usage
echo "Disk Usage:"
df -h /opt/germanato/backend
echo ""

# Active connections
echo "Active Connections:"
HTTP_CONN=$(netstat -an | grep :80 | wc -l)
GUNICORN_CONN=$(netstat -an | grep :5000 | wc -l)
echo "HTTP connections: $HTTP_CONN"
echo "Gunicorn connections: $GUNICORN_CONN"
echo ""

# Application health
echo "Application Health:"
if curl -s http://localhost/health > /dev/null 2>&1; then
    echo "✓ Application is healthy"
else
    echo "✗ Application health check failed"
fi
echo ""

# Recent errors
echo "Recent Nginx Errors (last 10):"
sudo tail -10 /var/log/nginx/error.log 2>/dev/null || echo "No error log found"
echo ""

echo "=== End of Report ==="
EOF

    sudo cp /tmp/germanato-monitor.sh "$MONITOR_SCRIPT"
    sudo chown root:root "$MONITOR_SCRIPT"
    sudo chmod +x "$MONITOR_SCRIPT"
    
    log "Monitoring script created"
}

# Optimize system settings
optimize_system() {
    log "Optimizing system settings..."
    
    # Increase file descriptor limits
    if ! grep -q "nofile 65536" /etc/security/limits.conf; then
        echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
        echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf
        log "File descriptor limits increased"
    fi
    
    # Optimize kernel parameters
    if ! grep -q "net.core.somaxconn" /etc/sysctl.conf; then
        cat >> /etc/sysctl.conf << 'EOF'

# GermanATO Performance Optimizations
net.core.somaxconn = 65536
net.ipv4.tcp_max_syn_backlog = 65536
net.core.netdev_max_backlog = 65536
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_keepalive_time = 1200
net.ipv4.tcp_max_tw_buckets = 5000
EOF
        log "Kernel parameters optimized"
    fi
    
    # Apply sysctl changes
    sudo sysctl -p > /dev/null 2>&1 || true
    
    log "System optimizations completed"
}

# Set up permissions
setup_permissions() {
    log "Setting up permissions..."
    
    # Create logs directory if it doesn't exist
    sudo mkdir -p "$APP_PATH/logs"
    
    # Set proper ownership
    sudo chown -R www-data:www-data "$APP_PATH"
    sudo chmod -R 755 "$APP_PATH"
    sudo chmod 755 "$APP_PATH/logs"
    
    log "Permissions set up"
}

# Enable and start services
enable_services() {
    log "Enabling and starting services..."
    
    # Enable site
    sudo ln -sf "$SITE_CONF" /etc/nginx/sites-enabled/
    
    # Remove default site if it exists
    sudo rm -f /etc/nginx/sites-enabled/default
    
    # Test nginx configuration
    if sudo nginx -t; then
        log "Nginx configuration test passed"
    else
        error "Nginx configuration test failed"
    fi
    
    # Reload systemd and restart services
    sudo systemctl daemon-reload
    sudo systemctl enable germanato
    sudo systemctl enable nginx
    
    # Start services
    sudo systemctl start germanato
    sudo systemctl start nginx
    
    log "Services enabled and started"
}

# Test the setup
test_setup() {
    log "Testing the setup..."
    
    # Wait a moment for services to start
    sleep 3
    
    # Check service status
    if sudo systemctl is-active --quiet nginx; then
        log "✓ Nginx is running"
    else
        error "✗ Nginx failed to start"
    fi
    
    if sudo systemctl is-active --quiet germanato; then
        log "✓ GermanATO service is running"
    else
        error "✗ GermanATO service failed to start"
    fi
    
    # Test HTTP response
    if curl -s -o /dev/null -w "%{http_code}" http://localhost | grep -q "200\|301\|302"; then
        log "✓ HTTP server is responding"
    else
        warning "✗ HTTP server test failed"
    fi
    
    # Test API endpoint
    if curl -s -o /dev/null -w "%{http_code}" http://localhost/api/ | grep -q "200\|301\|302\|404"; then
        log "✓ API endpoint is accessible"
    else
        warning "✗ API endpoint test failed"
    fi
    
    log "Setup testing completed"
}

# Display final information
show_final_info() {
    echo ""
    echo "=========================================="
    echo "GermanATO Nginx Performance Setup Complete"
    echo "=========================================="
    echo ""
    echo "Services:"
    echo "  - Nginx: $(sudo systemctl is-active nginx)"
    echo "  - GermanATO: $(sudo systemctl is-active germanato)"
    echo ""
    echo "Configuration Files:"
    echo "  - Nginx main config: $NGINX_CONF"
    echo "  - Site config: $SITE_CONF"
    echo "  - Service file: $SERVICE_FILE"
    echo ""
    echo "Useful Commands:"
    echo "  - Monitor performance: sudo $MONITOR_SCRIPT"
    echo "  - Check nginx status: sudo systemctl status nginx"
    echo "  - Check app status: sudo systemctl status germanato"
    echo "  - View nginx logs: sudo tail -f /var/log/nginx/error.log"
    echo "  - View app logs: sudo tail -f $APP_PATH/logs/gunicorn_error.log"
    echo ""
    echo "Access your application at: http://localhost"
    echo "API endpoint: http://localhost/api/"
    echo "Health check: http://localhost/health"
    echo ""
    echo "Performance optimizations applied:"
    echo "  ✓ 12 nginx workers (matching 12 CPU cores)"
    echo "  ✓ Load balancing across 4 gunicorn workers"
    echo "  ✓ Optimized buffers for 16GB RAM"
    echo "  ✓ Static file caching"
    echo "  ✓ Gzip compression"
    echo "  ✓ Performance monitoring script"
    echo ""
}

# Main execution
main() {
    echo "GermanATO Nginx Performance Setup Script"
    echo "======================================="
    echo ""
    
    check_root
    check_system
    stop_services
    remove_existing_config
    create_nginx_main_config
    create_site_config
    create_service_file
    create_monitor_script
    optimize_system
    setup_permissions
    enable_services
    test_setup
    show_final_info
    
    log "Setup completed successfully!"
}

# Run main function
main "$@" 