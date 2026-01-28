// Vendor Detail JavaScript

let currentVendor = null;
let currentVendorId = null;
let ledgerEntries = [];
let consignments = [];
let deleteItemId = null;
let deleteItemType = null;

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  // Wait for auth to be available
  if (typeof auth === "undefined" || !auth.requirePageAccess) {
    console.error("Auth not available, retrying...");
    setTimeout(() => {
      if (typeof auth !== "undefined" && auth.requirePageAccess) {
        initializeVendorDetail();
      } else {
        console.error("Auth still not available after retry");
        window.location.href = "login.html";
      }
    }, 100);
    return;
  }

  initializeVendorDetail();
});

function initializeVendorDetail() {
  // Check authentication and access
  if (!auth.requirePageAccess("vendor-detail")) {
    return;
  }

  // Get vendor ID from URL
  const pathParts = window.location.pathname.split("/");
  currentVendorId = parseInt(pathParts[pathParts.length - 1]);

  if (currentVendorId) {
    loadVendorDetails();
    setupEventListeners();
    setupBackButton();
  } else {
    showError("Invalid vendor ID");
  }
}

// Setup back button
function setupBackButton() {
  const backBtn = document.getElementById("back-btn");
  if (backBtn) {
    backBtn.addEventListener("click", function (e) {
      e.preventDefault();
      window.location.href = "/vendors";
    });
  }
}

// Tab switching functions
function switchTab(tabName) {
  // Hide all tab panes
  const tabPanes = document.querySelectorAll(".tab-pane");
  tabPanes.forEach((pane) => {
    pane.classList.remove("active");
  });

  // Remove active class from all tab buttons
  const tabBtns = document.querySelectorAll(".tab-btn");
  tabBtns.forEach((btn) => {
    btn.classList.remove("active");
  });

  // Show selected tab pane
  const selectedPane = document.getElementById(tabName);
  if (selectedPane) {
    selectedPane.classList.add("active");
  }

  // Add active class to selected tab button
  const selectedBtn = document.getElementById(tabName + "-tab");
  if (selectedBtn) {
    selectedBtn.classList.add("active");
  }

  // Load data for the selected tab
  if (tabName === "ledger") {
    loadLedgerEntries();
  } else if (tabName === "consignments") {
    loadConsignments();
  }
}

// Modal functions
function showModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.style.display = "flex";
    modal.classList.add("show");
  }
}

function hideModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.style.display = "none";
    modal.classList.remove("show");
  }
}

function openLedgerModal() {
  resetLedgerForm();
  showModal("ledgerModal");
}

function closeLedgerModal() {
  hideModal("ledgerModal");
  resetLedgerForm();
}

function openConsignmentModal() {
  resetConsignmentForm();
  showModal("consignmentModal");
}

function closeConsignmentModal() {
  hideModal("consignmentModal");
  resetConsignmentForm();
}

function openDeleteModal(itemId, itemType, itemName) {
  deleteItemId = itemId;
  deleteItemType = itemType;
  const deleteMessage = document.getElementById("deleteMessage");
  if (deleteMessage) {
    deleteMessage.textContent = `Are you sure you want to delete ${itemType} "${itemName}"? This action cannot be undone.`;
  }
  showModal("deleteModal");
}

function closeDeleteModal() {
  hideModal("deleteModal");
  deleteItemId = null;
  deleteItemType = null;
}

// Setup event listeners
function setupEventListeners() {
  // Tab switching is handled by onclick attributes in HTML
  // Export buttons are handled by onclick attributes in HTML
  // Modal functions are handled by our custom modal system

  // Save ledger entry
  const saveLedgerBtn = document.getElementById("saveLedgerBtn");
  if (saveLedgerBtn) {
    saveLedgerBtn.addEventListener("click", function () {
      saveLedgerEntry();
    });
  }

  // Save consignment
  const saveConsignmentBtn = document.getElementById("saveConsignmentBtn");
  if (saveConsignmentBtn) {
    saveConsignmentBtn.addEventListener("click", function (e) {
      e.preventDefault();
      saveConsignment();
    });
  }

  // Auto-calculate consignment amount
  const consignmentQuantity = document.getElementById("consignmentQuantity");
  if (consignmentQuantity) {
    consignmentQuantity.addEventListener("input", calculateConsignmentAmount);
  }

  const consignmentRate = document.getElementById("consignmentRate");
  if (consignmentRate) {
    consignmentRate.addEventListener("input", calculateConsignmentAmount);
  }

  // Delete confirmation
  const confirmDeleteBtn = document.getElementById("confirmDeleteBtn");
  if (confirmDeleteBtn) {
    confirmDeleteBtn.addEventListener("click", function () {
      confirmDelete();
    });
  }
}

// Load vendor details
async function loadVendorDetails() {
  try {
    const data = await APIHelper.get(`/api/vendors/${currentVendorId}`);
    if (!data) return;

    currentVendor = data;
    displayVendorInfo(data);
    loadLedgerEntries(); // Load ledger by default
  } catch (error) {
    console.error("Error loading vendor details:", error);
    showError("Error loading vendor details. Please try again.");
  }
}

// Display vendor information
function displayVendorInfo(vendor) {
  // Update header elements
  const vendorName = document.getElementById("vendorName");
  const vendorCompany = document.getElementById("vendorCompany");
  if (vendorName) {
    vendorName.textContent = `${vendor.name} - ${vendor.company_name}`;
  }
  if (vendorCompany) {
    vendorCompany.style.display = "none";
  }

  // Update vendor info card elements
  const vendorInfoName = document.getElementById("vendorInfoName");
  const vendorInfoCompany = document.getElementById("vendorInfoCompany");
  if (vendorInfoName) {
    vendorInfoName.textContent = vendor.name;
  }
  if (vendorInfoCompany) {
    vendorInfoCompany.textContent = vendor.company_name;
  }

  // Update vendor details section
  const vendorInfo = document.getElementById("vendorInfo");
  if (vendorInfo) {
    vendorInfo.innerHTML = `
        <div class="vendor-detail-item">
            <div class="vendor-detail-label">Vendor Name</div>
            <div class="vendor-detail-value">${vendor.name}</div>
        </div>
        <div class="vendor-detail-item">
            <div class="vendor-detail-label">Company Name</div>
            <div class="vendor-detail-value">${vendor.company_name}</div>
        </div>
        <div class="vendor-detail-item">
            <div class="vendor-detail-label">Contact Person</div>
            <div class="vendor-detail-value">${vendor.contact_person}</div>
        </div>
        <div class="vendor-detail-item">
            <div class="vendor-detail-label">Phone</div>
            <div class="vendor-detail-value">${vendor.phone}</div>
        </div>
        <div class="vendor-detail-item">
            <div class="vendor-detail-label">Email</div>
            <div class="vendor-detail-value">${vendor.email || "N/A"}</div>
        </div>
        <div class="vendor-detail-item">
            <div class="vendor-detail-label">CNIC</div>
            <div class="vendor-detail-value">${vendor.cnic || "N/A"}</div>
        </div>
        <div class="vendor-detail-item">
            <div class="vendor-detail-label">Address</div>
            <div class="vendor-detail-value">${vendor.address}</div>
        </div>
    `;
  }
}

// Load ledger entries
async function loadLedgerEntries() {
  try {
    showLedgerLoading();

    const startDate = document.getElementById("ledgerStartDate").value;
    const endDate = document.getElementById("ledgerEndDate").value;

    let url = `/api/vendors/${currentVendorId}/ledger`;
    const params = new URLSearchParams();

    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);

    if (params.toString()) {
      url += "?" + params.toString();
    }

    const data = await APIHelper.get(url);
    if (!data) return;

    ledgerEntries = data;
    renderLedgerTable(data);
    calculateLedgerTotals(data);
  } catch (error) {
    console.error("Error loading ledger entries:", error);
    showError("Error loading ledger entries. Please try again.");
  }
}

// Render ledger table
function renderLedgerTable(entries) {
  const tbody = document.getElementById("ledgerTableBody");

  if (entries.length === 0) {
    tbody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center text-muted">
                    <i class="fas fa-inbox"></i> No ledger entries found
                </td>
            </tr>
        `;
    return;
  }

  tbody.innerHTML = entries
    .map(
      (entry) => `
        <tr>
            <td>${formatDate(entry.created_at)}</td>
            <td>${entry.description}</td>
            <td>${entry.folio || "N/A"}</td>
            <td class="currency ${
              entry.debit > 0 ? "positive" : ""
            }">${formatCurrency(entry.debit)}</td>
            <td class="currency ${
              entry.credit > 0 ? "positive" : ""
            }">${formatCurrency(entry.credit)}</td>
            <td class="currency ${
              entry.balance >= 0 ? "positive" : "negative"
            }">${formatCurrency(entry.balance)}</td>
            <td>
              <button
                class="action-btn delete-btn"
                onclick="deleteLedgerEntry(${entry.id})"
                title="Delete Entry"
              >
                Delete
              </button>
            </td>
        </tr>
    `
    )
    .join("");
}

// Calculate ledger totals
function calculateLedgerTotals(entries) {
  const totalDebit = entries.reduce(
    (sum, entry) => sum + parseFloat(entry.debit),
    0
  );
  const totalCredit = entries.reduce(
    (sum, entry) => sum + parseFloat(entry.credit),
    0
  );
  const closingBalance =
    entries.length > 0 ? parseFloat(entries[0].balance) : 0;

  document.getElementById("totalDebit").textContent =
    formatCurrency(totalDebit);
  document.getElementById("totalCredit").textContent =
    formatCurrency(totalCredit);
  document.getElementById("closingBalance").textContent =
    formatCurrency(closingBalance);
}

// Load consignments
async function loadConsignments() {
  try {
    showConsignmentLoading();

    const startDate = document.getElementById("consignmentStartDate").value;
    const endDate = document.getElementById("consignmentEndDate").value;
    const invoiceNo = document.getElementById("consignmentInvoiceNo").value;

    let url = `/api/vendors/${currentVendorId}/consignments`;
    const params = new URLSearchParams();

    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    if (invoiceNo) params.append("invoice_no", invoiceNo);

    if (params.toString()) {
      url += "?" + params.toString();
    }

    const data = await APIHelper.get(url);
    if (!data) return;

    consignments = data;
    renderConsignmentsTable(data);
  } catch (error) {
    console.error("Error loading consignments:", error);
    showError("Error loading consignments. Please try again.");
  }
}

// Render consignments table
function renderConsignmentsTable(consignmentsList) {
  const tbody = document.getElementById("consignmentsTableBody");

  if (consignmentsList.length === 0) {
    tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center text-muted">
                    <i class="fas fa-inbox"></i> No consignment records found
                </td>
            </tr>
        `;
    return;
  }

  tbody.innerHTML = consignmentsList
    .map(
      (consignment) => `
        <tr>
            <td>${formatDate(consignment.created_at)}</td>
            <td>${consignment.invoice_no}</td>
            <td>${consignment.item_name}</td>
            <td>${consignment.quantity}</td>
            <td class="currency">${formatCurrency(consignment.rate)}</td>
            <td class="currency positive">${formatCurrency(
              consignment.amount
            )}</td>
            <td>${consignment.remarks || "N/A"}</td>
            <td>
                <button class="action-btn delete-btn" onclick="deleteConsignment(${
                  consignment.id
                })" title="Delete">
                    Delete
                </button>
            </td>
        </tr>
    `
    )
    .join("");
}

// Save ledger entry
async function saveLedgerEntry() {
  const form = document.getElementById("ledgerForm");
  if (!form.checkValidity()) {
    form.reportValidity();
    return;
  }

  const entryData = {
    vendor_id: currentVendorId,
    date: document.getElementById("ledgerDate").value,
    description: document.getElementById("ledgerDescription").value.trim(),
    folio: document.getElementById("ledgerFolio").value.trim() || null,
    debit: parseFloat(document.getElementById("ledgerDebit").value) || 0,
    credit: parseFloat(document.getElementById("ledgerCredit").value) || 0,
  };

  try {
    const data = await APIHelper.post("/api/ledger/add", entryData);
    if (!data) return;

    showSuccess(data.message);
    loadLedgerEntries();
    hideModal("ledgerModal");
  } catch (error) {
    console.error("Error saving ledger entry:", error);
    showError("Error saving ledger entry. Please try again.");
  }
}

// Save consignment entry
async function saveConsignment() {
  const form = document.getElementById("consignmentForm");
  if (!form.checkValidity()) {
    form.reportValidity();
    return;
  }

  // Get form values
  const date = document.getElementById("consignmentDate").value;
  const invoiceNo = document
    .getElementById("consignmentFormInvoiceNo")
    .value.trim();
  const itemName = document.getElementById("consignmentItemName").value.trim();
  const quantity = document.getElementById("consignmentQuantity").value;
  const rate = document.getElementById("consignmentRate").value;
  const remarks = document.getElementById("consignmentRemarks").value.trim();

  // Validate required fields
  if (!date || !invoiceNo || !itemName || !quantity || !rate) {
    showError("Please fill in all required fields");
    return;
  }

  const consignmentData = {
    vendor_id: currentVendorId,
    date: date,
    invoice_no: invoiceNo,
    item_name: itemName,
    quantity: parseInt(quantity),
    rate: parseFloat(rate),
    remarks: remarks || null,
  };

  try {
    const data = await APIHelper.post("/api/consignments/add", consignmentData);
    if (!data) return;

    showSuccess(data.message);
    loadConsignments();
    hideModal("consignmentModal");
    resetConsignmentForm();
  } catch (error) {
    showError("Error saving consignment. Please try again.");
  }
}

// Calculate consignment amount
function calculateConsignmentAmount() {
  const quantity =
    parseFloat(document.getElementById("consignmentQuantity").value) || 0;
  const rate =
    parseFloat(document.getElementById("consignmentRate").value) || 0;
  const amount = quantity * rate;

  // Amount is calculated automatically in the backend
  // No need to set a field value here
}

// Delete consignment
function deleteConsignment(consignmentId) {
  deleteItemId = consignmentId;
  deleteItemType = "consignment";
  const deleteMessage = document.getElementById("deleteMessage");
  if (deleteMessage) {
    deleteMessage.textContent =
      "Are you sure you want to delete this consignment record?";
  }
  showModal("deleteModal");
}

// Delete vendor
function deleteVendor() {
  deleteItemId = currentVendorId;
  deleteItemType = "vendor";
  const deleteMessage = document.getElementById("deleteMessage");
  if (deleteMessage) {
    deleteMessage.textContent =
      "Are you sure you want to delete this vendor? This will also delete all associated ledger entries and consignment records.";
  }
  showModal("deleteModal");
}

// Delete ledger entry
function deleteLedgerEntry(ledgerId) {
  deleteItemId = ledgerId;
  deleteItemType = "ledger";
  const deleteMessage = document.getElementById("deleteMessage");
  if (deleteMessage) {
    deleteMessage.textContent =
      "Are you sure you want to delete this ledger entry?";
  }
  showModal("deleteModal");
}

// Confirm delete
async function confirmDelete() {
  if (!deleteItemId || !deleteItemType) return;

  try {
    let url, message;

    if (deleteItemType === "vendor") {
      url = `/api/vendors/${deleteItemId}`;
      message = "Vendor deleted successfully";
    } else if (deleteItemType === "consignment") {
      url = `/api/consignments/${deleteItemId}`;
      message = "Consignment record deleted successfully";
    } else if (deleteItemType === "ledger") {
      url = `/api/ledger/${deleteItemId}`;
      message = "Ledger entry deleted successfully";
    }

    const data = await APIHelper.delete(url);
    if (!data) return;

    showSuccess(message);

    if (deleteItemType === "vendor") {
      window.location.href = "/vendors";
    } else if (deleteItemType === "consignment") {
      loadConsignments();
    } else if (deleteItemType === "ledger") {
      loadLedgerEntries();
    }

    hideModal("deleteModal");
  } catch (error) {
    console.error("Error deleting item:", error);
    showError("Error deleting item. Please try again.");
  }
}

// Edit vendor (redirect to vendors page with edit mode)
function editVendor() {
  window.location.href = `/vendors?edit=${currentVendorId}`;
}

// Filter functions
function filterLedger() {
  loadLedgerEntries();
}

function clearLedgerFilter() {
  document.getElementById("ledgerStartDate").value = "";
  document.getElementById("ledgerEndDate").value = "";
  loadLedgerEntries();
}

function filterConsignments() {
  loadConsignments();
}

// Export functions
function exportLedger(format) {
  if (format === "excel") {
    exportLedgerToExcel();
  }
}

function exportConsignment(format) {
  if (format === "excel") {
    exportConsignmentToExcel();
  }
}

// Export ledger to Excel
function exportLedgerToExcel() {
  try {
    const table = document.getElementById("ledgerTable");
    if (!table) {
      showError("Ledger table not found");
      return;
    }

    const ws = XLSX.utils.table_to_sheet(table);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Ledger Statement");

    const fileName = `ledger_${currentVendorId}_${
      new Date().toISOString().split("T")[0]
    }.xlsx`;
    XLSX.writeFile(wb, fileName);

    showInfo("Ledger exported to Excel successfully!");
  } catch (error) {
    console.error("Error exporting ledger to Excel:", error);
    showError("Failed to export ledger to Excel");
  }
}

// Export consignments to Excel
function exportConsignmentToExcel() {
  try {
    const table = document.getElementById("consignmentsTable");
    if (!table) {
      showError("Consignment table not found");
      return;
    }

    const ws = XLSX.utils.table_to_sheet(table);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Consignment Reports");

    const fileName = `consignments_${currentVendorId}_${
      new Date().toISOString().split("T")[0]
    }.xlsx`;
    XLSX.writeFile(wb, fileName);

    showInfo("Consignments exported to Excel successfully!");
  } catch (error) {
    console.error("Error exporting consignments to Excel:", error);
    showError("Failed to export consignments to Excel");
  }
}

// Reset forms
function resetLedgerForm() {
  document.getElementById("ledgerForm").reset();
  document.getElementById("ledgerDate").value = new Date()
    .toISOString()
    .split("T")[0];
}

function resetConsignmentForm() {
  document.getElementById("consignmentForm").reset();
  document.getElementById("consignmentDate").value = new Date()
    .toISOString()
    .split("T")[0];
}

// Show loading states
function showLedgerLoading() {
  const tbody = document.getElementById("ledgerTableBody");
  tbody.innerHTML = `
        <tr>
            <td colspan="6" class="text-center">
                <div class="spinner-border" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </td>
        </tr>
    `;
}

function showConsignmentLoading() {
  const tbody = document.getElementById("consignmentsTableBody");
  tbody.innerHTML = `
        <tr>
            <td colspan="8" class="text-center">
                <div class="spinner-border" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </td>
        </tr>
    `;
}

// Notification functions are now imported from notification-utils.js

// Format date for display
function formatDate(dateString) {
  if (!dateString) return "N/A";

  // Handle the format "2025-10-07 10:08:14" by treating it as UTC time
  let date;
  if (dateString.includes(" ")) {
    // If it contains a space, it's likely in "YYYY-MM-DD HH:MM:SS" format
    // Add 'Z' to indicate UTC time, then convert to Pakistan time
    const isoString = dateString.replace(" ", "T") + "Z";
    date = new Date(isoString);
  } else {
    date = new Date(dateString);
  }

  // Check if date is valid
  if (isNaN(date.getTime())) {
    console.error("Invalid date string:", dateString);
    return "Invalid Date";
  }

  // Format for Pakistan time (UTC+5)
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Karachi",
  });
}

// Format currency for display
function formatCurrency(amount) {
  return new Intl.NumberFormat("en-PK", {
    style: "currency",
    currency: "PKR",
    minimumFractionDigits: 2,
  }).format(amount);
}
