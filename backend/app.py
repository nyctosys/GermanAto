import os
from dotenv import load_dotenv  
load_dotenv() 
from flask import Flask, send_from_directory
from config import Config
from models import db
from routes import bp as invoice_bp
from inventory_routes import inventory_bp
from car_routes import car_bp
from reports_routes import reports_bp
from whatsapp_routes import whatsapp_bp
from auth_routes import auth_bp
from repair_order_routes import repair_order_bp
from expense_routes import expense_routes
from cash_received_routes import cash_received_routes
from flask_cors import CORS
import webbrowser
import threading
from werkzeug.middleware.proxy_fix import ProxyFix 



app = Flask(__name__, static_folder='./static', static_url_path='/static')
app.config.from_object(Config)

# Configure session
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

app.config.update(
    SESSION_COOKIE_SECURE=False,   # Set to True if using HTTPS in production
    SESSION_COOKIE_SAMESITE="Lax", # Avoids CSRF issues while allowing most auth flows
    SESSION_COOKIE_HTTPONLY=True,  # Recommended
    SESSION_COOKIE_NAME="germanato_session",  # Custom session name
    PERMANENT_SESSION_LIFETIME=86400,  # 24 hours in seconds
    SESSION_COOKIE_DOMAIN=None,    # Let Flask auto-detect
    SESSION_COOKIE_PATH="/"        # Available for entire domain
)

# 🔑 Trust Nginx headers (optional but good)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)


# Allow CORS for the API routes with credentials support
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "supports_credentials": True,
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Initialize the database
db.init_app(app)

# Create all database tables
with app.app_context():
    db.create_all()

# Register the blueprint for auth routes
app.register_blueprint(auth_bp, url_prefix='/api/auth')

# Register the blueprint for invoice routes
app.register_blueprint(invoice_bp, url_prefix='/api')

# Register the blueprint for inventory routes
app.register_blueprint(inventory_bp, url_prefix='/api')

# Register the blueprint for car routes
app.register_blueprint(car_bp, url_prefix='/api')

# Register the blueprint for reports routes
app.register_blueprint(reports_bp, url_prefix='/api')

# Register the blueprint for WhatsApp routes
app.register_blueprint(whatsapp_bp, url_prefix='/api')

# Register the blueprint for repair order routes
app.register_blueprint(repair_order_bp, url_prefix='/api')

# Register the blueprint for expense routes
app.register_blueprint(expense_routes, url_prefix='/api')

# Register the blueprint for cash received routes
app.register_blueprint(cash_received_routes, url_prefix='/api')
# Helper function to get the frontend directory
def get_frontend_dir():
    return os.path.join(os.path.dirname(__file__), './frontend')

# Route to serve home.html page
@app.route('/')
def serve_home():
    response = send_from_directory(get_frontend_dir(), 'login.html')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Route to serve home.html page at /home.html
@app.route('/home.html')
def serve_home_page():
    response = send_from_directory(get_frontend_dir(), 'home.html')
    return response

# Route to serve invoiceSystem.html page at /invoiceSystem.html
@app.route('/invoiceSystem.html')
def serve_invoice_system():
    response = send_from_directory(get_frontend_dir(), 'invoiceSystem.html')
    return response

# Route to serve invoice.html page
@app.route('/invoice.html')
def serve_invoice():
    response = send_from_directory(get_frontend_dir(), 'invoice.html')
    return response



# Route to serve invoice-template.html page
@app.route('/invoice-template.html')
def serve_invoice_template():
    response = send_from_directory(get_frontend_dir(), 'invoice-template.html')
    return response

# Route to serve invoice-management.html page
@app.route('/invoice-management.html')
def serve_invoice_management():
    response = send_from_directory(get_frontend_dir(), 'invoice-management.html')
    return response

# Route to serve inventory.html page
@app.route('/inventory.html')
def serve_inventory():
    response = send_from_directory(get_frontend_dir(), 'inventory.html')
    return response

# Route to serve car.html page
@app.route('/car.html')
def serve_car():
    response = send_from_directory(get_frontend_dir(), 'car.html')
    return response

# Route to serve reports.html page
@app.route('/reports.html')
def serve_reports():
    response = send_from_directory(get_frontend_dir(), 'reports.html')
    return response

# Route to serve whatsapp-notifications.html page
@app.route('/whatsapp-notifications.html')
def serve_whatsapp_notifications():
    response = send_from_directory(get_frontend_dir(), 'whatsapp-notifications.html')
    return response

# Route to serve login.html page
@app.route('/login.html')
def serve_login():
    response = send_from_directory(get_frontend_dir(), 'login.html')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Route to serve admin.html page
@app.route('/admin.html')
def serve_admin():
    response = send_from_directory(get_frontend_dir(), 'admin.html')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Route to serve pending-quotes.html page
@app.route('/pending-quotes.html')
def serve_pending_quotes():
    response = send_from_directory(get_frontend_dir(), 'pending-quotes.html')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Route to serve repair-order.html page
@app.route('/repair-order.html')
def serve_repair_order():
    response = send_from_directory(get_frontend_dir(), 'repair-order.html')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/repair-order-template.html')
def serve_repair_order_template():
    response = send_from_directory(get_frontend_dir(), 'repair-order-template.html')
    return response

@app.route('/repair-orders-management.html')
def serve_repair_orders_management():
    response = send_from_directory(get_frontend_dir(), 'repair-orders-management.html')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Route to serve finance-management.html page
@app.route('/finance-management.html')
def serve_finance_management():
    response = send_from_directory(get_frontend_dir(), 'finance-management.html')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/daily-expenses.html')
def serve_daily_expenses():
    response = send_from_directory(get_frontend_dir(), 'daily-expenses.html')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Route to serve low-stock-print.html page
@app.route('/low-stock-print.html')
def serve_low_stock_print():
    response = send_from_directory(get_frontend_dir(), 'low-stock-print.html')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/transaction-history.html')
def serve_transaction_history():
    response = send_from_directory(get_frontend_dir(), 'transaction-history.html')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


# Route to serve static files (js, css, images, etc.)
@app.route('/static/<path:path>')
def serve_static(path):
    response = send_from_directory(os.path.join(get_frontend_dir(), 'static'), path)
    return response

def open_browser():
    webbrowser.open_new("http://127.0.0.1:5001")

if __name__ == '__main__':
    threading.Timer(1, open_browser).start()
    app.run(host="0.0.0.0", port=5001)