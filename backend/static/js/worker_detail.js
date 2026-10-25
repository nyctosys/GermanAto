// Worker Detail JavaScript

let currentWorker = null;
let currentWorkerId = null;

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  // Wait for auth to be available
  if (typeof auth === "undefined" || !auth.requirePageAccess) {
    console.error("Auth not available, retrying...");
    setTimeout(() => {
      if (typeof auth !== "undefined" && auth.requirePageAccess) {
        initializeWorkerDetail();
      } else {
        console.error("Auth still not available after retry");
        window.location.href = "login.html";
      }
    }, 100);
    return;
  }

  initializeWorkerDetail();
});

function initializeWorkerDetail() {
  // Check authentication and access
  if (!auth.requirePageAccess("worker-detail")) {
    return;
  }

  // Get worker ID from URL
  const pathParts = window.location.pathname.split("/");
  currentWorkerId = parseInt(pathParts[pathParts.length - 1]);

  if (currentWorkerId) {
    loadWorkerDetails();
    setupEventListeners();
    setupBackButton();
  } else {
    showError("Invalid worker ID");
  }
}

// Setup back button
function setupBackButton() {
  const backBtn = document.getElementById("back-btn");
  if (backBtn) {
    backBtn.addEventListener("click", function (e) {
      e.preventDefault();
      window.location.href = "/hr";
    });
  }
}

// Setup event listeners
function setupEventListeners() {
  // Modal functionality
  const editWorkerModal = document.getElementById("editWorkerModal");
  if (editWorkerModal) {
    editWorkerModal.addEventListener("click", function (e) {
      if (e.target === editWorkerModal) {
        closeEditWorkerModal();
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

// Load worker details from API
async function loadWorkerDetails() {
  try {
    const data = await APIHelper.get(`/api/workers/${currentWorkerId}`);
    currentWorker = data;
    displayWorkerInfo();
  } catch (error) {
    console.error("Error loading worker details:", error);
    showError("Error loading worker details. Please try again.");
  }
}

// Display worker information
function displayWorkerInfo() {
  if (!currentWorker) {
    return;
  }

  // Update header
  const workerNameEl = document.getElementById("workerName");
  if (workerNameEl) {
    workerNameEl.textContent = `${currentWorker.first_name} ${currentWorker.last_name}`;
  }

  // Update worker basic info
  const workerFullNameEl = document.getElementById("workerFullName");
  if (workerFullNameEl) {
    workerFullNameEl.textContent = `${currentWorker.first_name} ${currentWorker.last_name}`;
  }

  const workerPositionEl = document.getElementById("workerPosition");
  if (workerPositionEl) {
    workerPositionEl.textContent = currentWorker.position;
  }

  const workerDepartmentEl = document.getElementById("workerDepartment");
  if (workerDepartmentEl) {
    workerDepartmentEl.textContent = currentWorker.department;
  }

  // Update detailed information
  const workerEmployeeIdEl = document.getElementById("workerEmployeeId");
  if (workerEmployeeIdEl) {
    workerEmployeeIdEl.textContent = currentWorker.employee_id || "N/A";
  }

  const workerPhoneEl = document.getElementById("workerPhone");
  if (workerPhoneEl) {
    workerPhoneEl.textContent = currentWorker.phone || "N/A";
  }

  const workerEmailEl = document.getElementById("workerEmail");
  if (workerEmailEl) {
    workerEmailEl.textContent = currentWorker.email || "N/A";
  }

  const workerCnicEl = document.getElementById("workerCnic");
  if (workerCnicEl) {
    workerCnicEl.textContent = currentWorker.cnic || "N/A";
  }

  const workerDateOfBirthEl = document.getElementById("workerDateOfBirth");
  if (workerDateOfBirthEl) {
    workerDateOfBirthEl.textContent = formatDate(currentWorker.date_of_birth);
  }

  const workerHireDateEl = document.getElementById("workerHireDate");
  if (workerHireDateEl) {
    workerHireDateEl.textContent = formatDate(currentWorker.hire_date);
  }

  const workerSalaryEl = document.getElementById("workerSalary");
  if (workerSalaryEl) {
    workerSalaryEl.textContent = currentWorker.salary
      ? formatCurrency(currentWorker.salary)
      : "N/A";
  }

  // Status with badge
  const statusElement = document.getElementById("workerStatus");
  if (statusElement) {
    statusElement.innerHTML = `<span class="status-badge status-${currentWorker.status}">${currentWorker.status}</span>`;
  }

  const workerAddressEl = document.getElementById("workerAddress");
  if (workerAddressEl) {
    workerAddressEl.textContent = currentWorker.address || "N/A";
  }

  const workerEmergencyContactEl = document.getElementById(
    "workerEmergencyContact"
  );
  if (workerEmergencyContactEl) {
    workerEmergencyContactEl.textContent =
      currentWorker.emergency_contact_name || "N/A";
  }

  const workerEmergencyPhoneEl = document.getElementById(
    "workerEmergencyPhone"
  );
  if (workerEmergencyPhoneEl) {
    workerEmergencyPhoneEl.textContent =
      currentWorker.emergency_contact_phone || "N/A";
  }

  const workerNotesEl = document.getElementById("workerNotes");
  if (workerNotesEl) {
    workerNotesEl.textContent = currentWorker.notes || "N/A";
  }
}

// Edit worker
function editWorker() {
  if (!currentWorker) return;

  // Populate form with current worker data
  document.getElementById("editEmployeeId").value = currentWorker.employee_id;
  document.getElementById("editFirstName").value = currentWorker.first_name;
  document.getElementById("editLastName").value = currentWorker.last_name;
  document.getElementById("editEmail").value = currentWorker.email || "";
  document.getElementById("editPhone").value = currentWorker.phone;
  document.getElementById("editAddress").value = currentWorker.address;
  document.getElementById("editCnic").value = currentWorker.cnic;
  document.getElementById("editDateOfBirth").value =
    currentWorker.date_of_birth;
  document.getElementById("editHireDate").value = currentWorker.hire_date;
  document.getElementById("editPosition").value = currentWorker.position;
  document.getElementById("editDepartment").value = currentWorker.department;
  document.getElementById("editSalary").value = currentWorker.salary || "";
  document.getElementById("editStatus").value = currentWorker.status;
  document.getElementById("editEmergencyContactName").value =
    currentWorker.emergency_contact_name || "";
  document.getElementById("editEmergencyContactPhone").value =
    currentWorker.emergency_contact_phone || "";
  document.getElementById("editNotes").value = currentWorker.notes || "";

  showModal("editWorkerModal");
}

// Close edit worker modal
function closeEditWorkerModal() {
  hideModal("editWorkerModal");
}

// Delete worker
function deleteWorker() {
  showModal("deleteModal");
}

// Close delete modal
function closeDeleteModal() {
  hideModal("deleteModal");
}

// Save worker
async function saveWorker() {
  const form = document.getElementById("editWorkerForm");
  if (!form.checkValidity()) {
    form.reportValidity();
    return;
  }

  const workerData = {
    employee_id: document.getElementById("editEmployeeId").value.trim(),
    first_name: document.getElementById("editFirstName").value.trim(),
    last_name: document.getElementById("editLastName").value.trim(),
    email: document.getElementById("editEmail").value.trim() || null,
    phone: document.getElementById("editPhone").value.trim(),
    address: document.getElementById("editAddress").value.trim(),
    cnic: document.getElementById("editCnic").value.trim(),
    date_of_birth: document.getElementById("editDateOfBirth").value,
    hire_date: document.getElementById("editHireDate").value,
    position: document.getElementById("editPosition").value.trim(),
    department: document.getElementById("editDepartment").value.trim(),
    salary: document.getElementById("editSalary").value || null,
    status: document.getElementById("editStatus").value,
    emergency_contact_name:
      document.getElementById("editEmergencyContactName").value.trim() || null,
    emergency_contact_phone:
      document.getElementById("editEmergencyContactPhone").value.trim() || null,
    notes: document.getElementById("editNotes").value.trim() || null,
  };

  try {
    const data = await APIHelper.put(
      `/api/workers/${currentWorkerId}`,
      workerData
    );
    showSuccess(data.message);
    currentWorker = data.worker;
    displayWorkerInfo();
    closeEditWorkerModal();
  } catch (error) {
    console.error("Error updating worker:", error);
    showError("Error updating worker. Please try again.");
  }
}

// Confirm delete
async function confirmDelete() {
  try {
    const data = await APIHelper.delete(`/api/workers/${currentWorkerId}`);
    showSuccess(data.message);
    setTimeout(() => {
      window.location.href = "/hr";
    }, 1500);
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

// Format currency for display
function formatCurrency(amount) {
  if (!amount) return "N/A";
  return new Intl.NumberFormat("en-PK", {
    style: "currency",
    currency: "PKR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
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
