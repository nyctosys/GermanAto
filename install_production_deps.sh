#!/bin/bash

# Production Server Dependencies Installation Script
# This script installs missing dependencies for the Germanato App

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
    
    if [ ! -f "backend/requirements.txt" ]; then
        error "requirements.txt not found. Please run this script from the project root."
    fi
    
    log "✓ Directory structure verified"
}

# Check Python version
check_python() {
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is not installed. Please install Python 3 first."
    fi
    
    python_version=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
    log "✓ Python version: $python_version"
}

# Check pip
check_pip() {
    if ! command -v pip3 &> /dev/null; then
        error "pip3 is not installed. Please install pip3 first."
    fi
    
    log "✓ pip3 is available"
}

# Install missing dependencies
install_dependencies() {
    log "Installing missing dependencies..."
    
    # Install Flask-JWT-Extended specifically
    log "Installing Flask-JWT-Extended..."
    pip3 install Flask-JWT-Extended==4.6.0
    
    if [ $? -eq 0 ]; then
        success "✓ Flask-JWT-Extended installed successfully"
    else
        error "Failed to install Flask-JWT-Extended"
    fi
    
    # Install other missing dependencies if any
    log "Installing other dependencies from requirements.txt..."
    pip3 install -r backend/requirements.txt
    
    if [ $? -eq 0 ]; then
        success "✓ All dependencies installed successfully"
    else
        warning "Some dependencies may have failed to install. Check the output above."
    fi
}

# Verify installation
verify_installation() {
    log "Verifying Flask-JWT-Extended installation..."
    
    python3 -c "
import flask_jwt_extended
print('✓ Flask-JWT-Extended version:', flask_jwt_extended.__version__)
print('✓ Import successful')
" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        success "✓ Flask-JWT-Extended verification successful"
    else
        error "Flask-JWT-Extended verification failed"
    fi
}

# Test application import
test_application() {
    log "Testing application imports..."
    
    cd backend
    
    python3 -c "
try:
    from flask_jwt_extended import JWTManager
    print('✓ JWTManager import successful')
    
    from flask_jwt_extended import jwt_required, get_jwt_identity
    print('✓ JWT decorators import successful')
    
    print('✓ All JWT imports working correctly')
except ImportError as e:
    print('❌ Import error:', e)
    exit(1)
" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        success "✓ Application imports test passed"
    else
        error "Application imports test failed"
    fi
    
    cd ..
}

# Show installation summary
show_summary() {
    echo ""
    echo "=========================================="
    echo "Dependencies Installation Summary"
    echo "=========================================="
    echo ""
    echo "✅ Installed Packages:"
    echo "   - Flask-JWT-Extended==4.6.0"
    echo "   - All packages from requirements.txt"
    echo ""
    echo "✅ Verification:"
    echo "   - Flask-JWT-Extended import successful"
    echo "   - JWT decorators working"
    echo "   - Application imports verified"
    echo ""
    echo "🚀 Next Steps:"
    echo "   1. Restart your application server"
    echo "   2. Test JWT authentication endpoints"
    echo "   3. Verify all routes are working"
    echo ""
    echo "📝 If you still get import errors:"
    echo "   - Check your Python virtual environment"
    echo "   - Ensure you're using the correct Python version"
    echo "   - Try: pip3 install --upgrade Flask-JWT-Extended"
    echo ""
}

# Main execution
main() {
    echo "GermanATO Production Dependencies Installation"
    echo "=============================================="
    echo ""
    
    check_directory
    check_python
    check_pip
    install_dependencies
    verify_installation
    test_application
    show_summary
    
    log "Dependencies installation completed successfully!"
    echo ""
    echo "🎉 Your Germanato app dependencies are now installed!"
}

# Run main function
main "$@"

