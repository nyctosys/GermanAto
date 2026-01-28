/**
 * Create Invoice Module
 * Handles creating new invoices and quotes
 */

import {
  state,
  loadCustomers,
  loadCars,
  loadInventory,
  setupSearchableDropdowns,
  setupCommonEventListeners,
  updateDocumentTypeToggle,
  handleInventoryDeduction,
  collectFormData,
  validateFormData,
  updateCustomerAndCarRecords,
  resetForm,
  updateTotal,
  handleCustomerChange,
  handleCarChange,
  addItem,
} from "./invoiceShared.js";

// Initialize create invoice page
async function initializeCreateInvoice() {
  console.log("Create Invoice module loaded");

  // Wait for required elements to be available
  const invoiceForm = document.getElementById("invoice-form");
  if (!invoiceForm) {
    console.error("Invoice form not found, retrying...");
    setTimeout(initializeCreateInvoice, 100);
    return;
  }

  // Load data
  loadCustomers();
  loadCars();
  await loadInventory();

  // Check if we're coming from a repair order
  const urlParams = new URLSearchParams(window.location.search);
  const fromRepairOrder = urlParams.get("from") === "repair-order";

  if (fromRepairOrder) {
    // Set to invoice mode when coming from repair order
    const directInvoiceToggle = document.getElementById("direct-invoice-toggle");
    if (directInvoiceToggle) {
      directInvoiceToggle.checked = true;
      updateDocumentTypeToggle();
    }

    // Wait for data to load before loading repair order data
    setTimeout(() => {
      loadRepairOrderData();
    }, 1000);
  }

  // Set up event listeners
  setupSearchableDropdowns();
  setupCommonEventListeners();

  // Document type toggle functionality
  document
    .getElementById("direct-invoice-toggle")
    .addEventListener("change", updateDocumentTypeToggle);

  // Inventory deduction button
  document
    .getElementById("deduct-inventory-btn")
    .addEventListener("click", handleInventoryDeduction);

  // Set initial state of inventory deduction section (hidden by default in Quote Mode)
  const inventoryDeductionSection = document.querySelector(".inventory-deduction-section");
  if (inventoryDeductionSection) {
    inventoryDeductionSection.style.display = "none";
  }

  // Ensure quote mode is properly set on page load
  const toggle = document.getElementById("direct-invoice-toggle");
  if (toggle && !toggle.checked) {
    updateDocumentTypeToggle();
  }

  // Set up form submission
  document
    .getElementById("invoice-form")
    .addEventListener("submit", handleFormSubmit);
}

// Initialize when DOM is ready or immediately if already loaded
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeCreateInvoice);
} else {
  // DOM is already loaded
  initializeCreateInvoice();
}

// Handle form submission for creating new invoice
async function handleFormSubmit(event) {
  event.preventDefault();

  const submitButton = event.submitter;
  const directInvoiceToggle = document.getElementById("direct-invoice-toggle");

  // Determine document type based on toggle and button clicked
  let documentType;
  if (directInvoiceToggle.checked) {
    // Direct Invoice Mode - always create invoice
    documentType = "invoice";
  } else {
    // Quote Mode - use the button that was clicked
    documentType = submitButton.getAttribute("data-type") || "quote";
  }

  // Collect form data
  const formData = collectFormData();

  // Validate form data
  if (!validateFormData(formData)) {
    return;
  }

  // Add document type to form data
  const invoiceData = {
    ...formData,
    type_of: documentType === "invoice" ? "Invoice" : "Quote",
  };

  try {
    // Update customer and car records
    await updateCustomerAndCarRecords(formData);

    // Create the invoice
    const result = await APIHelper.post("/api/add", invoiceData);

    if (!result) return;

    // Store invoice data in sessionStorage for the template page
    sessionStorage.setItem("invoiceData", JSON.stringify(invoiceData));
    sessionStorage.setItem("invoiceId", result.invoice_id);
    sessionStorage.setItem("documentType", documentType);

    // Navigate to the invoice template page
    window.location.href = "invoice-template.html?from=invoice";

    // Reset form
    resetForm();
  } catch (error) {
    console.error("Error:", error);
    const errorMessage = error.message || "Failed to create document.";
    alert(errorMessage);
  }
}

// Load repair order data for invoice generation
function loadRepairOrderData() {
  try {
    const repairOrderData = JSON.parse(sessionStorage.getItem("repairOrderForInvoice"));
    if (!repairOrderData) return;

    // Populate customer information
    document.getElementById("customer_name").value = repairOrderData.customer_name || "";
    document.getElementById("customer_address").value = repairOrderData.customer_address || "";
    document.getElementById("customer_phone").value = repairOrderData.customer_phone || "";

    // Populate vehicle information
    document.getElementById("customer_reg").value = repairOrderData.customer_reg_no || "";
    document.getElementById("customer_made").value = repairOrderData.customer_made || "";
    document.getElementById("customer_mileage").value = repairOrderData.customer_mileage || "";
    document.getElementById("customer_vin").value = repairOrderData.customer_vin || "";
    document.getElementById("customer_color").value = repairOrderData.customer_color || "";
    document.getElementById("customer_chasis").value = repairOrderData.customer_chasis || "";

    // Find and select the correct customer
    const customer = state.customers.find(
      (c) =>
        c.name === repairOrderData.customer_name &&
        c.phone === repairOrderData.customer_phone
    );
    if (customer) {
      const customerDisplayText = `${customer.name} - ${customer.phone}`;
      document.getElementById("customer-select").value = customerDisplayText;
      handleCustomerChange(customer.id);
    } else {
      const customerDisplayText = `${repairOrderData.customer_name} - ${repairOrderData.customer_phone}`;
      document.getElementById("customer-select").value = customerDisplayText;
    }

    // Find and select the correct car
    const car = state.cars.find((c) => c.plate_no === repairOrderData.customer_reg_no);
    if (car) {
      const carDisplayText = `${car.make} - ${car.plate_no}`;
      document.getElementById("car-select").value = carDisplayText;
      handleCarChange(car.id);
    } else {
      const carDisplayText = `${repairOrderData.customer_made} - ${repairOrderData.customer_reg_no}`;
      document.getElementById("car-select").value = carDisplayText;
    }

    // Clear existing items before adding repair order parts
    const itemsContainer = document.getElementById("items-container");
    if (itemsContainer) {
      itemsContainer.innerHTML = "";
    }

    // Reset the counter for proper item numbering
    state.counter = 0;

    // Populate parts from repair order
    if (repairOrderData.parts && repairOrderData.parts.length > 0) {
      repairOrderData.parts.forEach((part) => {
        addItem("item");
        const items = document.querySelectorAll(".item");
        const lastItem = items[items.length - 1];

        const productNameInput = lastItem.querySelector(".product-name");
        if (productNameInput) {
          productNameInput.value = part.description || "";
        }

        const partNumberInput = lastItem.querySelector(".part-number");
        if (partNumberInput) {
          partNumberInput.value = part.part_number || "";
        }

        const quantityInput = lastItem.querySelector(".quantity");
        if (quantityInput) {
          quantityInput.value = part.quantity || "";
        }

        // Clear price field - repair order parts don't have prices
        const priceInput = lastItem.querySelector(".price");
        if (priceInput) {
          priceInput.value = "";
        }
      });

      updateTotal();
    }

    // Populate labour from repair order
    if (repairOrderData.labour && repairOrderData.labour.length > 0) {
      repairOrderData.labour.forEach((labour) => {
        addItem("labour");

        setTimeout(() => {
          const items = document.querySelectorAll(".item");
          const lastItem = items[items.length - 1];

          const labourDescriptionInput = lastItem.querySelector(".labour-description");
          if (labourDescriptionInput) {
            labourDescriptionInput.value = labour.description || "";
          }

          const priceInput = lastItem.querySelector(".price");
          if (priceInput) {
            priceInput.value = "";
          }
        }, 100);
      });

      setTimeout(() => {
        updateTotal();
      }, 200);
    }

    // Clear the repair order data from session storage
    sessionStorage.removeItem("repairOrderForInvoice");

    alert("Repair order data loaded successfully!");
  } catch (error) {
    console.error("Error loading repair order data:", error);
    alert("Error loading repair order data.");
  }
}
