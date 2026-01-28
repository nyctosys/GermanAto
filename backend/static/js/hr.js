// HR Management JavaScript

let workers = [];
let currentWorkerId = null;

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  // Wait for auth to be available
  if (typeof auth === "undefined" || !auth.requirePageAccess) {
    console.error("Auth not available, retrying...");
    setTimeout(() => {
      if (typeof auth !== "undefined" && auth.requirePageAccess) {
        initializeHR();
      } else {
        console.error("Auth still not available after retry");
        window.location.href = "login.html";
      }
    }, 100);
    return;
  }

  initializeHR();
});

function initializeHR() {
  // Check authentication and access
  if (!auth.requirePageAccess("hr")) {
    return;
  }

  loadWorkers();
  loadDepartments();
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
    searchInput.addEventListener("keypress", function (e) {
      if (e.key === "Enter") {
        searchWorkers();
      }
    });
  }

  // Filter functionality
  const statusFilter = document.getElementById("statusFilter");
  if (statusFilter) {
    statusFilter.addEventListener("change", searchWorkers);
  }

  const departmentFilter = document.getElementById("departmentFilter");
  if (departmentFilter) {
    departmentFilter.addEventListener("change", searchWorkers);
  }

  // Modal functionality
  const workerModal = document.getElementById("workerModal");
  if (workerModal) {
    workerModal.addEventListener("click", function (e) {
      if (e.target === workerModal) {
        closeWorkerModal();
      }
    });
  }

  const deleteModal = document.getElementById("deleteModal");
  if (deleteModal) {
    deleteModal.addEventListener("click", function (e) {
      if (e.target === deleteModal) {
        closeDeleteModal();
      }
    });
  }
}

// Load workers from API
async function loadWorkers() {
  try {
    const data = await APIHelper.get("/api/workers");
    if (!data) return;

    workers = data.workers;
    renderWorkersTable();
  } catch (error) {
    console.error("Error loading workers:", error);
    showError("Error loading workers. Please try again.");
  }
}

// Load departments for filter and form dropdown
async function loadDepartments() {
  try {
    // Load from settings API WITHOUT sync to prevent recreating old departments
    const data = await APIHelper.get("/api/settings/departments");
    if (!data || !data.departments) return;

    const departments = data.departments;

    // Populate filter dropdown
    const departmentFilter = document.getElementById("departmentFilter");
    if (departmentFilter) {
      // Clear existing options except the first one
      departmentFilter.innerHTML = '<option value="">All Departments</option>';

      departments.forEach((dept) => {
        const option = document.createElement("option");
        option.value = dept.name;
        option.textContent = dept.name;
        departmentFilter.appendChild(option);
      });
    }

    // Populate form dropdown
    const departmentSelect = document.getElementById("department");
    if (departmentSelect) {
      // Clear existing options except the first one
      departmentSelect.innerHTML = '<option value="">Select Department</option>';

      departments.forEach((dept) => {
        const option = document.createElement("option");
        option.value = dept.name;
        option.textContent = dept.name;
        departmentSelect.appendChild(option);
      });
    }
  } catch (error) {
    console.error("Error loading departments:", error);
    showError("Error loading departments. Please try again.");
  }
}

// Render workers table
function renderWorkersTable() {
  const tbody = document.getElementById("workersTableBody");
  if (!tbody) return;

  if (workers.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" class="loading-cell">
          <span>No workers found</span>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = workers
    .map(
      (worker) => `
        <tr>
          <td>${worker.employee_id}</td>
          <td>${worker.first_name} ${worker.last_name}</td>
          <td>${worker.position}</td>
          <td>${worker.department}</td>
          <td>${worker.phone}</td>
          <td>
            <span class="status-badge status-${worker.status}">
              ${worker.status}
            </span>
          </td>
          <td>${formatDate(worker.hire_date)}</td>
          <td>
            <div class="action-buttons">
              <a href="/hr/${worker.id}" class="action-btn view-btn">
                View
              </a>
              <button class="action-btn edit-btn" onclick="editWorker(${
                worker.id
              })">
                Edit
              </button>
              <button class="action-btn delete-btn" onclick="deleteWorker(${
                worker.id
              })">
                Delete
              </button>
            </div>
          </td>
        </tr>
      `
    )
    .join("");
}

// Search workers
function searchWorkers() {
  const searchTerm = document.getElementById("searchInput").value.trim();
  const statusFilter = document.getElementById("statusFilter").value;
  const departmentFilter = document.getElementById("departmentFilter").value;

  let filteredWorkers = workers;

  // Apply search filter
  if (searchTerm) {
    const searchLower = searchTerm.toLowerCase();
    filteredWorkers = filteredWorkers.filter(
      (worker) =>
        worker.first_name.toLowerCase().includes(searchLower) ||
        worker.last_name.toLowerCase().includes(searchLower) ||
        worker.employee_id.toLowerCase().includes(searchLower) ||
        worker.phone.toLowerCase().includes(searchLower) ||
        worker.position.toLowerCase().includes(searchLower)
    );
  }

  // Apply status filter
  if (statusFilter) {
    filteredWorkers = filteredWorkers.filter(
      (worker) => worker.status === statusFilter
    );
  }

  // Apply department filter
  if (departmentFilter) {
    filteredWorkers = filteredWorkers.filter(
      (worker) => worker.department === departmentFilter
    );
  }

  // Temporarily replace workers array for rendering
  const originalWorkers = workers;
  workers = filteredWorkers;
  renderWorkersTable();
  workers = originalWorkers;
}

// Clear filters
function clearFilters() {
  document.getElementById("searchInput").value = "";
  document.getElementById("statusFilter").value = "";
  document.getElementById("departmentFilter").value = "";
  renderWorkersTable();
}

// Open add worker modal
function openAddWorkerModal() {
  currentWorkerId = null;
  document.getElementById("modalTitle").textContent = "Add Worker";
  document.getElementById("workerForm").reset();

  // Set today's date as default for hire date
  const today = new Date().toISOString().split("T")[0];
  document.getElementById("hireDate").value = today;

  // Ensure departments are loaded
  loadDepartments();

  showModal("workerModal");
}

// Close worker modal
function closeWorkerModal() {
  hideModal("workerModal");
  document.getElementById("workerForm").reset();
  currentWorkerId = null;
}

// Edit worker
async function editWorker(workerId) {
  const worker = workers.find((w) => w.id === workerId);
  if (!worker) return;

  currentWorkerId = workerId;
  document.getElementById("modalTitle").textContent = "Edit Worker";

  // Ensure departments are loaded before setting the value
  await loadDepartments();

  // Populate form with worker data
  document.getElementById("employeeId").value = worker.employee_id;
  document.getElementById("firstName").value = worker.first_name;
  document.getElementById("lastName").value = worker.last_name;
  document.getElementById("email").value = worker.email || "";
  document.getElementById("phone").value = worker.phone;
  document.getElementById("address").value = worker.address;
  document.getElementById("cnic").value = worker.cnic;
  document.getElementById("dateOfBirth").value = worker.date_of_birth;
  document.getElementById("hireDate").value = worker.hire_date;
  document.getElementById("position").value = worker.position;
  
  // Set department value - if it doesn't exist in dropdown, add it as an option
  const departmentSelect = document.getElementById("department");
  const departmentValue = worker.department;
  if (departmentSelect) {
    // Check if the value exists in the dropdown
    const optionExists = Array.from(departmentSelect.options).some(
      opt => opt.value === departmentValue
    );
    
    if (!optionExists && departmentValue) {
      // Add the department as an option if it doesn't exist (for legacy data)
      const option = document.createElement("option");
      option.value = departmentValue;
      option.textContent = departmentValue + " (Legacy)";
      departmentSelect.appendChild(option);
    }
    
    departmentSelect.value = departmentValue;
  }
  
  document.getElementById("salary").value = worker.salary || "";
  document.getElementById("status").value = worker.status;
  document.getElementById("emergencyContactName").value =
    worker.emergency_contact_name || "";
  document.getElementById("emergencyContactPhone").value =
    worker.emergency_contact_phone || "";
  document.getElementById("notes").value = worker.notes || "";

  showModal("workerModal");
}

// Delete worker
function deleteWorker(workerId) {
  currentWorkerId = workerId;
  const worker = workers.find((w) => w.id === workerId);
  const deleteMessage = document.getElementById("deleteMessage");
  if (deleteMessage && worker) {
    deleteMessage.textContent = `Are you sure you want to delete ${worker.first_name} ${worker.last_name}?`;
  }
  showModal("deleteModal");
}

// Close delete modal
function closeDeleteModal() {
  hideModal("deleteModal");
  currentWorkerId = null;
}

// Save worker
async function saveWorker() {
  const form = document.getElementById("workerForm");
  if (!form.checkValidity()) {
    form.reportValidity();
    return;
  }

  const workerData = {
    employee_id: document.getElementById("employeeId").value.trim(),
    first_name: document.getElementById("firstName").value.trim(),
    last_name: document.getElementById("lastName").value.trim(),
    email: document.getElementById("email").value.trim() || null,
    phone: document.getElementById("phone").value.trim(),
    address: document.getElementById("address").value.trim(),
    cnic: document.getElementById("cnic").value.trim(),
    date_of_birth: document.getElementById("dateOfBirth").value,
    hire_date: document.getElementById("hireDate").value,
    position: document.getElementById("position").value.trim(),
    department: document.getElementById("department").value.trim(),
    salary: document.getElementById("salary").value
      ? parseFloat(document.getElementById("salary").value)
      : null,
    status: document.getElementById("status").value,
    emergency_contact_name:
      document.getElementById("emergencyContactName").value.trim() || null,
    emergency_contact_phone:
      document.getElementById("emergencyContactPhone").value.trim() || null,
    notes: document.getElementById("notes").value.trim() || null,
  };

  try {
    console.log("Worker data being sent:", workerData);

    const url = currentWorkerId
      ? `/api/workers/${currentWorkerId}`
      : "/api/workers";
    const method = currentWorkerId ? "PUT" : "POST";

    const data =
      method === "POST"
        ? await APIHelper.post(url, workerData)
        : await APIHelper.put(url, workerData);

    if (!data) return;

    console.log("Response data:", data);

    showSuccess(data.message);
    loadWorkers();
    closeWorkerModal();
  } catch (error) {
    console.error("Error saving worker:", error);
    showError("Error saving worker. Please try again.");
  }
}

// Confirm delete
async function confirmDelete() {
  if (!currentWorkerId) return;

  try {
    const data = await APIHelper.delete(`/api/workers/${currentWorkerId}`);
    if (!data) return;

    showSuccess(data.message);
    loadWorkers();
    closeDeleteModal();
  } catch (error) {
    console.error("Error deleting worker:", error);
    showError("Error deleting worker. Please try again.");
  }
}

// Format date for display
function formatDate(dateString) {
  if (!dateString) return "N/A";

  const date = new Date(dateString);
  if (isNaN(date.getTime())) return "Invalid Date";

  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
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
