# GermanATO Auto Trader - Z440 PC Setup Guide

## System Requirements

### Hardware (Z440 Workstation)

- **CPU**: Intel Xeon E5-1620 v3 (4 cores, 8 threads)
- **RAM**: 16GB DDR4 ECC
- **Storage**: 256GB SSD
- **Network**: Gigabit Ethernet
- **OS**: Ubuntu Server 22.04 LTS

### Software Requirements

- Python 3.9+
- MySQL 8.0+
- Nginx (for reverse proxy)
- Gunicorn (WSGI server)
- Git

## Initial Server Setup

### 1. Update System

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget git vim htop
```

### 2. Install Python 3.9

```bash
sudo apt install -y python3.9 python3.9-venv python3.9-dev
sudo apt install -y python3-pip
```

### 3. Install MySQL

```bash
sudo apt install -y mysql-server mysql-client
sudo mysql_secure_installation
```

### 4. Install Nginx

```bash
sudo apt install -y nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

### 5. Create Application User

```bash
sudo useradd -m -s /bin/bash germanato
sudo usermod -aG sudo germanato
sudo passwd germanato
```

## Application Deployment

### 1. Clone Repository

```bash
sudo -u germanato git clone https://github.com/your-repo/germanato-app.git /opt/germanato
cd /opt/germanato
```

### 2. Set Up Python Environment

```bash
cd /opt/germanato/backend
python3.9 -m venv env
source env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Database

```bash
sudo mysql -u root -p
```

```sql
CREATE DATABASE germanato_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'germanato_user'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON germanato_db.* TO 'germanato_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 4. Configure Environment Variables

```bash
cd /opt/germanato/backend
cp .env.example .env
sudo -u germanato nano .env
```

**Required Environment Variables:**

```env
FLASK_APP=app.py
FLASK_ENV=production
SECRET_KEY=your_very_secure_secret_key_here
DATABASE_URL=mysql+pymysql://germanato_user:your_secure_password@localhost/germanato_db
```

### 5. Initialize Database

```bash
cd /opt/germanato/backend
source env/bin/activate
python3.9 -c "
from app import app, db
with app.app_context():
    db.create_all()
    print('Database tables created successfully!')
"
```

### 6. Create Admin User

```bash
cd /opt/germanato/backend
source env/bin/activate
python3.9 create_admin_user.py
```

## Service Configuration

### 1. Create Systemd Service

```bash
sudo tee /etc/systemd/system/germanato.service > /dev/null <<EOF
[Unit]
Description=GermanATO Auto Trader
After=network.target mysql.service

[Service]
Type=simple
User=germanato
Group=germanato
WorkingDirectory=/opt/germanato/backend
Environment=PATH=/opt/germanato/backend/env/bin
ExecStart=/opt/germanato/backend/env/bin/python start_production.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

### 2. Configure Nginx

```bash
sudo tee /etc/nginx/sites-available/germanato > /dev/null <<EOF
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
        alias /opt/germanato/backend/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Frontend files
    location / {
        root /opt/germanato/backend/frontend;
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
    gzip_proxied expired no-cache no-store private must-revalidate auth;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/javascript;
}
EOF
```

### 3. Enable Site and Start Services

```bash
sudo ln -s /etc/nginx/sites-available/germanato /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

sudo systemctl daemon-reload
sudo systemctl enable germanato
sudo systemctl start germanato
```

## Logging Configuration

### 1. Create Log Directory

```bash
sudo mkdir -p /opt/germanato/logs
sudo chown germanato:germanato /opt/germanato/logs
```

### 2. Configure Log Rotation

```bash
sudo tee /etc/logrotate.d/germanato > /dev/null <<EOF
/opt/germanato/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 germanato germanato
    postrotate
        systemctl reload germanato
    endscript
}
EOF
```

## Security Configuration

### 1. Configure Firewall

```bash
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

### 2. Set File Permissions

```bash
sudo chown -R germanato:germanato /opt/germanato
sudo chmod -R 755 /opt/germanato
sudo chmod 600 /opt/germanato/backend/.env
```

## Monitoring and Maintenance

### 1. Check Service Status

```bash
sudo systemctl status germanato
sudo systemctl status nginx
sudo systemctl status mysql
```

### 2. View Logs

```bash
# Application logs
sudo journalctl -u germanato -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Gunicorn logs
sudo tail -f /opt/germanato/logs/gunicorn_access.log
sudo tail -f /opt/germanato/logs/gunicorn_error.log
```

### 3. Database Backup

```bash
# Create backup script
sudo tee /opt/germanato/backup.sh > /dev/null <<EOF
#!/bin/bash
BACKUP_DIR="/opt/germanato/backups"
DATE=\$(date +%Y%m%d_%H%M%S)
mkdir -p \$BACKUP_DIR
mysqldump -u germanato_user -p germanato_db > \$BACKUP_DIR/germanato_\$DATE.sql
gzip \$BACKUP_DIR/germanato_\$DATE.sql
find \$BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
EOF

sudo chmod +x /opt/germanato/backup.sh
sudo chown germanato:germanato /opt/germanato/backup.sh

# Add to crontab for daily backups
sudo crontab -e
# Add: 0 2 * * * /opt/germanato/backup.sh
```

## Troubleshooting

### Common Issues

1. **Service won't start**

   ```bash
   sudo systemctl status germanato
   sudo journalctl -u germanato -n 50
   ```

2. **Database connection issues**

   ```bash
   sudo mysql -u germanato_user -p germanato_db
   ```

3. **Permission issues**

   ```bash
   sudo chown -R germanato:germanato /opt/germanato
   ```

4. **Port conflicts**
   ```bash
   sudo netstat -tlnp | grep :5000
   sudo netstat -tlnp | grep :80
   ```

## Performance Optimization

### 1. MySQL Optimization

```bash
sudo nano /etc/mysql/mysql.conf.d/mysqld.cnf
```

Add to `[mysqld]` section:

```ini
innodb_buffer_pool_size = 1G
innodb_log_file_size = 256M
innodb_flush_log_at_trx_commit = 2
query_cache_size = 64M
query_cache_type = 1
```

### 2. System Optimization

```bash
# Increase file descriptor limits
echo "germanato soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "germanato hard nofile 65536" | sudo tee -a /etc/security/limits.conf
```

## Access Information

- **Web Interface**: http://your-server-ip
- **Admin Panel**: http://your-server-ip/admin.html
- **Default Admin**: Use credentials created with `create_admin_user.py`

## Support

For issues or questions:

1. Check logs: `sudo journalctl -u germanato -f`
2. Verify configuration files
3. Test database connectivity
4. Check firewall settings

---

**Note**: This setup is optimized for the Z440 workstation with 3 users in a LAN environment. Adjust worker counts and resource allocations based on actual usage patterns.
