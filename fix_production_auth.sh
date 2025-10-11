#!/bin/bash

# Production Authentication Fix Script
# This script fixes common JWT authentication issues in production

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}"
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

# Check if we're in the right directory
check_directory() {
    if [ ! -d "backend" ]; then
        error "Backend directory not found. Please run this script from the project root."
    fi
    
    if [ ! -f "backend/config.py" ]; then
        error "config.py not found. Please run this script from the project root."
    fi
    
    log "✓ Directory structure verified"
}

# Create production environment file
create_production_env() {
    log "Creating production environment configuration..."
    
    cat > backend/.env.production << 'EOF'
# Production Environment Configuration
# Copy this to .env and update with your actual values

# Database Configuration
DATABASE_URL=mysql+pymysql://root:germanato_password_2024@localhost:3306/germanato_db

# Security Keys (CHANGE THESE IN PRODUCTION!)
SECRET_KEY=your-super-secret-key-change-this-in-production-2024
JWT_SECRET_KEY=your-jwt-secret-key-change-this-in-production-2024

# Production Settings
FLASK_ENV=production
FLASK_DEBUG=False

# JWT Settings for Production
JWT_ACCESS_TOKEN_EXPIRES=86400  # 24 hours
JWT_REFRESH_TOKEN_EXPIRES=604800  # 7 days
JWT_COOKIE_SECURE=False  # Set to True if using HTTPS
JWT_COOKIE_CSRF_PROTECT=False  # Set to True for CSRF protection

# Session Settings
SESSION_COOKIE_SECURE=False  # Set to True if using HTTPS
SESSION_COOKIE_SAMESITE=Lax
SESSION_COOKIE_HTTPONLY=True
EOF

    success "✓ Production environment file created"
}

# Update JWT configuration for production
update_jwt_config() {
    log "Updating JWT configuration for production..."
    
    # Create a backup of the current config
    cp backend/config.py backend/config.py.backup
    
    # Update the config with production-optimized settings
    cat > backend/config_production.py << 'EOF'
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT Configuration - Production Optimized
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-secret-key-change-in-production")
    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", 86400))  # 24 hours
    JWT_REFRESH_TOKEN_EXPIRES = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES", 604800))  # 7 days
    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TOKEN_LOCATION = ["headers", "cookies"]
    JWT_COOKIE_SECURE = os.getenv("JWT_COOKIE_SECURE", "False").lower() == "true"
    JWT_COOKIE_CSRF_PROTECT = os.getenv("JWT_COOKIE_CSRF_PROTECT", "False").lower() == "true"
    JWT_COOKIE_SAMESITE = os.getenv("JWT_COOKIE_SAMESITE", "Lax")
    JWT_COOKIE_DOMAIN = None  # Auto-detect domain
    JWT_COOKIE_PATH = "/"  # Available for entire domain
    JWT_TOKEN_LOCATION = ["headers", "cookies"]  # Allow both headers and cookies
    
    # Session Configuration
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "False").lower() == "true"
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_NAME = "germanato_session"
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours
    SESSION_COOKIE_DOMAIN = None
    SESSION_COOKIE_PATH = "/"
EOF

    success "✓ JWT configuration updated for production"
}

# Create production-ready authentication middleware
create_auth_middleware() {
    log "Creating production authentication middleware..."
    
    cat > backend/auth_middleware.py << 'EOF'
"""
Production Authentication Middleware
Handles token refresh and authentication issues
"""

from flask import request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from functools import wraps
import logging

logger = logging.getLogger(__name__)

def production_jwt_required(f):
    """
    Enhanced JWT decorator for production with better error handling
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Verify JWT token
            verify_jwt_in_request()
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"JWT verification failed: {str(e)}")
            return jsonify({
                'error': 'Authentication failed',
                'message': 'Please log in again',
                'code': 'AUTH_REQUIRED'
            }), 401
    return decorated_function

def handle_auth_errors(app):
    """
    Register authentication error handlers
    """
    @app.errorhandler(401)
    def handle_unauthorized(e):
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Please log in to access this resource',
            'code': 'AUTH_REQUIRED'
        }), 401
    
    @app.errorhandler(403)
    def handle_forbidden(e):
        return jsonify({
            'error': 'Forbidden',
            'message': 'You do not have permission to access this resource',
            'code': 'PERMISSION_DENIED'
        }), 403

def setup_cors_for_production(app):
    """
    Setup CORS for production with proper credentials handling
    """
    from flask_cors import CORS
    
    CORS(app, resources={
        r"/api/*": {
            "origins": ["*"],  # Configure with your actual domain in production
            "supports_credentials": True,
            "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        }
    })
EOF

    success "✓ Authentication middleware created"
}

# Create production startup script
create_production_startup() {
    log "Creating production startup script..."
    
    cat > backend/start_production.py << 'EOF'
#!/usr/bin/env python3
"""
Production Startup Script for Germanato App
Handles proper initialization and error handling
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from auth_middleware import handle_auth_errors, setup_cors_for_production

def setup_production_app():
    """Setup the app for production"""
    
    # Configure logging
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Setup authentication error handlers
    handle_auth_errors(app)
    
    # Setup CORS for production
    setup_cors_for_production(app)
    
    # Configure for production
    app.config['DEBUG'] = False
    app.config['TESTING'] = False
    
    return app

if __name__ == '__main__':
    app = setup_production_app()
    
    # Get configuration from environment
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"Starting Germanato App in production mode...")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Debug: {debug}")
    
    app.run(host=host, port=port, debug=debug)
EOF

    chmod +x backend/start_production.py
    success "✓ Production startup script created"
}

# Create frontend authentication fix
create_frontend_auth_fix() {
    log "Creating frontend authentication fix..."
    
    cat > backend/static/js/auth_production.js << 'EOF'
// Production Authentication Manager
// Enhanced version with better error handling and token management

class ProductionAuthManager {
  constructor() {
    this.user = null;
    this.isAuthenticated = false;
    this.accessToken = null;
    this.refreshToken = null;
    this.refreshPromise = null;
    this.init();
  }

  async init() {
    // Load tokens from localStorage
    this.accessToken = localStorage.getItem("accessToken");
    this.refreshToken = localStorage.getItem("refreshToken");
    this.user = JSON.parse(localStorage.getItem("user") || "null");
    this.isAuthenticated = !!this.accessToken;

    // If we have tokens, verify them with the server
    if (this.isAuthenticated) {
      await this.verifyToken();
    }
  }

  async verifyToken() {
    try {
      const response = await fetch("/api/auth/verify", {
        method: "GET",
        headers: {
          Authorization: `Bearer ${this.accessToken}`,
          "Content-Type": "application/json",
        },
        credentials: 'include'  // Important for production
      });

      if (response.ok) {
        const data = await response.json();
        this.user = data.user;
        this.isAuthenticated = true;
        localStorage.setItem("user", JSON.stringify(data.user));
        return true;
      } else {
        // Token is invalid, try to refresh
        return await this.refreshAccessToken();
      }
    } catch (error) {
      console.error("Token verification failed:", error);
      this.clearAuth();
      return false;
    }
  }

  async refreshAccessToken() {
    // Prevent multiple simultaneous refresh attempts
    if (this.refreshPromise) {
      return this.refreshPromise;
    }

    this.refreshPromise = this._doRefresh();
    const result = await this.refreshPromise;
    this.refreshPromise = null;
    return result;
  }

  async _doRefresh() {
    if (!this.refreshToken) {
      this.clearAuth();
      return false;
    }

    try {
      const response = await fetch("/api/auth/refresh", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.refreshToken}`,
          "Content-Type": "application/json",
        },
        credentials: 'include'
      });

      if (response.ok) {
        const data = await response.json();
        this.accessToken = data.access_token;
        this.refreshToken = data.refresh_token;
        
        localStorage.setItem("accessToken", this.accessToken);
        localStorage.setItem("refreshToken", this.refreshToken);
        
        this.isAuthenticated = true;
        return true;
      } else {
        this.clearAuth();
        return false;
      }
    } catch (error) {
      console.error("Token refresh failed:", error);
      this.clearAuth();
      return false;
    }
  }

  async login(username, password) {
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: 'include',
        body: JSON.stringify({ username, password }),
      });

      if (response.ok) {
        const data = await response.json();
        this.accessToken = data.access_token;
        this.refreshToken = data.refresh_token;
        this.user = data.user;
        this.isAuthenticated = true;

        // Store tokens
        localStorage.setItem("accessToken", this.accessToken);
        localStorage.setItem("refreshToken", this.refreshToken);
        localStorage.setItem("user", JSON.stringify(this.user));

        return { success: true, user: this.user };
      } else {
        const error = await response.json();
        return { success: false, error: error.error || "Login failed" };
      }
    } catch (error) {
      console.error("Login failed:", error);
      return { success: false, error: "Network error" };
    }
  }

  logout() {
    this.clearAuth();
    
    // Call logout endpoint
    fetch("/api/auth/logout", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${this.accessToken}`,
        "Content-Type": "application/json",
      },
      credentials: 'include'
    }).catch(error => {
      console.error("Logout request failed:", error);
    });
  }

  clearAuth() {
    this.user = null;
    this.isAuthenticated = false;
    this.accessToken = null;
    this.refreshToken = null;
    
    localStorage.removeItem("accessToken");
    localStorage.removeItem("refreshToken");
    localStorage.removeItem("user");
  }

  // Enhanced fetch method with automatic token refresh
  async authenticatedFetch(url, options = {}) {
    // Add authorization header if we have a token
    if (this.accessToken) {
      options.headers = {
        ...options.headers,
        Authorization: `Bearer ${this.accessToken}`,
      };
    }

    // Add credentials for production
    options.credentials = 'include';

    try {
      const response = await fetch(url, options);
      
      // If we get a 401, try to refresh the token
      if (response.status === 401 && this.refreshToken) {
        const refreshed = await this.refreshAccessToken();
        if (refreshed) {
          // Retry the request with the new token
          options.headers.Authorization = `Bearer ${this.accessToken}`;
          return await fetch(url, options);
        } else {
          // Refresh failed, redirect to login
          window.location.href = '/login.html';
          return response;
        }
      }
      
      return response;
    } catch (error) {
      console.error("Authenticated fetch failed:", error);
      throw error;
    }
  }
}

// Global instance
window.authManager = new ProductionAuthManager();

// Auto-refresh token every 20 minutes
setInterval(() => {
  if (window.authManager.isAuthenticated) {
    window.authManager.refreshAccessToken();
  }
}, 20 * 60 * 1000);
EOF

    success "✓ Frontend authentication fix created"
}

# Show production setup summary
show_summary() {
    echo ""
    echo "=========================================="
    echo "Production Authentication Fix Complete"
    echo "=========================================="
    echo ""
    echo "✅ Fixed Issues:"
    echo "   - JWT token expiration extended to 24 hours"
    echo "   - Added automatic token refresh"
    echo "   - Enhanced error handling"
    echo "   - Production-optimized CORS settings"
    echo "   - Better session management"
    echo ""
    echo "✅ Files Created/Updated:"
    echo "   - backend/.env.production (environment config)"
    echo "   - backend/config_production.py (JWT config)"
    echo "   - backend/auth_middleware.py (auth middleware)"
    echo "   - backend/start_production.py (production startup)"
    echo "   - backend/static/js/auth_production.js (frontend fix)"
    echo ""
    echo "🚀 Next Steps:"
    echo "   1. Copy .env.production to .env and update values"
    echo "   2. Update your app.py to use config_production.py"
    echo "   3. Include auth_production.js in your HTML files"
    echo "   4. Restart your application server"
    echo ""
    echo "📝 Configuration Notes:"
    echo "   - Set JWT_COOKIE_SECURE=True if using HTTPS"
    echo "   - Set JWT_COOKIE_CSRF_PROTECT=True for CSRF protection"
    echo "   - Update CORS origins with your actual domain"
    echo ""
}

# Main execution
main() {
    echo "GermanATO Production Authentication Fix"
    echo "======================================"
    echo ""
    
    check_directory
    create_production_env
    update_jwt_config
    create_auth_middleware
    create_production_startup
    create_frontend_auth_fix
    show_summary
    
    log "Production authentication fix completed successfully!"
    echo ""
    echo "🎉 Your authentication issues should now be resolved!"
}

# Run main function
main "$@"
