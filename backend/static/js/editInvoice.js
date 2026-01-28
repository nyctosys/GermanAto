/**
 * Edit Invoice Module
 * Handles editing existing invoices and quotes
 */

import {
  state,
  loadCustomers,
  loadCars,
  loadInventory,
  setupSearchableDropdowns,
  setupCommonEventListeners,
  collectFormData,
  validateFormData,
  updateCustomerAndCarRecords,
  updateTotal,
  updateTaxDisplay,
  handleCustomerChange,
  handleCarChange,
  addItem,
} from "./invoiceShared.js";

// Store the invoice ID being edited
let editId = null;

// Initialize edit invoice page
async function initializeEditInvoice() {
  // Wait for required elements to be available
  const invoiceForm = document.getElementById("invoice-form");
  if (!invoiceForm) {
    console.error("Invoice form not found, retrying...");
    setTimeout(initializeEditInvoice, 100);
    return;
  }

  const params = new URLSearchParams(window.location.search);
  editId = params.get("id");

  if (!editId) {
    console.error("No invoice ID provided for editing");
    alert("No invoice ID provided. Redirecting to invoice management.");
    window.location.href = "invoice-management.html";
    return;
  }

  console.log("Edit Invoice module loaded for invoice ID:", editId);

  // Load data
  loadCustomers();
  loadCars();
  await loadInventory();

  // Load invoice data for editing
  await loadInvoiceForEdit(editId);

  // Set up event listeners
  setupSearchableDropdowns();
  setupCommonEventListeners();

  // Set up form submission for update
  document
    .getElementById("invoice-form")
    .addEventListener("submit", handleFormSubmit);
}

// Initialize when DOM is ready or immediately if already loaded
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeEditInvoice);
} else {
  // DOM is already loaded
  initializeEditInvoice();
}

// ===== PERMISSION CHECKS =====

// Function to check if invoice is older than 1 day
function isInvoiceOlderThanOneDay(createdAtStr) {
  const createdDate = new Date(createdAtStr);
  const currentDate = new Date();
  const oneDayInMs = 24 * 60 * 60 * 1000;
  return currentDate - createdDate > oneDayInMs;
}

// Function to check if user can edit this invoice
function canUserEditInvoice(invoice) {
  const userStr = localStorage.getItem("user");
  if (!userStr) return false;

  const user = JSON.parse(userStr);

  // Admins can always edit
  if (user.role === "admin") {
    return true;
  }

  // Accountants can always edit quotes, but invoices older than 1 day are restricted
  if (user.role === "accountant") {
    if (invoice.type_of.toLowerCase() === "quote") {
      return true;
    }
    return !isInvoiceOlderThanOneDay(invoice.created_at);
  }

  // Other roles cannot edit
  return false;
}

// ===== LOAD INVOICE FOR EDITING =====

async function loadInvoiceForEdit(invoiceId) {
  try {
    const data = await APIHelper.get(`/api/invoice/${invoiceId}`);
    if (!data) {
      const errorFn = typeof showError === 'function' ? showError : alert;
      errorFn("Failed to fetch invoice for editing.");
      return;
    }

    // Check if user can edit this invoice based on role and time restrictions
    if (!canUserEditInvoice(data)) {
      const errorFn = typeof showError === 'function' ? showError : alert;
      errorFn(
        "You cannot edit invoices older than 1 day. Please contact an administrator."
      );
      window.history.back();
      return;
    }

    // Wait for customers and cars to be loaded
    await waitForData();

    // Find and select the customer based on name and phone
    const customerSelect = document.getElementById("customer-select");

    // Try exact match first (name AND phone)
    let customer = state.customers?.find(
      (c) => c.name === data.customer_name && c.phone === data.customer_phone
    );
    // Fallback: match by phone only
    if (!customer && data.customer_phone) {
      customer = state.customers?.find((c) => c.phone === data.customer_phone);
    }
    // Fallback: match by name only
    if (!customer && data.customer_name) {
      customer = state.customers?.find((c) => c.name === data.customer_name);
    }

    if (customer) {
      const customerDisplayText = `${customer.name} - ${customer.phone}`;
      customerSelect.value = customerDisplayText;
      handleCustomerChange(customer.id);

      // Wait for car dropdown to be populated with customer's cars
      setTimeout(() => {
        const carSelect = document.getElementById("car-select");
        // Find car by plate number, but only from the selected customer's cars
        const car = state.cars?.find(
          (c) => c.plate_no === data.customer_reg_no && c.customer_id === customer.id
        );

        if (car) {
          const carDisplayText = `${car.make} ${car.model} - ${car.plate_no}`;
          carSelect.value = carDisplayText;
          handleCarChange(car.id);
        } else if (data.customer_reg_no) {
          // If car not found for this customer, still populate the fields manually
          // This handles cases where the car might have been reassigned or deleted
          document.getElementById("customer_reg").value = data.customer_reg_no || "";
          document.getElementById("customer_made").value = data.customer_made || "";
          document.getElementById("customer_mileage").value = data.customer_mileage || "";
          document.getElementById("customer_vin").value = data.customer_vin || "";
          document.getElementById("customer_color").value = data.customer_color || "";
          document.getElementById("customer_chasis").value = data.customer_chasis || "";
          document.getElementById("car-details").style.display = "block";
        }
      }, 100);
    }

    // Set advance payment
    document.querySelector(".advance").value = data.advance || 0;

    // Set discount
    document.getElementById("discount").value = data.discount || 0;

    // Set tax information
    const taxToggle = document.getElementById("tax-toggle");
    if (data.include_tax !== undefined) {
      taxToggle.checked = data.include_tax;
      updateTaxDisplay();
    }

    // Clear old items/labours
    const itemsContainer = document.getElementById("items-container");
    itemsContainer.innerHTML = "";

    // Reset counter for clean numbering
    state.counter = 0;

    // Add items
    data.items.forEach((item) => {
      addItem("item");
      const lastItem =
        document.querySelectorAll(".item")[
          document.querySelectorAll(".item").length - 1
        ];
      lastItem.querySelector(".product-name").value = item.product_name;
      lastItem.querySelector(".part-number").value = item.part_number || "";
      lastItem.querySelector(".quantity").value = item.quantity;
      lastItem.querySelector(".price").value = item.price;

      // Store item ID for update
      const hiddenInput = document.createElement("input");
      hiddenInput.type = "hidden";
      hiddenInput.classList.add("item-id");
      hiddenInput.value = item.id;
      lastItem.appendChild(hiddenInput);
    });

    // Add labours
    data.labours.forEach((labour) => {
      addItem("labour");
      const lastLabour =
        document.querySelectorAll(".item")[
          document.querySelectorAll(".item").length - 1
        ];
      lastLabour.querySelector(".labour-description").value = labour.description;
      lastLabour.querySelector(".price").value = labour.price;

      // Store labour ID for update
      const hiddenInput = document.createElement("input");
      hiddenInput.type = "hidden";
      hiddenInput.classList.add("labour-id");
      hiddenInput.value = labour.id;
      lastLabour.appendChild(hiddenInput);
    });

    // Show only Update button
    prepareUpdateButton(data.type_of);

    // Show document type as read-only indicator when editing
    const documentTypeToggleContainer = document.querySelector(".document-type-toggle");
    if (documentTypeToggleContainer) {
      const docTypeDisplay = data.type_of.toLowerCase() === "invoice" ? "Invoice" : "Quote";
      const bgColor = data.type_of.toLowerCase() === "invoice" ? "#d4edda" : "#e2e3e5";
      const textColor = data.type_of.toLowerCase() === "invoice" ? "#155724" : "#383d41";

      // Replace entire content with just the document type indicator
      documentTypeToggleContainer.innerHTML = `
        <div style="text-align: center; padding: 15px;">
          <span style="
            display: inline-block;
            padding: 12px 24px;
            background-color: ${bgColor};
            color: ${textColor};
            font-weight: bold;
            font-size: 1.2em;
            border-radius: 8px;
            border: 2px solid ${textColor};
          ">
            Editing: ${docTypeDisplay}
          </span>
        </div>
      `;
    }

    // Hide inventory deduction section when editing
    const inventoryDeductionSection = document.querySelector(".inventory-deduction-section");
    if (inventoryDeductionSection) {
      inventoryDeductionSection.style.display = "none";
    }

    // Update totals and balances
    updateTotal();

    // Store global edit info
    window.editingInvoiceId = invoiceId;
    window.editingDocumentType = data.type_of;
  } catch (err) {
    console.error("Error loading invoice:", err);
    alert("Error loading invoice.");
  }
}

// ===== HELPER FUNCTIONS =====

// Function to wait for customers, cars, and inventory data to be loaded
function waitForData() {
  return new Promise((resolve) => {
    const checkData = () => {
      if (
        state.customers.length > 0 ||
        state.cars.length > 0 ||
        window.customers ||
        window.cars
      ) {
        // Use window globals if state is not populated yet
        if (state.customers.length === 0 && window.customers) {
          state.customers = window.customers;
        }
        if (state.cars.length === 0 && window.cars) {
          state.cars = window.cars;
        }
        resolve();
      } else {
        setTimeout(checkData, 50);
      }
    };
    checkData();
  });
}

// Function to prepare Update Button
function prepareUpdateButton(docType) {
  const buttonContainer = document.querySelector(".btns-submit");
  buttonContainer.innerHTML = ""; // Clear old buttons

  const updateButton = document.createElement("button");
  updateButton.type = "submit";
  updateButton.className = "wide-btn-submit";

  const buttonText =
    docType.toLowerCase() === "invoice" ? "Update Invoice" : "Update Quote";

  updateButton.innerText = buttonText;
  buttonContainer.appendChild(updateButton);
}

// ===== FORM SUBMISSION =====

// Handle form submission for updating invoice
async function handleFormSubmit(event) {
  event.preventDefault();

  // Collect form data
  const formData = collectFormData();

  // Validate form data
  if (!validateFormData(formData)) {
    return;
  }

  // Preserve the original document type
  const documentType = window.editingDocumentType || sessionStorage.getItem("documentType") || "invoice";

  // Add document type to form data
  const invoiceData = {
    ...formData,
    type_of: documentType.toLowerCase() === "invoice" ? "Invoice" : "Quote",
  };

  try {
    // Update customer and car records
    await updateCustomerAndCarRecords(formData);

    // Update the invoice
    const result = await APIHelper.put(`/api/invoice/${editId}/update`, invoiceData);

    if (!result) return;

    // Store invoice data in sessionStorage for the template page
    sessionStorage.setItem("invoiceData", JSON.stringify(invoiceData));
    sessionStorage.setItem("invoiceId", result.invoice_id);
    sessionStorage.setItem("documentType", documentType.toLowerCase());

    // Navigate to the invoice template page
    window.location.href = "invoice-template.html?from=invoice";
  } catch (error) {
    console.error("Error:", error);
    const errorMessage = error.message || "Failed to update document.";
    alert(errorMessage);
  }
}
