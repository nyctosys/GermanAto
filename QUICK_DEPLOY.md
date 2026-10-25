# GermanATO - Quick Deployment Guide (Z440 PC)

## 🚀 One-Command Deployment

### Fresh Installation

```bash
# Clone the repository
sudo git clone https://github.com/your-repo/germanato-app.git /opt/germanato
cd /opt/germanato

# Run deployment script
sudo ./deploy.sh --full
```

### Update Existing Installation

```bash
cd /opt/germanato
sudo ./deploy.sh --update
```

### Check Service Status

```bash
sudo ./deploy.sh --status
```

## 📋 Pre-Deployment Checklist

- [ ] Ubuntu Server 22.04 LTS installed
- [ ] Root access available
- [ ] Internet connection active
- [ ] At least 10GB free disk space
- [ ] Static IP address configured (recommended)

## 🔧 Post-Deployment Steps

### 1. Change Default Passwords

```bash
# Change MySQL root password
sudo mysql -u root -p
ALTER USER 'root'@'localhost' IDENTIFIED BY 'your_new_root_password';

# Change application database password
sudo mysql -u root -p
ALTER USER 'germanato_user'@'localhost' IDENTIFIED BY 'your_new_app_password';
```

### 2. Update Environment Variables

```bash
sudo nano /opt/germanato/backend/.env
```

Update:

- `SECRET_KEY` (generate a secure random key)
- `DATABASE_URL` (if you changed the password)

### 3. Configure SSL (Optional)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com
```

## 🌐 Access Information

- **Web Interface**: http://your-server-ip
- **Admin Panel**: http://your-server-ip/admin.html
- **Default Admin**: Use credentials from `create_admin_user.py`

## 📊 System Requirements

### Hardware (Z440 Workstation)

- CPU: Intel Xeon E5-1620 v3 (4 cores, 8 threads)
- RAM: 16GB DDR4 ECC
- Storage: 256GB SSD
- Network: Gigabit Ethernet

### Software

- Ubuntu Server 22.04 LTS
- Python 3.9+
- MySQL 8.0+
- Nginx
- Gunicorn

## 🔍 Troubleshooting

### Service Won't Start

```bash
# Check service status
sudo systemctl status germanato

# View logs
sudo journalctl -u germanato -f

# Check configuration
sudo nginx -t
```

### Database Issues

```bash
# Test database connection
sudo mysql -u germanato_user -p germanato_db

# Check database status
sudo systemctl status mysql
```

### Permission Issues

```bash
# Fix permissions
sudo chown -R germanato:germanato /opt/germanato
sudo chmod -R 755 /opt/germanato
```

## 📈 Performance Monitoring

### Check Resource Usage

```bash
# System resources
htop

# Disk usage
df -h

# Memory usage
free -h
```

### View Application Logs

```bash
# Gunicorn logs
sudo tail -f /opt/germanato/logs/gunicorn_access.log
sudo tail -f /opt/germanato/logs/gunicorn_error.log

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

## 🔄 Maintenance

### Daily Backups

- Automatic backups run at 2 AM daily
- Stored in `/opt/germanato/backups/`
- Kept for 7 days

### Manual Backup

```bash
sudo /opt/germanato/backup.sh
```

### Update Application

```bash
cd /opt/germanato
sudo git pull
sudo ./deploy.sh --update
```

## 🛡️ Security Notes

1. **Change all default passwords**
2. **Configure firewall rules**
3. **Enable SSL/TLS encryption**
4. **Regular security updates**
5. **Monitor access logs**

## 📞 Support

For issues:

1. Check logs: `sudo journalctl -u germanato -f`
2. Verify configuration files
3. Test database connectivity
4. Check firewall settings

---

**Note**: This deployment is optimized for the Z440 workstation with 3 users in a LAN environment.
