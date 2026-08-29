from flask import request
import logging
import os
from werkzeug.utils import secure_filename
import time

logger = logging.getLogger(__name__)

UPLOAD_FOLDER = 'static/uploads'

def save_uploaded_file(file):
    """Save an uploaded file securely with a unique timestamp prefix."""
    if not file or file.filename == '':
        return None
    try:
        sec_filename = secure_filename(file.filename)
        # Add timestamp prefix to prevent name collisions
        unique_name = f"{int(time.time())}_{sec_filename}"
        
        # Ensure the uploads directory exists
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        file_path = os.path.join(UPLOAD_FOLDER, unique_name)
        file.save(file_path)
        
        # Return path relative to static/
        return f"uploads/{unique_name}"
    except Exception as e:
        logger.error(f"Error saving uploaded file: {e}")
        return None

def log_action(user, action, module, reference_id, details):
    """Log an application action to the database."""
    try:
        from models import db, AppLog
        
        # Get IP address from flask request safely
        ip_address = None
        try:
            if request:
                ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
                if ip_address and ',' in ip_address:
                    ip_address = ip_address.split(',')[0].strip()
        except RuntimeError:
            # Not in request context (e.g. CLI script)
            pass
        
        user_id = user.id if user else None
        username = user.username if user else 'anonymous/system'
        
        log_entry = AppLog(
            user_id=user_id,
            username=username,
            action=action,
            module=module,
            reference_id=reference_id,
            details=details,
            ip_address=ip_address
        )
        db.session.add(log_entry)
        db.session.flush()  # Ensure ID is populated, outer commit will write to DB
        logger.info(f"AppLog: [{username}] {action} in {module} ({reference_id}): {details}")
    except Exception as e:
        logger.error(f"Failed to write app log: {e}")
