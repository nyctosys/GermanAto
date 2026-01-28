// Settings Page JavaScript

let editingDepartmentId = null;
let editingCategoryId = null;

// Initialize page
document.addEventListener("DOMContentLoaded", function () {
  // Check authentication
  if (!auth.requirePageAccess("settings")) {
    return;
  }

  // Load theme preference
  loadThemePreference();

  // Load departments and categories
  loadDepartments();
  loadCategories();

  // Setup event listeners
  setupEventListeners();
});

// Setup event listeners
function setupEventListeners() {
  // Theme selector
  const themeSelect = document.getElementById("theme-select");
  if (themeSelect) {
    themeSelect.addEventListener("change", handleThemeChange);
  }

  // Department form
  const departmentForm = document.getElementById("department-form");
  if (departmentForm) {
    departmentForm.addEventListener("submit", handleDepartmentSubmit);
  }

  // Category form
  const categoryForm = document.getElementById("category-form");
  if (categoryForm) {
    categoryForm.addEventListener("submit", handleCategorySubmit);
  }

  // Close modals when clicking outside
  window.addEventListener("click", function (event) {
    const departmentModal = document.getElementById("department-modal");
    const categoryModal = document.getElementById("category-modal");

    if (event.target === departmentModal) {
      closeDepartmentModal();
    }
    if (event.target === categoryModal) {
      closeCategoryModal();
    }
  });
}

// ===== THEME MANAGEMENT =====

function loadThemePreference() {
  const savedTheme = localStorage.getItem("theme") || "light";
  const themeSelect = document.getElementById("theme-select");
  
  // Apply theme using global function (from theme.js)
  if (window.applyGlobalTheme) {
    window.applyGlobalTheme(savedTheme);
  }
  
  if (themeSelect) {
    themeSelect.value = savedTheme;
  }
}

function handleThemeChange(event) {
  const theme = event.target.value;
  localStorage.setItem("theme", theme);
  
  // Apply theme using global function (from theme.js)
  if (window.applyGlobalTheme) {
    window.applyGlobalTheme(theme);
  }
  
  showNotification(`Theme changed to ${theme}`, "success");
}

// ===== DEPARTMENT MANAGEMENT =====

async function loadDepartments() {
  try {
    // Load departments from central Settings
    const [departmentsResponse, workersResponse] = await Promise.all([
      APIHelper.get("/api/settings/departments?include_inactive=true"),
      APIHelper.get("/api/workers")
    ]);
    
    if (departmentsResponse && departmentsResponse.departments) {
      // Count workers per department
      const workerCounts = {};
      if (workersResponse && workersResponse.workers) {
        workersResponse.workers.forEach(worker => {
          const deptName = worker.department;
          if (deptName) {
            workerCounts[deptName] = (workerCounts[deptName] || 0) + 1;
          }
        });
      }
      
      displayDepartments(departmentsResponse.departments, workerCounts);
    }
  } catch (error) {
    console.error("Error loading departments:", error);
    showNotification("Failed to load departments", "error");
  }
}

function displayDepartments(departments, workerCounts = {}) {
  const tbody = document.getElementById("departments-tbody");
  if (!tbody) return;

  if (departments.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align: center; padding: 24px; color: var(--text-muted);">
          No departments found. Click "Add Department" to create one.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = departments
    .map(
      (dept) => {
        const workerCount = workerCounts[dept.name] || 0;
        return `
    <tr>
      <td>${dept.id}</td>
      <td><strong>${escapeHtml(dept.name)}</strong></td>
      <td>${escapeHtml(dept.description || "-")}</td>
      <td>
        <span class="usage-count">${workerCount} ${workerCount === 1 ? 'worker' : 'workers'}</span>
      </td>
      <td>
        <div class="action-buttons">
          <button class="action-btn edit-btn" onclick="editDepartment(${dept.id})">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
            </svg>
            Edit
          </button>
          <button class="action-btn delete-btn" onclick="deleteDepartment(${dept.id}, '${escapeHtml(dept.name)}')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
            Delete
          </button>
        </div>
      </td>
    </tr>
  `;
      }
    )
    .join("");
}

function openDepartmentModal(departmentId = null) {
  // Set editingDepartmentId first, before any async operations
  editingDepartmentId = departmentId;
  
  const modal = document.getElementById("department-modal");
  const form = document.getElementById("department-form");
  const title = document.getElementById("department-modal-title");

  if (departmentId) {
    title.textContent = "Edit Department";
    // Load department data
    loadDepartmentData(departmentId);
  } else {
    title.textContent = "Add Department";
    form.reset();
    // Ensure editingDepartmentId is null for new entries
    editingDepartmentId = null;
  }

  modal.classList.add("show");
}

function closeDepartmentModal() {
  const modal = document.getElementById("department-modal");
  modal.classList.remove("show");
  editingDepartmentId = null;
  document.getElementById("department-form").reset();
}

async function loadDepartmentData(departmentId) {
  try {
    // Ensure editingDepartmentId is set before loading data
    editingDepartmentId = departmentId;
    
    const response = await APIHelper.get("/api/settings/departments");
    
    if (response && response.departments) {
      const department = response.departments.find((d) => d.id === departmentId);
      if (department) {
        document.getElementById("department-name").value = department.name;
        document.getElementById("department-description").value =
          department.description || "";
        // Ensure editingDepartmentId is still set after loading
        editingDepartmentId = departmentId;
      } else {
        console.error("Department not found with ID:", departmentId);
        showNotification("Department not found", "error");
        closeDepartmentModal();
      }
    }
  } catch (error) {
    console.error("Error loading department data:", error);
    showNotification("Failed to load department data", "error");
    closeDepartmentModal();
  }
}

async function editDepartment(departmentId) {
  openDepartmentModal(departmentId);
}

async function handleDepartmentSubmit(event) {
  event.preventDefault();

  // Store the editingDepartmentId in a local variable to prevent it from being lost
  const currentEditingId = editingDepartmentId;

  const formData = {
    name: document.getElementById("department-name").value.trim(),
    description: document.getElementById("department-description").value.trim(),
  };

  if (!formData.name) {
    showNotification("Department name is required", "error");
    return;
  }

  try {
    let response;
    // Check if we're editing (currentEditingId should be set)
    if (currentEditingId !== null && currentEditingId !== undefined && currentEditingId !== 0) {
      // Update existing department
      response = await APIHelper.put(
        `/api/settings/departments/${currentEditingId}`,
        formData
      );
      if (response && response.department) {
        showNotification("Department updated successfully", "success");
        closeDepartmentModal();
        loadDepartments();
      } else {
        throw new Error("Update failed - no response received");
      }
    } else {
      // Create new department
      response = await APIHelper.post("/api/settings/departments", formData);
      if (response && response.department) {
        showNotification("Department created successfully", "success");
        closeDepartmentModal();
        loadDepartments();
      } else {
        throw new Error("Create failed - no response received");
      }
    }
  } catch (error) {
    console.error("Error saving department:", error);
    const errorMessage =
      error.message || "Failed to save department. Please try again.";
    showNotification(errorMessage, "error");
    // Don't close modal on error so user can fix and retry
  }
}

async function deleteDepartment(departmentId, departmentName) {
  if (
    !confirm(
      `Are you sure you want to delete the department "${departmentName}"? This action cannot be undone.`
    )
  ) {
    return;
  }

  try {
    await APIHelper.delete(`/api/settings/departments/${departmentId}`);
    showNotification("Department deleted successfully", "success");
    loadDepartments();
  } catch (error) {
    console.error("Error deleting department:", error);
    const errorMessage =
      error.message || "Failed to delete department. Please try again.";
    showNotification(errorMessage, "error");
  }
}

// ===== CATEGORY MANAGEMENT =====

async function loadCategories() {
  try {
    // Load categories from central Settings
    const [categoriesResponse, inventoryResponse] = await Promise.all([
      APIHelper.get("/api/settings/categories?include_inactive=true"),
      APIHelper.get("/api/inventory?per_page=1000")
    ]);
    
    if (categoriesResponse && categoriesResponse.categories) {
      // Count items per category
      const itemCounts = {};
      if (inventoryResponse && inventoryResponse.items) {
        inventoryResponse.items.forEach(item => {
          const catName = item.category;
          if (catName) {
            itemCounts[catName] = (itemCounts[catName] || 0) + 1;
          }
        });
      }
      
      displayCategories(categoriesResponse.categories, itemCounts);
    }
  } catch (error) {
    console.error("Error loading categories:", error);
    showNotification("Failed to load categories", "error");
  }
}

function displayCategories(categories, itemCounts = {}) {
  const tbody = document.getElementById("categories-tbody");
  if (!tbody) return;

  if (categories.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align: center; padding: 24px; color: var(--text-muted);">
          No categories found. Click "Add Category" to create one.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = categories
    .map(
      (cat) => {
        const itemCount = itemCounts[cat.name] || 0;
        return `
    <tr>
      <td>${cat.id}</td>
      <td><strong>${escapeHtml(cat.name)}</strong></td>
      <td>${escapeHtml(cat.description || "-")}</td>
      <td>
        <span class="usage-count">${itemCount} ${itemCount === 1 ? 'item' : 'items'}</span>
      </td>
      <td>
        <div class="action-buttons">
          <button class="action-btn edit-btn" onclick="editCategory(${cat.id})">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
            </svg>
            Edit
          </button>
          <button class="action-btn delete-btn" onclick="deleteCategory(${cat.id}, '${escapeHtml(cat.name)}')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
            Delete
          </button>
        </div>
      </td>
    </tr>
  `;
      }
    )
    .join("");
}

function openCategoryModal(categoryId = null) {
  // Set editingCategoryId first, before any async operations
  editingCategoryId = categoryId;
  
  const modal = document.getElementById("category-modal");
  const form = document.getElementById("category-form");
  const title = document.getElementById("category-modal-title");

  if (categoryId) {
    title.textContent = "Edit Category";
    // Load category data
    loadCategoryData(categoryId);
  } else {
    title.textContent = "Add Category";
    form.reset();
    // Ensure editingCategoryId is null for new entries
    editingCategoryId = null;
  }

  modal.classList.add("show");
}

function closeCategoryModal() {
  const modal = document.getElementById("category-modal");
  modal.classList.remove("show");
  editingCategoryId = null;
  document.getElementById("category-form").reset();
}

async function loadCategoryData(categoryId) {
  try {
    // Ensure editingCategoryId is set before loading data
    editingCategoryId = categoryId;
    
    const response = await APIHelper.get("/api/settings/categories");
    
    if (response && response.categories) {
      const category = response.categories.find((c) => c.id === categoryId);
      if (category) {
        document.getElementById("category-name").value = category.name;
        document.getElementById("category-description").value =
          category.description || "";
        // Ensure editingCategoryId is still set after loading
        editingCategoryId = categoryId;
      } else {
        console.error("Category not found with ID:", categoryId);
        showNotification("Category not found", "error");
        closeCategoryModal();
      }
    }
  } catch (error) {
    console.error("Error loading category data:", error);
    showNotification("Failed to load category data", "error");
    closeCategoryModal();
  }
}

async function editCategory(categoryId) {
  openCategoryModal(categoryId);
}

async function handleCategorySubmit(event) {
  event.preventDefault();

  // Store the editingCategoryId in a local variable to prevent it from being lost
  const currentEditingId = editingCategoryId;

  const formData = {
    name: document.getElementById("category-name").value.trim(),
    description: document.getElementById("category-description").value.trim(),
  };

  if (!formData.name) {
    showNotification("Category name is required", "error");
    return;
  }

  try {
    let response;
    // Check if we're editing (currentEditingId should be set)
    if (currentEditingId !== null && currentEditingId !== undefined && currentEditingId !== 0) {
      // Update existing category
      response = await APIHelper.put(
        `/api/settings/categories/${currentEditingId}`,
        formData
      );
      if (response && response.category) {
        showNotification("Category updated successfully", "success");
        closeCategoryModal();
        loadCategories();
      } else {
        throw new Error("Update failed - no response received");
      }
    } else {
      // Create new category
      response = await APIHelper.post("/api/settings/categories", formData);
      if (response && response.category) {
        showNotification("Category created successfully", "success");
        closeCategoryModal();
        loadCategories();
      } else {
        throw new Error("Create failed - no response received");
      }
    }
  } catch (error) {
    console.error("Error saving category:", error);
    const errorMessage =
      error.message || "Failed to save category. Please try again.";
    showNotification(errorMessage, "error");
    // Don't close modal on error so user can fix and retry
  }
}

async function deleteCategory(categoryId, categoryName) {
  if (
    !confirm(
      `Are you sure you want to delete the category "${categoryName}"? This action cannot be undone.`
    )
  ) {
    return;
  }

  try {
    await APIHelper.delete(`/api/settings/categories/${categoryId}`);
    showNotification("Category deleted successfully", "success");
    loadCategories();
  } catch (error) {
    console.error("Error deleting category:", error);
    const errorMessage =
      error.message || "Failed to delete category. Please try again.";
    showNotification(errorMessage, "error");
  }
}

// ===== UTILITY FUNCTIONS =====

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function showNotification(message, type = "info") {
  // Create toast element
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;

  // Style the toast
  toast.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 1rem 1.5rem;
    border-radius: 8px;
    color: white;
    font-weight: 500;
    z-index: 3000;
    animation: slideInRight 0.3s ease-out;
    max-width: 300px;
    word-wrap: break-word;
  `;

  // Set background color based on type
  switch (type) {
    case "success":
      toast.style.background = "linear-gradient(135deg, #28a745, #20c997)";
      break;
    case "error":
      toast.style.background = "linear-gradient(135deg, #dc3545, #fd7e14)";
      break;
    case "warning":
      toast.style.background = "linear-gradient(135deg, #ffc107, #fd7e14)";
      break;
    default:
      toast.style.background = "linear-gradient(135deg, #17a2b8, #20c997)";
  }

  // Add to page
  document.body.appendChild(toast);

  // Remove after 3 seconds
  setTimeout(() => {
    toast.style.animation = "slideOutRight 0.3s ease-in";
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 300);
  }, 3000);
}

// Make functions globally available
window.openDepartmentModal = openDepartmentModal;
window.closeDepartmentModal = closeDepartmentModal;
window.editDepartment = editDepartment;
window.deleteDepartment = deleteDepartment;
window.openCategoryModal = openCategoryModal;
window.closeCategoryModal = closeCategoryModal;
window.editCategory = editCategory;
window.deleteCategory = deleteCategory;
