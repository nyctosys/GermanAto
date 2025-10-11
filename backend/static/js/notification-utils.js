// Notification utility functions for consistent UI feedback across the app

// Show success notification
function showSuccess(message) {
  // Ensure DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => showSuccess(message));
    return;
  }

  const alertDiv = document.createElement("div");
  alertDiv.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 9999;
    min-width: 300px;
    max-width: 400px;
    padding: 15px 20px;
    background-color: #d4edda;
    color: #155724;
    border: 1px solid #c3e6cb;
    border-radius: 4px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    font-family: Arial, sans-serif;
    font-size: 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    animation: slideIn 0.3s ease-out;
  `;
  
  alertDiv.innerHTML = `
    <span style="display: flex; align-items: center;">
      <span style="color: #28a745; margin-right: 8px; font-size: 16px;">✓</span>
      ${message}
    </span>
    <button type="button" onclick="this.parentElement.remove()" style="
      background: none;
      border: none;
      color: #155724;
      font-size: 18px;
      cursor: pointer;
      padding: 0;
      margin-left: 10px;
    ">&times;</button>
  `;

  // Add CSS animation if not already added
  if (!document.getElementById('notification-styles')) {
    const style = document.createElement('style');
    style.id = 'notification-styles';
    style.textContent = `
      @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
      }
    `;
    document.head.appendChild(style);
  }

  document.body.appendChild(alertDiv);

  setTimeout(() => {
    if (alertDiv.parentNode) {
      alertDiv.remove();
    }
  }, 3000);
}

// Show error notification
function showError(message) {
  // Ensure DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => showError(message));
    return;
  }

  const alertDiv = document.createElement("div");
  alertDiv.className = "alert alert-danger alert-dismissible fade show position-fixed";
  alertDiv.style.cssText = "top: 20px; right: 20px; z-index: 9999; min-width: 300px; max-width: 400px;";
  alertDiv.innerHTML = `
    <i class="fas fa-exclamation-circle"></i> ${message}
    <button type="button" class="close" onclick="this.parentElement.remove()">&times;</button>
  `;

  document.body.appendChild(alertDiv);

  setTimeout(() => {
    if (alertDiv.parentNode) {
      alertDiv.remove();
    }
  }, 5000);
}

// Show info notification
function showInfo(message) {
  const alertDiv = document.createElement("div");
  alertDiv.className = "alert alert-info alert-dismissible fade show position-fixed";
  alertDiv.style.cssText = "top: 20px; right: 20px; z-index: 9999; min-width: 300px; max-width: 400px;";
  alertDiv.innerHTML = `
    <i class="fas fa-info-circle"></i> ${message}
    <button type="button" class="close" onclick="this.parentElement.remove()">&times;</button>
  `;

  document.body.appendChild(alertDiv);

  setTimeout(() => {
    if (alertDiv.parentNode) {
      alertDiv.remove();
    }
  }, 3000);
}

// Show warning notification
function showWarning(message) {
  const alertDiv = document.createElement("div");
  alertDiv.className = "alert alert-warning alert-dismissible fade show position-fixed";
  alertDiv.style.cssText = "top: 20px; right: 20px; z-index: 9999; min-width: 300px; max-width: 400px;";
  alertDiv.innerHTML = `
    <i class="fas fa-exclamation-triangle"></i> ${message}
    <button type="button" class="close" onclick="this.parentElement.remove()">&times;</button>
  `;

  document.body.appendChild(alertDiv);

  setTimeout(() => {
    if (alertDiv.parentNode) {
      alertDiv.remove();
    }
  }, 4000);
}
