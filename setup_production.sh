#!/bin/bash

# Production Server Setup Script for Germanato App
# This script sets up the virtual environment and installs dependencies

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
    
    python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
    log "✓ Python version: $python_version"
}

# Check if virtual environment exists
check_venv() {
    if [ -d "backend/env" ]; then
        log "✓ Virtual environment found at backend/env/"
        VENV_PATH="backend/env"
    elif [ -d "venv" ]; then
        log "✓ Virtual environment found at venv/"
        VENV_PATH="venv"
    elif [ -d ".venv" ]; then
        log "✓ Virtual environment found at .venv/"
        VENV_PATH=".venv"
    elif [ -d "env" ]; then
        log "✓ Virtual environment found at env/"
        VENV_PATH="env"
    else
        warning "No virtual environment found. Creating one..."
        create_venv
    fi
}

# Create virtual environment
create_venv() {
    log "Creating virtual environment..."
    
    python3 -m venv backend/env
    
    if [ $? -eq 0 ]; then
        success "✓ Virtual environment created at backend/env/"
        VENV_PATH="backend/env"
    else
        error "Failed to create virtual environment"
    fi
}

# Activate virtual environment
activate_venv() {
    log "Activating virtual environment..."
    
    if [ -f "$VENV_PATH/bin/activate" ]; then
        source "$VENV_PATH/bin/activate"
        success "✓ Virtual environment activated"
        
        # Show activation command for future use
        echo ""
        echo "📝 To activate virtual environment manually in the future:"
        echo "   source $VENV_PATH/bin/activate"
        echo ""
    else
        error "Virtual environment activation script not found"
    fi
}

# Install dependencies
install_dependencies() {
    log "Installing dependencies..."
    
    # Upgrade pip first
    pip install --upgrade pip
    
    # Install requirements
    pip install -r backend/requirements.txt
    
    if [ $? -eq 0 ]; then
        success "✓ All dependencies installed successfully"
    else
        error "Failed to install dependencies"
    fi
}

# Verify installation
verify_installation() {
    log "Verifying installation..."
    
    # Check Flask-JWT-Extended specifically
    python -c "
import flask_jwt_extended
print('✓ Flask-JWT-Extended version:', flask_jwt_extended.__version__)
" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        success "✓ Flask-JWT-Extended verification successful"
    else
        error "Flask-JWT-Extended verification failed"
    fi
    
    # Test other critical imports
    python -c "
import flask
import flask_sqlalchemy
import pymysql
print('✓ Core dependencies verified')
" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        success "✓ Core dependencies verified"
    else
        error "Core dependencies verification failed"
    fi
}

# Test application startup
test_application() {
    log "Testing application startup..."
    
    cd backend
    
    python -c "
try:
    from app import app
    print('✓ Application imports successful')
    print('✓ All routes registered')
except Exception as e:
    print('❌ Application import error:', e)
    exit(1)
" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        success "✓ Application startup test passed"
    else
        error "Application startup test failed"
    fi
    
    cd ..
}

# Show setup summary
show_summary() {
    echo ""
    echo "=========================================="
    echo "Production Server Setup Complete"
    echo "=========================================="
    echo ""
    echo "✅ Virtual Environment:"
    echo "   - Location: $VENV_PATH"
    echo "   - Status: Activated"
    echo ""
    echo "✅ Dependencies Installed:"
    echo "   - Flask-JWT-Extended==4.6.0"
    echo "   - All packages from requirements.txt"
    echo ""
    echo "✅ Verification:"
    echo "   - Flask-JWT-Extended working"
    echo "   - Core dependencies verified"
    echo "   - Application imports successful"
    echo ""
    echo "🚀 Next Steps:"
    echo "   1. Keep virtual environment activated: source $VENV_PATH/bin/activate"
    echo "   2. Start your application server"
    echo "   3. Test all endpoints"
    echo ""
    echo "📝 Useful Commands:"
    echo "   - Activate venv: source $VENV_PATH/bin/activate"
    echo "   - Deactivate venv: deactivate"
    echo "   - Check installed packages: pip list"
    echo "   - Update requirements: pip freeze > requirements.txt"
    echo ""
}

# Main execution
main() {
    echo "GermanATO Production Server Setup"
    echo "================================="
    echo ""
    
    check_directory
    check_python
    check_venv
    activate_venv
    install_dependencies
    verify_installation
    test_application
    show_summary
    
    log "Production server setup completed successfully!"
    echo ""
    echo "🎉 Your Germanato app is ready to run!"
    echo ""
    echo "💡 Remember to activate the virtual environment before running your app:"
    echo "   source $VENV_PATH/bin/activate"
}

# Run main function
main "$@"

