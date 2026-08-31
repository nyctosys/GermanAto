// Vendor Management JavaScript

let vendors = [];
let currentVendorId = null;

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  // Wait for auth to be available
  if (typeof auth === "undefined" || !auth.requirePageAccess) {
    console.error("Auth not available, retrying...");
    setTimeout(() => {
      if (typeof auth !== "undefined" && auth.requirePageAccess) {
        initializeVendors();
      } else {
        console.error("Auth still not available after retry");
        window.location.href = "login.html";
      }
    }, 100);
    return;
  }

  initializeVendors();
});

function initializeVendors() {
  // Check authentication and access
  if (!auth.requirePageAccess("vendors")) {
    return;
  }

  loadVendors();
  setupEventListeners();
  setupBackButton();
}

// Setup back button
function setupBackButton() {
  const backBtn = document.getElementById("back-btn");
  if (backBtn) {
    backBtn.addEventListener("click", function (e) {
      e.preventDefault();
      window.location.href = "/home.html";
    });
  }
}

// Setup event listeners
function setupEventListeners() {
  // Search functionality
  const searchInput = document.getElementById("searchInput");
  if (searchInput) {
    searchInput.addEventListener("input", function () {
      const searchTerm = this.value.toLowerCase();
      filterVendors(searchTerm);
    });
  }

  // Refresh button
  const refreshBtn = document.getElementById("refreshBtn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", function () {
      loadVendors();
    });
  }

  // Save vendor button
  const saveVendorBtn = document.getElementById("saveVendorBtn");
  if (saveVendorBtn) {
    saveVendorBtn.addEventListener("click", function () {
      saveVendor();
    });
  }

  // Delete confirmation
  const confirmDeleteBtn = document.getElementById("confirmDeleteBtn");
  if (confirmDeleteBtn) {
    confirmDeleteBtn.addEventListener("click", function () {
      confirmDelete();
    });
  }
}

// Modal functions
function openAddVendorModal() {
  currentVendorId = null;
  document.getElementById("vendorModalTitle").textContent = "Add New Vendor";
  resetVendorForm();
  showModal("vendorModal");
}

function closeVendorModal() {
  hideModal("vendorModal");
  resetVendorForm();
}

function openDeleteModal(vendorId, vendorName) {
  currentVendorId = vendorId;
  const deleteMessage = document.getElementById("deleteMessage");
  if (deleteMessage) {
    deleteMessage.textContent = `Are you sure you want to delete vendor "${vendorName}"? This action cannot be undone and will also delete all associated ledger entries and consignment records.`;
  }
  showModal("deleteModal");
}

function closeDeleteModal() {
  hideModal("deleteModal");
  currentVendorId = null;
}

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

function searchVendors() {
  const searchTerm = document.getElementById("searchInput").value.toLowerCase();
  filterVendors(searchTerm);
}

// Load vendors from API
async function loadVendors() {
  try {
    showLoading();
    const data = await APIHelper.get("/api/vendors");
    // The endpoint returns { vendors: [...] }; tolerate the older bare array
    // so a stale cached script cannot blank the page.
    const rows = Array.isArray(data) ? data : data && data.vendors;
    if (!Array.isArray(rows)) return;

    vendors = rows;
    renderVendorsTable(vendors);
  } catch (error) {
    console.error("Error loading vendors:", error);
    APIHelper.renderError("vendorsTableBody", error, loadVendors);
  }
}

// Render vendors table
function renderVendorsTable(vendorsList) {
  const tbody = document.getElementById("vendorsTableBody");

  if (vendorsList.length === 0) {
    APIHelper.renderEmpty(tbody, "No vendors found");
    return;
  }

  const esc = (value) => APIHelper.escapeHtml(value ?? "");

  tbody.innerHTML = vendorsList
    .map(
      (vendor) => `
        <tr>
            <td>${vendor.id}</td>
            <td>${esc(vendor.name)}</td>
            <td>${esc(vendor.company_name)}</td>
            <td>${esc(vendor.contact_person)}</td>
            <td>${esc(vendor.phone)}</td>
            <td>${esc(vendor.email || "N/A")}</td>
            <td>${formatDate(vendor.created_at)}</td>
            <td>
                <div class="action-buttons">
                    <button class="action-btn view-btn" onclick="viewVendor(${
                      vendor.id
                    })" title="View Details">
                        View
                    </button>
                    <button class="action-btn edit-btn" onclick="editVendor(${
                      vendor.id
                    })" title="Edit">
                        Edit
                    </button>
                    <button class="action-btn delete-btn" onclick="deleteVendor(${
                      vendor.id
                    })" title="Delete">
                        Delete
                    </button>
                </div>
            </td>
        </tr>
    `
    )
    .join("");
}

// Filter vendors based on search term
function filterVendors(searchTerm) {
  const filteredVendors = vendors.filter((vendor) =>
    ["name", "company_name", "contact_person", "phone", "email"].some((field) =>
      String(vendor[field] || "")
        .toLowerCase()
        .includes(searchTerm)
    )
  );
  renderVendorsTable(filteredVendors);
}

// View vendor details
function viewVendor(vendorId) {
  window.location.href = `/vendors/${vendorId}`;
}

// Edit vendor
function editVendor(vendorId) {
  const vendor = vendors.find((v) => v.id === vendorId);
  if (!vendor) return;

  currentVendorId = vendorId;

  // Populate form
  document.getElementById("vendorId").value = vendor.id;
  document.getElementById("vendorName").value = vendor.name;
  document.getElementById("companyName").value = vendor.company_name;
  document.getElementById("contactPerson").value = vendor.contact_person;
  document.getElementById("phone").value = vendor.phone;
  document.getElementById("email").value = vendor.email || "";
  document.getElementById("cnic").value = vendor.cnic || "";
  document.getElementById("address").value = vendor.address;

  // Update modal title
  document.getElementById("vendorModalTitle").textContent = "Edit Vendor";

  // Show modal
  showModal("vendorModal");
}

// Delete vendor
function deleteVendor(vendorId) {
  currentVendorId = vendorId;
  const vendor = vendors.find((v) => v.id === vendorId);
  if (vendor) {
    openDeleteModal(vendorId, vendor.name);
  }
}

// Confirm delete
async function confirmDelete() {
  if (!currentVendorId) return;

  try {
    const data = await APIHelper.delete(`/api/vendors/${currentVendorId}`);
    if (!data) return;

    showSuccess("Vendor deleted successfully");
    loadVendors();
    hideModal("deleteModal");
  } catch (error) {
    console.error("Error deleting vendor:", error);
    showError(error.message || "Error deleting vendor. Please try again.");
  }
}

// Save vendor (create or update)
async function saveVendor() {
  const form = document.getElementById("vendorForm");
  if (!form.checkValidity()) {
    form.reportValidity();
    return;
  }

  const vendorData = {
    name: document.getElementById("vendorName").value.trim(),
    company_name: document.getElementById("companyName").value.trim(),
    contact_person: document.getElementById("contactPerson").value.trim(),
    phone: document.getElementById("phone").value.trim(),
    email: document.getElementById("email").value.trim() || null,
    address: document.getElementById("address").value.trim(),
    cnic: document.getElementById("cnic").value.trim() || null,
  };

  try {
    const url = currentVendorId
      ? `/api/vendors/${currentVendorId}`
      : "/api/vendors";
    const method = currentVendorId ? "PUT" : "POST";

    const data =
      method === "POST"
        ? await APIHelper.post(url, vendorData)
        : await APIHelper.put(url, vendorData);

    if (!data) return;

    showSuccess(data.message);
    loadVendors();
    hideModal("vendorModal");
  } catch (error) {
    console.error("Error saving vendor:", error);
    showError(error.message || "Error saving vendor. Please try again.");
  }
}

// Reset vendor form
function resetVendorForm() {
  document.getElementById("vendorForm").reset();
  document.getElementById("vendorId").value = "";
  document.getElementById("vendorModalTitle").textContent = "Add New Vendor";
  currentVendorId = null;
}

// Show loading state
function showLoading() {
  APIHelper.renderLoading("vendorsTableBody", "Loading vendors...");
}

// Using global notification functions from notification-utils.js

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
