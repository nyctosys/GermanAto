document.addEventListener("DOMContentLoaded", () => {
  // Check authentication and page access
  if (!auth.requirePageAccess("repair-orders-management")) {
    return;
  }

  // Set up smart back button logic
  const backBtn = document.getElementById("back-btn");
  const urlParams = new URLSearchParams(window.location.search);
  const fromPage =
    urlParams.get("from") || localStorage.getItem("lastPage") || "admin";

  // Set back button destination based on where user came from
  if (backBtn) {
    if (fromPage === "home") {
      backBtn.href = "home.html";
    } else if (fromPage === "invoiceSystem") {
      backBtn.href = "invoiceSystem.html";
    } else if (fromPage === "dashboard") {
      backBtn.href = "invoiceSystem.html";
    } else if (fromPage === "inventory") {
      backBtn.href = "inventory.html";
    } else if (fromPage === "admin") {
      backBtn.href = "home.html"; // Redirect to home instead of admin panel
    } else {
      backBtn.href = "home.html"; // Default fallback to home
    }
  }

  // Track current page for back button logic
  localStorage.setItem("lastPage", "repair-orders-management");

  // Store the original from parameter for navigation chain preservation
  if (urlParams.get("from")) {
    localStorage.setItem("originalFrom", urlParams.get("from"));
  }

  const resultsDiv = document.getElementById(
    "repair-orders-management-results"
  );
  const btnAll = document.getElementById("show-all");
  const btnReceived = document.getElementById("show-received");
  const btnDiagnosis = document.getElementById("show-diagnosis");
  const btnRepair = document.getElementById("show-repair");
  const btnTesting = document.getElementById("show-testing");
  const btnComplete = document.getElementById("show-complete");

  // Search elements
  const keywordSearch = document.getElementById("keyword-search");
  const idSearch = document.getElementById("id-search");
  const searchBtn = document.getElementById("search-btn");
  const clearSearchBtn = document.getElementById("clear-search-btn");

  // Status mapping for timeline
  const statusOrder = [
    "received",
    "diagnosis",
    "repair",
    "testing",
    "complete",
  ];

  async function loadRepairOrders(status, searchParams = null) {
    APIHelper.renderLoading(resultsDiv, "Loading repair orders...");
    try {
      let url = `/api/repair-orders`;
      const params = new URLSearchParams();

      if (status && status !== "all") {
        params.append("status", status);
      }

      if (searchParams) {
        if (searchParams.keyword) {
          params.append("keyword", searchParams.keyword);
        }
        if (searchParams.id) {
          params.append("id", searchParams.id);
        }
      }

      // Add cache-busting parameter
      params.append("_t", Date.now());

      if (params.toString()) {
        url += `?${params.toString()}`;
      }

      const data = await APIHelper.get(url);
      if (!data) return;
      const repairOrders = data.repair_orders || [];

      if (repairOrders.length === 0) {
        resultsDiv.innerHTML = `<p>No ${
          status && status !== "all" ? status : ""
        } repair orders found.</p>`;
        return;
      }

      let html = '<div class="results-container">';
      html += '<div class="results-column repair-orders-column">';
      html += `<h3>Repair Orders (${repairOrders.length})</h3>`;

      html += repairOrders
        .map((repairOrder) => {
          const currentStatus = repairOrder.current_status || "received";
          const statusClass = `status-${currentStatus}`;

          // Calculate timeline progress
          const timelineHtml = generateTimelinePreview(
            repairOrder.status_timeline || {},
            currentStatus
          );

          // Get last changed status information
          const lastChanged = getLastChangedStatus(repairOrder.status_timeline);
          const lastChangedDisplay = lastChanged.date
            ? formatDate(lastChanged.date)
            : "N/A";

          // Calculate totals
          // Since we removed pricing, totals are now 0
          const partsTotal = 0;
          const labourTotal = 0;
          const totalEstimate = 0;

          return `
          <div class="repair-order-card" id="repair-order-card-${
            repairOrder.id
          }">
            <div class="repair-order-header">
              <div class="repair-order-id">RO #${repairOrder.id}</div>
              <div class="repair-order-status ${statusClass}">${currentStatus.toUpperCase()}</div>
            </div>
            
            <div class="repair-order-info">
              <div class="info-group">
                <div class="info-label">Customer Name</div>
                <div class="info-value">${
                  repairOrder.customer_name || "N/A"
                }${
                  repairOrder.customer_code
                    ? ` <span class="customer-code">${repairOrder.customer_code}</span>`
                    : ""
                }</div>
              </div>
              <div class="info-group">
                <div class="info-label">Phone</div>
                <div class="info-value">${
                  repairOrder.customer_phone || "N/A"
                }</div>
              </div>
              <div class="info-group">
                <div class="info-label">Vehicle</div>
                <div class="info-value">${
                  repairOrder.customer_reg_no || "N/A"
                } - ${repairOrder.customer_made || "N/A"}</div>
              </div>
              <div class="info-group">
                <div class="info-label">Created Date</div>
                <div class="info-value">${formatDate(
                  repairOrder.created_at
                )}</div>
              </div>
              <div class="info-group">
                <div class="info-label">Problem</div>
                <div class="info-value">${truncateText(
                  repairOrder.problem_description || "N/A",
                  50
                )}</div>
              </div>
              <div class="info-group">
                <div class="info-label">Assigned Worker</div>
                <div class="info-value">${
                  repairOrder.worker_name || "Not assigned"
                }</div>
              </div>
                <div class="info-group">
                  <div class="info-label">Last Status Change</div>
                  <div class="info-value">${
                    lastChanged.status.charAt(0).toUpperCase() +
                    lastChanged.status.slice(1)
                  } - ${lastChangedDisplay}</div>
                </div>
            </div>
            
            ${timelineHtml}
            
            <div class="repair-order-actions">
              <div class="action-buttons">
                <button class="view-btn">View</button>
                <button class="history-btn">History</button>
                <button class="edit-btn" ${(currentStatus === "complete" && auth.getCurrentUser().role !== "admin") ? "disabled style='opacity: 0.5; cursor: not-allowed;'" : ""}>Edit</button>
                ${
                  currentStatus === "complete"
                    ? '<button class="generate-invoice-btn">Generate Invoice</button>'
                    : ""
                }
                <button class="delete-btn" ${(currentStatus === "complete" && auth.getCurrentUser().role !== "admin") ? "disabled style='opacity: 0.5; cursor: not-allowed;'" : ""}>Delete</button>
              </div>
              <select class="status-dropdown" data-id="${repairOrder.id}" ${(currentStatus === "complete" && auth.getCurrentUser().role !== "admin") ? "disabled style='opacity: 0.7; cursor: not-allowed;'" : ""}>
                <option value="received" ${
                  currentStatus === "received" ? "selected" : ""
                }>Received</option>
                <option value="diagnosis" ${
                  currentStatus === "diagnosis" ? "selected" : ""
                }>Diagnosis</option>
                <option value="repair" ${
                  currentStatus === "repair" ? "selected" : ""
                }>Repair</option>
                <option value="testing" ${
                  currentStatus === "testing" ? "selected" : ""
                }>Testing</option>
                <option value="complete" ${
                  currentStatus === "complete" ? "selected" : ""
                }>Complete</option>
              </select>
            </div>
          </div>
        `;
        })
        .join("");

      html += "</div></div>";
      resultsDiv.innerHTML = html;

      // Attach event listeners after DOM is updated
      setTimeout(() => {
        repairOrders.forEach((repairOrder) => {
          // Status dropdown
          const statusDropdown = document.querySelector(
            `#repair-order-card-${repairOrder.id} .status-dropdown`
          );
          if (statusDropdown) {
            statusDropdown.addEventListener("change", async (e) => {
              const newStatus = e.target.value;
              const repairOrderId = parseInt(repairOrder.id); // Ensure ID is integer

              try {
                const res = await APIHelper.put(
                  `/api/repair-orders/${repairOrderId}/status`,
                  {
                    status: newStatus,
                    timestamp: new Date().toISOString(),
                  }
                );

                if (res) {
                  // Update the repairOrder object with server response data
                  if (res.status_timeline) {
                    repairOrder.status_timeline = res.status_timeline;
                  }
                  repairOrder.current_status = newStatus;

                  // Update the status display
                  const statusElement = document.querySelector(
                    `#repair-order-card-${repairOrder.id} .repair-order-status`
                  );
                  if (statusElement) {
                    statusElement.textContent = newStatus.toUpperCase();
                    statusElement.className = `repair-order-status status-${newStatus}`;
                  }

                  // Update timeline using server response data
                  const timelineElement = document.querySelector(
                    `#repair-order-card-${repairOrder.id} .timeline-preview`
                  );
                  if (timelineElement && res.status_timeline) {
                    timelineElement.innerHTML = generateTimelinePreview(
                      res.status_timeline,
                      newStatus
                    );
                  }

                  // Update last changed status display using server data
                  const lastChangedElement = document.querySelector(
                    `#repair-order-card-${repairOrder.id} .info-group:last-child .info-value`
                  );
                  if (lastChangedElement && res.status_timeline) {
                    const lastChanged = getLastChangedStatus(res.status_timeline);
                    const lastChangedDisplay = lastChanged.date
                      ? formatDate(lastChanged.date)
                      : "N/A";
                    lastChangedElement.textContent = `${
                      lastChanged.status.charAt(0).toUpperCase() +
                      lastChanged.status.slice(1)
                    } - ${lastChangedDisplay}`;
                  }

                  // Show success message
                  showNotification("Status updated successfully!", "success");
                } else {
                  const errorText = await res.text();
                  showNotification(
                    `Failed to update status: ${res.status}`,
                    "error"
                  );
                }
              } catch (err) {
                showNotification("Error updating status.", "error");
              }
            });
          }

          // View button
          const historyBtn = document.querySelector(
            `#repair-order-card-${repairOrder.id} .history-btn`
          );
          if (historyBtn) {
            historyBtn.addEventListener("click", () =>
              DocumentLog.open("repair-order", repairOrder.id)
            );
          }

          const viewBtn = document.querySelector(
            `#repair-order-card-${repairOrder.id} .view-btn`
          );
          if (viewBtn) {
            viewBtn.addEventListener("click", async () => {
              try {
                const fullRepairOrderData = await APIHelper.get(
                  `/api/repair-orders/${repairOrder.id}`
                );
                if (fullRepairOrderData) {
                  sessionStorage.setItem(
                    "repairOrderData",
                    JSON.stringify(fullRepairOrderData)
                  );
                  sessionStorage.setItem("repairOrderId", repairOrder.id);
                  window.location.href =
                    "repair-order-template.html?from=repair-orders-management";
                } else {
                  showNotification("Repair order not found", "error");
                }
              } catch (err) {
                showNotification("Failed to load repair order data", "error");
              }
            });
          }

          // Edit button
          const editBtn = document.querySelector(
            `#repair-order-card-${repairOrder.id} .edit-btn`
          );
          if (editBtn) {
            editBtn.addEventListener("click", () => {
              // Navigate to repair order edit page (to be created)
              window.location.href = `repair-order.html?id=${repairOrder.id}&from=repair-orders-management`;
            });
          }

          // Generate Invoice button (only for completed repair orders)
          const generateInvoiceBtn = document.querySelector(
            `#repair-order-card-${repairOrder.id} .generate-invoice-btn`
          );
          if (generateInvoiceBtn) {
            generateInvoiceBtn.addEventListener("click", async () => {
              try {
                // Get full repair order data
                const repairOrderData = await APIHelper.get(
                  `/api/repair-orders/${repairOrder.id}`
                );
                if (repairOrderData) {
                  // Store repair order data in session storage for invoice generation
                  sessionStorage.setItem(
                    "repairOrderForInvoice",
                    JSON.stringify(repairOrderData)
                  );

                  // Navigate to invoice generator with repair order data
                  window.location.href = `invoice.html?from=repair-order`;
                } else {
                  showNotification(
                    "Failed to load repair order data.",
                    "error"
                  );
                }
              } catch (err) {
                showNotification(
                  "Error occurred while loading repair order data.",
                  "error"
                );
              }
            });
          }

          // Delete button
          const deleteBtn = document.querySelector(
            `#repair-order-card-${repairOrder.id} .delete-btn`
          );
          if (deleteBtn) {
            deleteBtn.addEventListener("click", async () => {
              if (
                !confirm(
                  "Are you sure you want to delete this repair order? This action cannot be undone."
                )
              ) {
                return;
              }

              try {
                const res = await APIHelper.delete(
                  `/api/repair-orders/${repairOrder.id}`
                );

                if (res) {
                  document
                    .getElementById(`repair-order-card-${repairOrder.id}`)
                    .remove();
                  showNotification(
                    "Repair order deleted successfully!",
                    "success"
                  );
                } else {
                  showNotification("Failed to delete repair order.", "error");
                }
              } catch (err) {
                showNotification(
                  "Error occurred while deleting repair order.",
                  "error"
                );
              }
            });
          }
        });
      }, 100); // Small delay to ensure DOM is updated
    } catch (err) {
      console.error("Error fetching repair orders:", err);
      APIHelper.renderError(resultsDiv, err, () =>
        loadRepairOrders(status, searchParams)
      );
    }
  }

  // Generate timeline preview HTML
  function generateTimelinePreview(statusTimeline, currentStatus) {
    let html = '<div class="timeline-preview">';

    statusOrder.forEach((status, index) => {
      const isCurrent = status === currentStatus;
      const stepClass = isCurrent ? "current" : "";

      html += `
        <div class="timeline-step ${stepClass}">
          <div class="timeline-dot"></div>
          <span>${status.charAt(0).toUpperCase() + status.slice(1)}</span>
        </div>
      `;
    });

    html += "</div>";
    return html;
  }

  // Format date with time
  function formatDate(dateString) {
    if (!dateString) return "N/A";
    const date = new Date(dateString);
    return date.toLocaleString("en-PK", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  // Format currency
  function formatCurrency(amount) {
    return new Intl.NumberFormat("en-PK", {
      style: "currency",
      currency: "PKR",
      minimumFractionDigits: 2,
    }).format(amount || 0);
  }

  // Get last changed status and its date/time
  function getLastChangedStatus(statusTimeline) {
    if (!statusTimeline || Object.keys(statusTimeline).length === 0) {
      return { status: "received", date: null, time: null };
    }

    let lastStatus = "received";
    let lastDateTimestamp = null;
    let lastDate = null;
    let lastTime = null;

    // Find the most recent status change by comparing timestamps
    Object.keys(statusTimeline).forEach((status) => {
      const statusData = statusTimeline[status];
      if (statusData && statusData.date) {
        try {
          const statusDate = new Date(statusData.date);
          // Check if date is valid
          if (!isNaN(statusDate.getTime())) {
            const statusTimestamp = statusDate.getTime();
            // Compare timestamps to find the most recent
            if (lastDateTimestamp === null || statusTimestamp > lastDateTimestamp) {
              lastStatus = status;
              lastDateTimestamp = statusTimestamp;
              lastDate = statusData.date;
              lastTime = statusData.time;
            }
          }
        } catch (e) {
          // Skip invalid dates
          console.warn(`Invalid date for status ${status}:`, statusData.date);
        }
      }
    });

    return { status: lastStatus, date: lastDate, time: lastTime };
  }

  // Truncate text
  function truncateText(text, maxLength) {
    if (!text) return "N/A";
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + "...";
  }

  // Show notification
  function showNotification(message, type = "info") {
    // Create notification element
    const notification = document.createElement("div");
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 12px 20px;
      border-radius: 6px;
      color: white;
      font-weight: 600;
      z-index: 10000;
      animation: slideIn 0.3s ease;
    `;

    // Set background color based on type
    switch (type) {
      case "success":
        notification.style.backgroundColor = "#28a745";
        break;
      case "error":
        notification.style.backgroundColor = "#dc3545";
        break;
      case "warning":
        notification.style.backgroundColor = "#ffc107";
        notification.style.color = "#000";
        break;
      default:
        notification.style.backgroundColor = "#17a2b8";
    }

    // Add to page
    document.body.appendChild(notification);

    // Remove after 3 seconds
    setTimeout(() => {
      notification.style.animation = "slideOut 0.3s ease";
      setTimeout(() => {
        if (notification.parentNode) {
          notification.parentNode.removeChild(notification);
        }
      }, 300);
    }, 3000);
  }

  // Add CSS animations for notifications
  const style = document.createElement("style");
  style.textContent = `
    @keyframes slideIn {
      from { transform: translateX(100%); opacity: 0; }
      to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
      from { transform: translateX(0); opacity: 1; }
      to { transform: translateX(100%); opacity: 0; }
    }
  `;
  document.head.appendChild(style);

  // Button event listeners
  btnAll.addEventListener("click", () => {
    setActiveButton(btnAll);
    loadRepairOrders("all");
  });

  btnReceived.addEventListener("click", () => {
    setActiveButton(btnReceived);
    loadRepairOrders("received");
  });

  btnDiagnosis.addEventListener("click", () => {
    setActiveButton(btnDiagnosis);
    loadRepairOrders("diagnosis");
  });

  btnRepair.addEventListener("click", () => {
    setActiveButton(btnRepair);
    loadRepairOrders("repair");
  });

  btnTesting.addEventListener("click", () => {
    setActiveButton(btnTesting);
    loadRepairOrders("testing");
  });

  btnComplete.addEventListener("click", () => {
    setActiveButton(btnComplete);
    loadRepairOrders("complete");
  });

  // Search event listeners
  searchBtn.addEventListener("click", () => {
    performSearch();
  });

  clearSearchBtn.addEventListener("click", () => {
    clearSearch();
  });

  // Enter key support for search
  keywordSearch.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
      performSearch();
    }
  });

  idSearch.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
      performSearch();
    }
  });

  // Show/hide clear button based on input
  function updateClearButton() {
    const hasInput = keywordSearch.value.trim() || idSearch.value.trim();
    clearSearchBtn.style.display = hasInput ? "block" : "none";
  }

  keywordSearch.addEventListener("input", updateClearButton);
  idSearch.addEventListener("input", updateClearButton);

  // Search functions
  function performSearch() {
    const keyword = keywordSearch.value.trim();
    const id = idSearch.value.trim();

    if (!keyword && !id) {
      showNotification("Please enter a keyword or ID to search", "warning");
      return;
    }

    const searchParams = {};
    if (keyword) searchParams.keyword = keyword;
    if (id) searchParams.id = id;

    // Get current active status
    const activeStatus = getActiveStatus();
    loadRepairOrders(activeStatus, searchParams);
  }

  function clearSearch() {
    keywordSearch.value = "";
    idSearch.value = "";
    clearSearchBtn.style.display = "none";
    const activeStatus = getActiveStatus();
    loadRepairOrders(activeStatus);
  }

  function getActiveStatus() {
    if (btnAll.classList.contains("active")) return "all";
    if (btnReceived.classList.contains("active")) return "received";
    if (btnDiagnosis.classList.contains("active")) return "diagnosis";
    if (btnRepair.classList.contains("active")) return "repair";
    if (btnTesting.classList.contains("active")) return "testing";
    if (btnComplete.classList.contains("active")) return "complete";
    return "all";
  }

  // Set active button
  function setActiveButton(activeBtn) {
    [
      btnAll,
      btnReceived,
      btnDiagnosis,
      btnRepair,
      btnTesting,
      btnComplete,
    ].forEach((btn) => {
      btn.classList.remove("active");
    });
    activeBtn.classList.add("active");
  }

  // Create Repair Order button event listener
  const createRepairOrderBtn = document.getElementById(
    "create-repair-order-btn"
  );
  if (createRepairOrderBtn) {
    createRepairOrderBtn.addEventListener("click", () => {
      // Navigate to repair order form with from parameter
      window.location.href = "repair-order.html?from=repair-orders-management";
    });
  }

  // Initial load
  loadRepairOrders("all");
});
