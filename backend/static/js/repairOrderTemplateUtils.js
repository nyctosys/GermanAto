// ===== REPAIR ORDER TEMPLATE UTILITIES =====

// Format currency values
function formatCurrency(amount) {
  return new Intl.NumberFormat("en-PK", {
    style: "currency",
    currency: "PKR",
    minimumFractionDigits: 2,
  }).format(amount);
}

// Format dates with time
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

// Update status timeline - only highlight current status
function updateStatusTimeline(statusData, currentStatus = "received") {
  const statuses = ["received", "diagnosis", "repair", "testing", "complete"];

  statuses.forEach((status) => {
    const statusElement = document.getElementById(`status-${status}`);
    const dateElement = document.getElementById(`${status}-date`);

    if (statusElement) {
      // Remove all status classes first
      statusElement.classList.remove("completed", "current");

      // Only add current class to the current status
      if (status === currentStatus) {
        statusElement.classList.add("current");
      }

      // Update date if available
      if (dateElement) {
        if (statusData[status] && statusData[status].date) {
          dateElement.textContent = formatDate(statusData[status].date);

          // Add completion time if available
          if (statusData[status].time) {
            dateElement.textContent += ` ${statusData[status].time}`;
          }
        } else {
          dateElement.textContent = "Pending";
        }
      }
    }
  });
}

// Calculate totals from parts and labour (now always 0 since pricing removed)
function calculateTotals(parts, labour) {
  return {
    partsTotal: 0,
    labourTotal: 0,
    total: 0,
  };
}

// Populate parts table
function populatePartsTable(parts) {
  const tableBody = document.getElementById("parts-table-body");
  if (!tableBody) return;

  tableBody.innerHTML = "";

  if (!parts || parts.length === 0) {
    const emptyRow = document.createElement("tr");
    emptyRow.innerHTML =
      '<td colspan="4" style="text-align: center; color: #666;">No parts required</td>';
    tableBody.appendChild(emptyRow);
    return;
  }

  parts.forEach((part) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${part.description || "N/A"}</td>
      <td>${part.part_number || "N/A"}</td>
      <td>${part.quantity || 1}</td>
      <td>
        <span class="status-badge ${part.status?.toLowerCase() || "pending"}">
          ${part.status || "Pending"}
        </span>
      </td>
    `;
    tableBody.appendChild(row);
  });
}

// Populate labour table
function populateLabourTable(labour) {
  const tableBody = document.getElementById("labour-table-body");
  if (!tableBody) return;

  tableBody.innerHTML = "";

  if (!labour || labour.length === 0) {
    const emptyRow = document.createElement("tr");
    emptyRow.innerHTML =
      '<td colspan="2" style="text-align: center; color: #666;">No labour tasks</td>';
    tableBody.appendChild(emptyRow);
    return;
  }

  labour.forEach((task) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${task.description || "N/A"}</td>
      <td>
        <span class="status-badge ${task.status?.toLowerCase() || "pending"}">
          ${task.status || "Pending"}
        </span>
      </td>
    `;
    tableBody.appendChild(row);
  });
}

// Update estimate section (no-op - price fields removed)
function updateEstimate(partsTotal, labourTotal, taxAmount = 0) {
  // Price-related fields removed - function kept for compatibility but does nothing
}

// Validate repair order data
function validateRepairOrderData(data) {
  const requiredFields = ["customer_name", "customer_phone", "customer_reg_no"];

  const missingFields = requiredFields.filter((field) => !data[field]);

  if (missingFields.length > 0) {
    console.warn("Missing required fields:", missingFields);
    return false;
  }

  return true;
}

// Generate repair order number
function generateRepairOrderNumber() {
  const timestamp = Date.now();
  const random = Math.floor(Math.random() * 1000);
  return `RO${timestamp}${random}`;
}

// Save repair order data to session storage
function saveRepairOrderData(data) {
  try {
    sessionStorage.setItem("repairOrderData", JSON.stringify(data));
    sessionStorage.setItem(
      "repairOrderId",
      data.id || generateRepairOrderNumber()
    );
    return true;
  } catch (error) {
    console.error("Error saving repair order data:", error);
    return false;
  }
}

// Load repair order data from session storage
function loadRepairOrderData() {
  try {
    const data = sessionStorage.getItem("repairOrderData");
    const id = sessionStorage.getItem("repairOrderId");

    if (data && id) {
      return {
        data: JSON.parse(data),
        id: id,
      };
    }

    return null;
  } catch (error) {
    console.error("Error loading repair order data:", error);
    return null;
  }
}

// Clear repair order data from session storage
function clearRepairOrderData() {
  sessionStorage.removeItem("repairOrderData");
  sessionStorage.removeItem("repairOrderId");
}

// Update vehicle condition display
function updateVehicleCondition(condition) {
  const fields = [
    "fuel-level",
    "exterior-condition",
    "interior-condition",
    "personal-items",
  ];

  fields.forEach((field) => {
    const element = document.getElementById(field);
    if (element) {
      element.textContent = condition[field] || "N/A";
    }
  });
}

// Update problem and diagnosis sections
function updateProblemAndDiagnosis(problem, diagnosis) {
  const problemElement = document.getElementById("problem-description");
  const diagnosisElement = document.getElementById("diagnosis-plan");

  if (problemElement) {
    problemElement.textContent = problem || "No problem description provided.";
  }

  if (diagnosisElement) {
    diagnosisElement.textContent = diagnosis || "No diagnosis plan provided.";
  }
}

// Update notes section
function updateNotes(notes) {
  const notesElement = document.getElementById("repair-notes");
  if (notesElement) {
    notesElement.textContent = notes || "No additional notes.";
  }
}

// Initialize repair order template
function initializeRepairOrderTemplate() {
  const repairOrderData = loadRepairOrderData();

  if (!repairOrderData) {
    console.warn("No repair order data found");
    return;
  }

  const { data, id } = repairOrderData;

  if (!validateRepairOrderData(data)) {
    console.error("Invalid repair order data");
    return;
  }

  // Update header
  document.getElementById("repair-order-id").textContent = `RO #${id}`;
  document.getElementById("repair-order-date").textContent = formatDate(
    data.created_date || new Date()
  );

  // Update customer and vehicle information
  const customerFields = [
    "customer_name",
    "customer_address",
    "customer_phone",
    "customer_reg_no",
    "customer_made",
    "customer_mileage",
    "customer_vin",
    "customer_color",
    "customer_chasis",
  ];

  customerFields.forEach((field) => {
    const element = document.getElementById(field.replace("customer_", ""));
    if (element) {
      let value = data[field] || "N/A";
      if (field === "customer_mileage" && value !== "N/A") {
        value = `${value}km`;
      }
      element.textContent = value;
    }
  });

  // Update vehicle condition
  if (data.vehicle_condition) {
    updateVehicleCondition(data.vehicle_condition);
  }

  // Update problem and diagnosis
  updateProblemAndDiagnosis(data.problem_description, data.diagnosis_plan);

  // Update parts and labour tables
  populatePartsTable(data.parts || []);
  populateLabourTable(data.labour || []);

  // Price-related fields removed - no totals to update

  // Update status timeline
  if (data.status_timeline) {
    updateStatusTimeline(data.status_timeline, data.current_status);
  }

  // Update notes
  updateNotes(data.notes);

  // Clear session storage after successful initialization
  clearRepairOrderData();
}

// Export functions for use in other scripts
window.RepairOrderUtils = {
  formatCurrency,
  formatDate,
  updateStatusTimeline,
  calculateTotals,
  populatePartsTable,
  populateLabourTable,
  updateEstimate,
  validateRepairOrderData,
  generateRepairOrderNumber,
  saveRepairOrderData,
  loadRepairOrderData,
  clearRepairOrderData,
  updateVehicleCondition,
  updateProblemAndDiagnosis,
  updateNotes,
  initializeRepairOrderTemplate,
};
