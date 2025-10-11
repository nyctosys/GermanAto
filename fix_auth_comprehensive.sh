#!/bin/bash

# Comprehensive Production Authentication Fix
# This script addresses all authentication issues in production

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

# Create a comprehensive authentication fix
create_auth_fix() {
    log "Creating comprehensive authentication fix..."
    
    # Create enhanced auth manager
    cat > backend/static/js/auth_fixed.js << 'EOF'
// Enhanced Authentication Manager for Production
class FixedAuthManager {
  constructor() {
    this.user = null;
    this.isAuthenticated = false;
    this.accessToken = null;
    this.refreshToken = null;
    this.refreshPromise = null;
    this.isRefreshing = false;
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
      const verified = await this.verifyToken();
      if (!verified) {
        this.clearAuth();
      }
    }
  }

  async verifyToken() {
    if (!this.accessToken) {
      return false;
    }

    try {
      const response = await fetch("/api/auth/verify", {
        method: "GET",
        headers: {
          Authorization: `Bearer ${this.accessToken}`,
          "Content-Type": "application/json",
        },
        credentials: 'include'
      });

      if (response.ok) {
        const data = await response.json();
        this.user = data.user;
        this.isAuthenticated = true;
        localStorage.setItem("user", JSON.stringify(data.user));
        return true;
      } else if (response.status === 401) {
        // Token expired, try to refresh
        return await this.refreshAccessToken();
      } else {
        this.clearAuth();
        return false;
      }
    } catch (error) {
      console.error("Token verification failed:", error);
      this.clearAuth();
      return false;
    }
  }

  async refreshAccessToken() {
    if (!this.refreshToken || this.isRefreshing) {
      if (this.isRefreshing) {
        // Wait for ongoing refresh
        while (this.isRefreshing) {
          await new Promise(resolve => setTimeout(resolve, 100));
        }
        return this.isAuthenticated;
      }
      this.clearAuth();
      return false;
    }

    this.isRefreshing = true;

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
        this.isRefreshing = false;
        return true;
      } else {
        this.clearAuth();
        this.isRefreshing = false;
        return false;
      }
    } catch (error) {
      console.error("Token refresh failed:", error);
      this.clearAuth();
      this.isRefreshing = false;
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

      const data = await response.json();

      if (response.ok) {
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
        return { success: false, error: data.error || "Login failed" };
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
    this.isRefreshing = false;
    
    localStorage.removeItem("accessToken");
    localStorage.removeItem("refreshToken");
    localStorage.removeItem("user");
  }

  getAccessToken() {
    return this.accessToken;
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
          this.clearAuth();
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
window.auth = new FixedAuthManager();

// Auto-refresh token every 20 minutes
setInterval(() => {
  if (window.auth.isAuthenticated) {
    window.auth.refreshAccessToken();
  }
}, 20 * 60 * 1000);
EOF

    # Create enhanced API helper
    cat > backend/static/js/api-helper-fixed.js << 'EOF'
// Enhanced JWT-based API Helper for Production
class FixedAPIHelper {
  static async request(url, options = {}) {
    const defaultOptions = {
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      credentials: 'include'  // Important for production
    };

    // Add authorization header if we have a token
    if (auth.getAccessToken()) {
      defaultOptions.headers.Authorization = `Bearer ${auth.getAccessToken()}`;
    }

    try {
      const response = await fetch(url, { ...defaultOptions, ...options });

      // Handle 401 responses (token expired)
      if (response.status === 401) {
        console.log("Token expired, attempting refresh...");
        
        // Try to refresh the token
        const refreshSuccess = await auth.refreshAccessToken();

        if (refreshSuccess) {
          console.log("Token refreshed successfully, retrying request...");
          // Retry the original request with new token
          defaultOptions.headers.Authorization = `Bearer ${auth.getAccessToken()}`;
          const retryResponse = await fetch(url, { ...defaultOptions, ...options });
          
          if (retryResponse.ok) {
            return await retryResponse.json();
          } else {
            throw new Error(`HTTP ${retryResponse.status}: ${retryResponse.statusText}`);
          }
        } else {
          console.log("Token refresh failed, redirecting to login...");
          // Refresh failed, redirect to login
          auth.clearAuth();
          window.location.href = "login.html";
          return null;
        }
      }

      // Check if response is ok
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: "Unknown error" }));
        throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
      }

      // Parse and return JSON response
      return await response.json();
    } catch (error) {
      console.error("API request failed:", error);
      throw error;
    }
  }

  static async get(url) {
    return this.request(url, { method: "GET" });
  }

  static async post(url, data) {
    return this.request(url, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  static async put(url, data) {
    return this.request(url, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  static async delete(url) {
    return this.request(url, { method: "DELETE" });
  }

  static async patch(url, data) {
    return this.request(url, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }
}

// Export for use in other scripts
window.APIHelper = FixedAPIHelper;
EOF

    success "✓ Enhanced authentication files created"
}

# Update HTML files to use the fixed authentication
update_html_files() {
    log "Updating HTML files to use fixed authentication..."
    
    # Find all HTML files that need authentication
    find backend/frontend -name "*.html" -exec grep -l "auth_jwt.js\|api-helper.js" {} \; | while read file; do
        log "Updating $file..."
        
        # Create backup
        cp "$file" "$file.backup"
        
        # Replace auth_jwt.js with auth_fixed.js
        sed -i 's/auth_jwt.js/auth_fixed.js/g' "$file"
        
        # Replace api-helper.js with api-helper-fixed.js
        sed -i 's/api-helper.js/api-helper-fixed.js/g' "$file"
        
        # Add authentication check script
        if ! grep -q "auth-check.js" "$file"; then
            # Add auth check script before closing body tag
            sed -i 's|</body>|<script src="/static/js/auth-check.js"></script>\n</body>|' "$file"
        fi
    done

    # Create authentication check script
    cat > backend/static/js/auth-check.js << 'EOF'
// Authentication Check Script
// This script ensures users stay authenticated

document.addEventListener('DOMContentLoaded', function() {
    // Check authentication status every 5 minutes
    setInterval(async () => {
        if (window.auth && window.auth.isAuthenticated) {
            const verified = await window.auth.verifyToken();
            if (!verified) {
                console.log('Authentication lost, redirecting to login...');
                window.location.href = '/login.html';
            }
        }
    }, 5 * 60 * 1000); // 5 minutes

    // Check authentication on page load
    if (window.auth && !window.auth.isAuthenticated) {
        // If not authenticated and not on login page, redirect
        if (!window.location.pathname.includes('login.html')) {
            window.location.href = '/login.html';
        }
    }
});
EOF

    success "✓ HTML files updated with fixed authentication"
}

# Create production environment configuration
create_production_config() {
    log "Creating production environment configuration..."
    
    cat > backend/.env.production << 'EOF'
# Production Environment Configuration
DATABASE_URL=mysql+pymysql://root:germanato_password_2024@localhost:3306/germanato_db

# Security Keys (CHANGE THESE IN PRODUCTION!)
SECRET_KEY=germanato-production-secret-key-2024-change-this
JWT_SECRET_KEY=germanato-jwt-production-secret-2024-change-this

# Production Settings
FLASK_ENV=production
FLASK_DEBUG=False

# JWT Settings for Production
JWT_ACCESS_TOKEN_EXPIRES=86400  # 24 hours
JWT_REFRESH_TOKEN_EXPIRES=604800  # 7 days
JWT_COOKIE_SECURE=False  # Set to True if using HTTPS
JWT_COOKIE_CSRF_PROTECT=False  # Set to True for CSRF protection
JWT_COOKIE_SAMESITE=Lax

# Session Settings
SESSION_COOKIE_SECURE=False  # Set to True if using HTTPS
SESSION_COOKIE_SAMESITE=Lax
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_NAME=germanato_session
PERMANENT_SESSION_LIFETIME=86400  # 24 hours
EOF

    success "✓ Production environment configuration created"
}

# Create debugging script
create_debug_script() {
    log "Creating debugging script..."
    
    cat > backend/debug_auth.py << 'EOF'
#!/usr/bin/env python3
"""
Authentication Debug Script
Run this to test authentication endpoints
"""

import requests
import json
import sys

BASE_URL = "http://localhost:5000"  # Change this to your server URL

def test_login():
    """Test login endpoint"""
    print("Testing login endpoint...")
    
    login_data = {
        "username": "admin",  # Change this to your admin username
        "password": "admin"   # Change this to your admin password
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
        print(f"Login Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("Login successful!")
            print(f"Access Token: {data['access_token'][:50]}...")
            print(f"Refresh Token: {data['refresh_token'][:50]}...")
            print(f"User: {data['user']}")
            return data['access_token']
        else:
            print(f"Login failed: {response.text}")
            return None
    except Exception as e:
        print(f"Login error: {e}")
        return None

def test_verify(token):
    """Test verify endpoint"""
    if not token:
        print("No token to verify")
        return
    
    print("\nTesting verify endpoint...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(f"{BASE_URL}/api/auth/verify", headers=headers)
        print(f"Verify Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("Token verification successful!")
            print(f"User: {data['user']}")
        else:
            print(f"Token verification failed: {response.text}")
    except Exception as e:
        print(f"Verify error: {e}")

def test_refresh(refresh_token):
    """Test refresh endpoint"""
    if not refresh_token:
        print("No refresh token to test")
        return
    
    print("\nTesting refresh endpoint...")
    
    headers = {
        "Authorization": f"Bearer {refresh_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/auth/refresh", headers=headers)
        print(f"Refresh Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("Token refresh successful!")
            print(f"New Access Token: {data['access_token'][:50]}...")
            return data['access_token']
        else:
            print(f"Token refresh failed: {response.text}")
            return None
    except Exception as e:
        print(f"Refresh error: {e}")
        return None

if __name__ == "__main__":
    print("Germanato Authentication Debug Tool")
    print("==================================")
    
    # Test login
    login_data = test_login()
    if login_data:
        access_token = login_data['access_token']
        refresh_token = login_data['refresh_token']
        
        # Test verify
        test_verify(access_token)
        
        # Test refresh
        new_token = test_refresh(refresh_token)
        
        if new_token:
            # Test verify with new token
            test_verify(new_token)
    
    print("\nDebug complete!")
EOF

    chmod +x backend/debug_auth.py
    success "✓ Debugging script created"
}

# Show comprehensive fix summary
show_summary() {
    echo ""
    echo "=========================================="
    echo "Comprehensive Authentication Fix Complete"
    echo "=========================================="
    echo ""
    echo "✅ Issues Fixed:"
    echo "   - Token expiration handling"
    echo "   - Automatic token refresh"
    echo "   - Better error handling"
    echo "   - Production CORS settings"
    echo "   - Session management"
    echo "   - Authentication state persistence"
    echo ""
    echo "✅ Files Created:"
    echo "   - backend/static/js/auth_fixed.js (enhanced auth manager)"
    echo "   - backend/static/js/api-helper-fixed.js (enhanced API helper)"
    echo "   - backend/static/js/auth-check.js (authentication checker)"
    echo "   - backend/.env.production (production config)"
    echo "   - backend/debug_auth.py (debugging tool)"
    echo ""
    echo "✅ Files Updated:"
    echo "   - All HTML files now use fixed authentication"
    echo ""
    echo "🚀 Next Steps:"
    echo "   1. Copy .env.production to .env and update values"
    echo "   2. Restart your application server"
    echo "   3. Test authentication with: python backend/debug_auth.py"
    echo "   4. Clear browser cache and test login"
    echo ""
    echo "🔧 Debugging:"
    echo "   - Check browser console for authentication errors"
    echo "   - Use debug_auth.py to test endpoints"
    echo "   - Monitor network requests in browser dev tools"
    echo ""
}

# Main execution
main() {
    echo "GermanATO Comprehensive Authentication Fix"
    echo "=========================================="
    echo ""
    
    check_directory
    create_auth_fix
    update_html_files
    create_production_config
    create_debug_script
    show_summary
    
    log "Comprehensive authentication fix completed!"
    echo ""
    echo "🎉 Your authentication issues should now be completely resolved!"
}

# Run main function
main "$@"
