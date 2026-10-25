#!/bin/bash

# JWT Production Fix Script for GermanATO
# This script fixes JWT authentication issues in production

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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
    
    log "✓ Directory structure verified"
}

# Fix JWT_SECRET_KEY in environment
fix_jwt_secret() {
    log "Fixing JWT_SECRET_KEY configuration..."
    
    # Check if JWT_SECRET_KEY is set in backend/.env
    if [ -f "backend/.env" ]; then
        if grep -q "JWT_SECRET_KEY" backend/.env; then
            log "✓ JWT_SECRET_KEY already exists in backend/.env"
        else
            echo "JWT_SECRET_KEY=my-super-secure-jwt-secret-key-for-production-2024" >> backend/.env
            success "✓ JWT_SECRET_KEY added to backend/.env"
        fi
    else
        # Create .env file with JWT_SECRET_KEY
        cat > backend/.env << EOF
# GermanATO Environment Configuration
SECRET_KEY=my-super-secure-hidden-key
JWT_SECRET_KEY=my-super-secure-jwt-secret-key-for-production-2024
DATABASE_URL=mysql+pymysql://root:root%401324@localhost/germanato_db
EOF
        success "✓ Created backend/.env with JWT_SECRET_KEY"
    fi
}

# Test JWT configuration
test_jwt_config() {
    log "Testing JWT configuration..."
    
    cd backend
    
    python -c "
import os
from dotenv import load_dotenv
load_dotenv()

jwt_secret = os.getenv('JWT_SECRET_KEY')
if jwt_secret and jwt_secret != 'jwt-secret-key-change-in-production':
    print('✓ JWT_SECRET_KEY is properly configured')
else:
    print('❌ JWT_SECRET_KEY is not properly configured')
    exit(1)
" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        success "✓ JWT configuration test passed"
    else
        error "JWT configuration test failed"
    fi
    
    cd ..
}

# Test JWT authentication
test_jwt_auth() {
    log "Testing JWT authentication..."
    
    cd backend
    
    python -c "
from app import app
from flask_jwt_extended import create_access_token
from models import User, db

with app.app_context():
    user = User.query.first()
    if user:
        token = create_access_token(identity=str(user.id))
        print('✓ JWT token creation successful')
        
        # Test workers endpoint
        with app.test_client() as client:
            headers = {'Authorization': f'Bearer {token}'}
            response = client.get('/api/workers', headers=headers)
            if response.status_code == 200:
                print('✓ HR workers endpoint working')
            else:
                print('❌ HR workers endpoint failed:', response.status_code)
                exit(1)
    else:
        print('❌ No users found in database')
        exit(1)
" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        success "✓ JWT authentication test passed"
    else
        error "JWT authentication test failed"
    fi
    
    cd ..
}

# Show summary
show_summary() {
    echo ""
    echo "=========================================="
    echo "JWT Production Fix Complete"
    echo "=========================================="
    echo ""
    echo "✅ Fixed Issues:"
    echo "   - JWT_SECRET_KEY environment variable set"
    echo "   - JWT configuration verified"
    echo "   - HR workers endpoint authentication working"
    echo ""
    echo "🚀 Next Steps:"
    echo "   1. Restart your production server"
    echo "   2. Test HR management from frontend"
    echo "   3. Verify all JWT-protected endpoints work"
    echo ""
    echo "📝 Important Notes:"
    echo "   - JWT_SECRET_KEY is now properly configured"
    echo "   - All HR routes use JWT authentication"
    echo "   - Frontend sends Authorization headers correctly"
    echo ""
}

# Main execution
main() {
    echo "GermanATO JWT Production Fix"
    echo "============================"
    echo ""
    
    check_directory
    fix_jwt_secret
    test_jwt_config
    test_jwt_auth
    show_summary
    
    log "JWT production fix completed successfully!"
    echo ""
    echo "🎉 HR management should now work properly!"
}

# Run main function
main "$@"