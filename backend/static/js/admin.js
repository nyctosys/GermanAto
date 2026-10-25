// Global variables
let currentEditId = null;
let users = [];

// Initialize the page
document.addEventListener("DOMContentLoaded", function () {
  // Wait for auth to be available
  if (typeof auth === "undefined" || !auth.requirePageAccess) {
    console.error("Auth not available, retrying...");
    setTimeout(() => {
      if (typeof auth !== "undefined" && auth.requirePageAccess) {
        initializeAdmin();
      } else {
        console.error("Auth still not available after retry");
        window.location.href = "login.html";
      }
    }, 100);
    return;
  }

  initializeAdmin();
});

function initializeAdmin() {
  // Check authentication and admin access
  if (!auth.requirePageAccess("admin")) {
    return;
  }

  // Set up smart back button logic
  const backBtn = document.getElementById("back-btn");
  const urlParams = new URLSearchParams(window.location.search);
  const fromPage =
    urlParams.get("from") || localStorage.getItem("lastPage") || "home";

  // Set back button destination based on where user came from
  if (backBtn) {
    if (fromPage === "home") {
      backBtn.href = "home.html";
    } else if (fromPage === "invoiceSystem") {
      backBtn.href = "invoiceSystem.html";
    } else {
      backBtn.href = "home.html"; // Default fallback
    }
  }

  // Track current page for back button logic
  localStorage.setItem("lastPage", "admin");

  loadUsers();
  setupEventListeners();
}

// Setup event listeners
function setupEventListeners() {
  // Form submission
  document
    .getElementById("user-form")
    .addEventListener("submit", handleFormSubmit);

  // Modal close on outside click
  document.getElementById("user-modal").addEventListener("click", function (e) {
    if (e.target === this) {
      closeModal();
    }
  });
}

// Load users
async function loadUsers() {
  try {
    users = await APIHelper.get("/api/auth/users");
    renderUsers();
  } catch (error) {
    console.error("Error loading users:", error);
    showError("Error loading users. Please check your connection.");
  }
}

// Render users table
function renderUsers() {
  const table = document.getElementById("users-table");

  if (users.length === 0) {
    table.innerHTML = `
            <div style="padding: 40px; text-align: center; color: #6c757d;">
                <h3>No users found</h3>
                <p>Click "Add New User" to get started</p>
            </div>
        `;
    return;
  }

  table.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>Username</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th>Last Login</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${users
                  .map(
                    (user) => `
                    <tr>
                        <td>${user.username}</td>
                        <td>${user.email}</td>
                        <td><span class="role-badge role-${
                          user.role
                        }">${user.role.replace("_", " ")}</span></td>
                        <td>${user.is_active ? "Active" : "Inactive"}</td>
                        <td>${
                          user.created_at
                            ? new Date(user.created_at).toLocaleDateString()
                            : "N/A"
                        }</td>
                        <td>${
                          user.last_login
                            ? new Date(user.last_login).toLocaleDateString()
                            : "Never"
                        }</td>
                        <td class="user-actions">
                            <button class="action-btn edit-btn" onclick="editUser(${
                              user.id
                            })">Edit</button>
                            <button class="action-btn delete-btn" onclick="deleteUser(${
                              user.id
                            })">Delete</button>
                        </td>
                    </tr>
                `
                  )
                  .join("")}
            </tbody>
        </table>
    `;
}

// Open add modal
function openAddUserModal() {
  currentEditId = null;
  document.getElementById("modal-title").textContent = "Add New User";
  document.getElementById("user-form").reset();
  document.getElementById("user-modal").style.display = "block";
}

// Open edit modal
function editUser(id) {
  const user = users.find((user) => user.id === id);
  if (!user) return;

  currentEditId = id;
  document.getElementById("modal-title").textContent = "Edit User";

  // Fill form with user data
  document.getElementById("username").value = user.username;
  document.getElementById("email").value = user.email;
  document.getElementById("role").value = user.role;
  document.getElementById("password").value = ""; // Don't show password
  document.getElementById("password").required = false; // Make password optional for edit

  document.getElementById("user-modal").style.display = "block";
}

// Close modal
function closeModal() {
  document.getElementById("user-modal").style.display = "none";
  currentEditId = null;
  document.getElementById("password").required = true; // Reset password requirement
}

// Handle form submission
async function handleFormSubmit(e) {
  e.preventDefault();

  const formData = new FormData(e.target);
  const userData = {
    username: formData.get("username"),
    email: formData.get("email"),
    role: formData.get("role"),
    password: formData.get("password"),
  };

  try {
    if (currentEditId) {
      // Update existing user
      await updateUser(currentEditId, userData);
    } else {
      // Add new user
      await addUser(userData);
    }

    closeModal();
    loadUsers();
  } catch (error) {
    console.error("Error saving user:", error);
    showError("Error saving user. Please try again.");
  }
}

// Add user
async function addUser(userData) {
  return await APIHelper.post("/api/auth/register", userData);
}

// Update user
async function updateUser(id, userData) {
  return await APIHelper.put(`/api/auth/users/${id}`, userData);
}

// Delete user
async function deleteUser(id) {
  if (!confirm("Are you sure you want to delete this user?")) {
    return;
  }

  try {
    await APIHelper.delete(`/api/auth/users/${id}`);
    users = users.filter((user) => user.id !== id);
    renderUsers();
  } catch (error) {
    console.error("Error deleting user:", error);
    showError("Error deleting user. Please try again.");
  }
}

// Tab Switching Logic
function switchTab(tab) {
  // Hide all sections, remove active class from all tab buttons
  document.querySelectorAll(".tab-section").forEach((sec) => (sec.style.display = "none"));
  document.querySelectorAll(".tab-btn").forEach((btn) => btn.classList.remove("active"));

  if (tab === "users") {
    document.getElementById("users-section").style.display = "block";
    document.getElementById("users-tab-btn").classList.add("active");
  } else if (tab === "permissions") {
    document.getElementById("permissions-section").style.display = "block";
    document.getElementById("permissions-tab-btn").classList.add("active");
    loadRolePermissions();
  } else if (tab === "logs") {
    document.getElementById("logs-section").style.display = "block";
    document.getElementById("logs-tab-btn").classList.add("active");
    loadLogs(1);
  }
}

// Logs Filtering State
let currentLogsPage = 1;

// Load App Action Logs
async function loadLogs(page = 1) {
  currentLogsPage = page;
  const username = document.getElementById("filter-username").value.trim();
  const module = document.getElementById("filter-module").value;
  const action = document.getElementById("filter-action").value;
  const startDate = document.getElementById("filter-start-date").value;
  const endDate = document.getElementById("filter-end-date").value;
  const keyword = document.getElementById("filter-keyword").value.trim();

  let url = `/api/admin/app-logs?page=${page}&per_page=50`;
  if (username) url += `&username=${encodeURIComponent(username)}`;
  if (module) url += `&module=${encodeURIComponent(module)}`;
  if (action) url += `&action=${encodeURIComponent(action)}`;
  if (startDate) url += `&start_date=${encodeURIComponent(startDate)}`;
  if (endDate) url += `&end_date=${encodeURIComponent(endDate)}`;
  if (keyword) url += `&keyword=${encodeURIComponent(keyword)}`;

  try {
    const data = await APIHelper.get(url);
    renderLogs(data.logs);
    renderLogsPagination(data.current_page, data.pages);
  } catch (error) {
    console.error("Error loading app logs:", error);
    showError("Failed to load logs. Please try again.");
  }
}

// Render Logs Table
function renderLogs(logs) {
  const table = document.getElementById("logs-table");

  if (!logs || logs.length === 0) {
    table.innerHTML = `
            <div style="padding: 40px; text-align: center; color: #6c757d;">
                <h3>No logs found</h3>
                <p>Try adjusting your search filters.</p>
            </div>
        `;
    return;
  }

  table.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th style="width: 160px;">Timestamp</th>
                    <th style="width: 100px;">User</th>
                    <th style="width: 120px;">Module</th>
                    <th style="width: 140px;">Action</th>
                    <th style="width: 100px;">Ref ID</th>
                    <th>Details</th>
                    <th style="width: 130px;">IP Address</th>
                </tr>
            </thead>
            <tbody>
                ${logs
                  .map(
                    (log) => `
                    <tr>
                        <td style="font-family: monospace; font-size: 11px;">${log.created_at || "N/A"}</td>
                        <td><strong>${log.username || "system"}</strong></td>
                        <td><span class="role-badge role-accountant">${log.module}</span></td>
                        <td><span class="role-badge role-admin">${log.action}</span></td>
                        <td>${log.reference_id || "-"}</td>
                        <td style="font-size: 13px;">${log.details}</td>
                        <td style="font-family: monospace; font-size: 12px; color: var(--text-muted);">${log.ip_address || "-"}</td>
                    </tr>
                `
                  )
                  .join("")}
            </tbody>
        </table>
    `;
}

// Render Logs Pagination Controls
function renderLogsPagination(currentPage, totalPages) {
  const container = document.getElementById("logs-pagination");
  if (totalPages <= 1) {
    container.innerHTML = "";
    return;
  }

  container.innerHTML = `
        <button class="page-btn" ${currentPage === 1 ? "disabled" : ""} onclick="loadLogs(${currentPage - 1})">Previous</button>
        <span class="page-info">Page ${currentPage} of ${totalPages}</span>
        <button class="page-btn" ${currentPage === totalPages ? "disabled" : ""} onclick="loadLogs(${currentPage + 1})">Next</button>
    `;
}

// Filter Actions
function applyLogsFilters() {
  loadLogs(1);
}

function resetLogsFilters() {
  document.getElementById("filter-username").value = "";
  document.getElementById("filter-module").value = "";
  document.getElementById("filter-action").value = "";
  document.getElementById("filter-start-date").value = "";
  document.getElementById("filter-end-date").value = "";
  document.getElementById("filter-keyword").value = "";
  loadLogs(1);
}

// Load Role Permissions from backend and check appropriate checkboxes
async function loadRolePermissions() {
  try {
    const data = await APIHelper.get("/api/auth/roles-permissions");
    if (!data) return;

    // Reset all checkboxes first
    document.querySelectorAll(".perm-chk").forEach(chk => chk.checked = false);

    // Populate accountant permissions
    if (data.accountant) {
      data.accountant.forEach(perm => {
        const chk = document.querySelector(`.accountant-chk[value="${perm}"]`);
        if (chk) chk.checked = true;
      });
    }

    // Populate inventory manager permissions
    if (data.inventory_manager) {
      data.inventory_manager.forEach(perm => {
        const chk = document.querySelector(`.inventory-chk[value="${perm}"]`);
        if (chk) chk.checked = true;
      });
    }
  } catch (error) {
    console.error("Error loading role permissions:", error);
    showError("Failed to load role permissions");
  }
}

// Save role permissions to backend
async function saveRolePermissions() {
  try {
    const accountantPerms = [];
    document.querySelectorAll(".accountant-chk:checked").forEach(chk => {
      accountantPerms.push(chk.value);
    });

    const inventoryPerms = [];
    document.querySelectorAll(".inventory-chk:checked").forEach(chk => {
      inventoryPerms.push(chk.value);
    });

    const payload = {
      accountant: accountantPerms,
      inventory_manager: inventoryPerms
    };

    const res = await APIHelper.request("/api/auth/roles-permissions", {
      method: "PUT",
      body: JSON.stringify(payload)
    });

    if (res) {
      showSuccess("Role permissions saved successfully!");
      if (typeof auth !== "undefined") {
        await auth.loadPermissions();
      }
    }
  } catch (error) {
    console.error("Error saving role permissions:", error);
    showError("Failed to save role permissions");
  }
}
