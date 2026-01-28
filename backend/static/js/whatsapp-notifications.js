document.addEventListener("DOMContentLoaded", function () {
  // Set up smart back button logic
  const backBtn = document.getElementById("back-btn");
  const urlParams = new URLSearchParams(window.location.search);
  const fromPage =
    urlParams.get("from") || localStorage.getItem("lastPage") || "admin";

  // Set back button destination based on where user came from
  if (fromPage === "admin") {
    backBtn.href = "admin.html";
  } else if (fromPage === "home") {
    backBtn.href = "home.html";
  } else if (fromPage === "invoiceSystem") {
    backBtn.href = "invoiceSystem.html";
  } else {
    backBtn.href = "admin.html"; // Default fallback
  }

  // Track current page for back button logic
  localStorage.setItem("lastPage", "whatsapp-notifications");

  // Global variables
  let notifications = [];
  let filteredNotifications = [];

  // DOM elements
  const searchInput = document.getElementById("search-input");
  const statusFilter = document.getElementById("status-filter");
  const typeFilter = document.getElementById("type-filter");
  const refreshBtn = document.getElementById("refresh-btn");
  const notificationsList = document.getElementById("notifications-list");
  const loadingSpinner = document.getElementById("loading-spinner");
  const noNotifications = document.getElementById("no-notifications");

  // Event listeners
  searchInput.addEventListener("input", filterNotifications);
  statusFilter.addEventListener("change", filterNotifications);
  typeFilter.addEventListener("change", filterNotifications);
  refreshBtn.addEventListener("click", loadNotifications);

  // Load notifications on page load
  loadNotifications();

  async function loadNotifications() {
    try {
      showLoading(true);

      const data = await APIHelper.get("/api/whatsapp/notifications");
      if (data) {
        notifications = data.notifications || [];
        filteredNotifications = [...notifications];

        updateStats(data.stats);
        renderNotifications();
      } else {
        throw new Error("Failed to load notifications");
      }
    } catch (error) {
      console.error("Error loading notifications:", error);
      showError("Failed to load notifications. Please try again.");
    } finally {
      showLoading(false);
    }
  }

  function updateStats(stats) {
    if (!stats) return;

    document.getElementById("total-sent").textContent = stats.total_sent || 0;
    document.getElementById("total-delivered").textContent =
      stats.total_delivered || 0;
    document.getElementById("total-failed").textContent =
      stats.total_failed || 0;

    const successRate = stats.success_rate || 0;
    document.getElementById(
      "success-rate"
    ).textContent = `${successRate.toFixed(1)}%`;
  }

  function filterNotifications() {
    const searchTerm = searchInput.value.toLowerCase();
    const statusFilterValue = statusFilter.value;
    const typeFilterValue = typeFilter.value;

    filteredNotifications = notifications.filter((notification) => {
      // Search filter
      const matchesSearch =
        notification.customer_name.toLowerCase().includes(searchTerm) ||
        notification.customer_phone.includes(searchTerm) ||
        notification.message_content.toLowerCase().includes(searchTerm);

      // Status filter
      const matchesStatus =
        statusFilterValue === "all" ||
        notification.status === statusFilterValue;

      // Type filter
      const matchesType =
        typeFilterValue === "all" ||
        notification.notification_type === typeFilterValue;

      return matchesSearch && matchesStatus && matchesType;
    });

    renderNotifications();
  }

  function renderNotifications() {
    if (filteredNotifications.length === 0) {
      notificationsList.style.display = "none";
      noNotifications.style.display = "flex";
      return;
    }

    notificationsList.style.display = "block";
    noNotifications.style.display = "none";

    notificationsList.innerHTML = filteredNotifications
      .map((notification) => createNotificationHTML(notification))
      .join("");
  }

  function createNotificationHTML(notification) {
    const statusClass = `status-${notification.status}`;
    const statusText =
      notification.status.charAt(0).toUpperCase() +
      notification.status.slice(1);

    const typeText = notification.notification_type
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");

    const timestamp = new Date(notification.created_at).toLocaleString();

    return `
      <div class="notification-item" data-id="${notification.id}">
        <div class="notification-header">
          <div class="notification-customer">
            <div class="customer-name">${escapeHtml(
              notification.customer_name
            )}</div>
            <div class="customer-phone">${escapeHtml(
              notification.customer_phone
            )}</div>
          </div>
          <div class="notification-status ${statusClass}">
            ${getStatusIcon(notification.status)}
            ${statusText}
          </div>
        </div>
        
        <div class="notification-details">
          <div class="detail-item">
            <div class="detail-label">Type</div>
            <div class="detail-value">${typeText}</div>
          </div>
          <div class="detail-item">
            <div class="detail-label">Document</div>
            <div class="detail-value">${
              notification.related_document_type || "N/A"
            } #${notification.related_document_id || "N/A"}</div>
          </div>
          <div class="detail-item">
            <div class="detail-label">Message ID</div>
            <div class="detail-value">${
              notification.whatsapp_message_id || "N/A"
            }</div>
          </div>
        </div>
        
        <div class="notification-message">${escapeHtml(
          notification.message_content
        )}</div>
        
        ${
          notification.error_message
            ? `
          <div class="notification-error">
            <strong>Error:</strong> ${escapeHtml(notification.error_message)}
          </div>
        `
            : ""
        }
        
        <div class="notification-timestamp">
          Sent: ${timestamp}
          ${
            notification.sent_at
              ? `<br>Delivered: ${new Date(
                  notification.sent_at
                ).toLocaleString()}`
              : ""
          }
        </div>
      </div>
    `;
  }

  function getStatusIcon(status) {
    const icons = {
      sent: "",
      delivered: "",
      failed: "",
      pending: "",
    };
    return icons[status] || "";
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function showLoading(show) {
    if (show) {
      loadingSpinner.style.display = "flex";
      notificationsList.style.display = "none";
      noNotifications.style.display = "none";
    } else {
      loadingSpinner.style.display = "none";
    }
  }

  function showError(message) {
    // Create error notification
    const errorDiv = document.createElement("div");
    errorDiv.className = "error-notification";
    errorDiv.innerHTML = `
      <div class="error-content">
        <span class="error-icon"></span>
        <span class="error-message">${message}</span>
        <button class="error-close" onclick="this.parentElement.parentElement.remove()">×</button>
      </div>
    `;

    // Add error styles
    errorDiv.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      background: #ffebee;
      border: 1px solid #f44336;
      border-radius: 8px;
      padding: 16px;
      color: #c62828;
      z-index: 1000;
      max-width: 400px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    `;

    document.body.appendChild(errorDiv);

    // Auto-remove after 5 seconds
    setTimeout(() => {
      if (errorDiv.parentElement) {
        errorDiv.remove();
      }
    }, 5000);
  }

  // Add click handler for notification items
  notificationsList.addEventListener("click", function (e) {
    const notificationItem = e.target.closest(".notification-item");
    if (notificationItem) {
      const notificationId = notificationItem.dataset.id;
      showNotificationDetails(notificationId);
    }
  });

  function showNotificationDetails(notificationId) {
    const notification = notifications.find((n) => n.id == notificationId);
    if (!notification) return;

    // Create modal for notification details
    const modal = document.createElement("div");
    modal.className = "notification-modal";
    modal.innerHTML = `
      <div class="modal-overlay">
        <div class="modal-content">
          <div class="modal-header">
            <h3>Notification Details</h3>
            <button class="modal-close" onclick="this.closest('.notification-modal').remove()">×</button>
          </div>
          <div class="modal-body">
            <div class="detail-row">
              <strong>Customer:</strong> ${escapeHtml(
                notification.customer_name
              )}
            </div>
            <div class="detail-row">
              <strong>Phone:</strong> ${escapeHtml(notification.customer_phone)}
            </div>
            <div class="detail-row">
              <strong>Type:</strong> ${notification.notification_type}
            </div>
            <div class="detail-row">
              <strong>Status:</strong> ${notification.status}
            </div>
            <div class="detail-row">
              <strong>Created:</strong> ${new Date(
                notification.created_at
              ).toLocaleString()}
            </div>
            ${
              notification.sent_at
                ? `
              <div class="detail-row">
                <strong>Sent:</strong> ${new Date(
                  notification.sent_at
                ).toLocaleString()}
              </div>
            `
                : ""
            }
            ${
              notification.error_message
                ? `
              <div class="detail-row">
                <strong>Error:</strong> ${escapeHtml(
                  notification.error_message
                )}
              </div>
            `
                : ""
            }
            <div class="detail-row">
              <strong>Message:</strong>
            </div>
            <div class="message-content">
              ${escapeHtml(notification.message_content)}
            </div>
          </div>
        </div>
      </div>
    `;

    // Add modal styles
    const style = document.createElement("style");
    style.textContent = `
      .notification-modal {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        z-index: 2000;
      }
      .modal-overlay {
        background: rgba(0,0,0,0.5);
        width: 100%;
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 20px;
      }
      .modal-content {
        background: white;
        border-radius: 12px;
        max-width: 600px;
        width: 100%;
        max-height: 80vh;
        overflow-y: auto;
      }
      .modal-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 20px;
        border-bottom: 1px solid #e9ecef;
      }
      .modal-header h3 {
        margin: 0;
        color: #212529;
      }
      .modal-close {
        background: none;
        border: none;
        font-size: 24px;
        cursor: pointer;
        color: #6c757d;
        padding: 0;
        width: 30px;
        height: 30px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        transition: background-color 0.2s;
      }
      .modal-close:hover {
        background: #f8f9fa;
      }
      .modal-body {
        padding: 20px;
      }
      .detail-row {
        margin-bottom: 12px;
        line-height: 1.5;
      }
      .message-content {
        background: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 16px;
        margin-top: 8px;
        white-space: pre-wrap;
        font-family: monospace;
        font-size: 0.875rem;
        max-height: 300px;
        overflow-y: auto;
      }
    `;
    document.head.appendChild(style);

    document.body.appendChild(modal);
  }
});
