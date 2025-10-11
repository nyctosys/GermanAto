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
  if (fromPage === "home") {
    backBtn.href = "home.html";
  } else if (fromPage === "invoiceSystem") {
    backBtn.href = "invoiceSystem.html";
  } else {
    backBtn.href = "home.html"; // Default fallback
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

// Show user management section
function showUserManagement() {
  // Update active button state
  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.classList.remove("active");
  });
  document
    .querySelector('.nav-btn[onclick="showUserManagement()"]')
    .classList.add("active");

  // Show user management section
  document.getElementById("user-management-section").style.display = "block";
}
