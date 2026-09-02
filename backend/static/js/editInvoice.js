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

/**
 * The car a document was written against.
 *
 * Mirrors document_links.resolve_car on the server, deliberately: the id
 * first, then the VIN, then the plate - and the plate compared with spacing
 * and punctuation stripped, because 'ABC-123' and 'ABC 123' are the same car
 * to everyone except a string comparison. Exact matching alone failed on 18
 * of the 500 invoices on file for that reason.
 *
 * The customer's own car wins when two share a plate. A car with no owner is
 * still accepted - it is almost certainly theirs, and saving the document
 * claims it.
 */
function resolveCarForDocument(data, customer) {
  const cars = state.cars || [];
  const plate = (v) => String(v || "").replace(/[^A-Za-z0-9]/g, "").toUpperCase();

  if (data.car_id) {
    const linked = cars.find((c) => c.id === data.car_id);
    if (linked) return linked;
  }

  const vin = String(data.customer_vin || "").trim().toUpperCase();
  if (vin) {
    const byVin = cars.find((c) => String(c.vin || "").trim().toUpperCase() === vin);
    if (byVin) return byVin;
  }

  const wanted = plate(data.customer_reg_no);
  if (!wanted) return null;

  const samePlate = cars.filter((c) => plate(c.plate_no) === wanted);
  return (
    samePlate.find((c) => c.customer_id === customer.id) ||
    samePlate.find((c) => !c.customer_id) ||
    null
  );
}

/** The form on whichever page we are editing from - invoice or quote. */
function getDocumentForm() {
  return (
    document.getElementById("invoice-form") || document.getElementById("quote-form")
  );
}

// Initialize edit invoice page
async function initializeEditInvoice() {
  // Wait for required elements to be available
  // Editing is shared, but the two forms have different ids - a quote is
  // edited on the quote page, where the form is #quote-form. Looking only for
  // #invoice-form left the quote page retrying forever with an empty form.
  const invoiceForm = getDocumentForm();
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
  getDocumentForm().addEventListener("submit", handleFormSubmit);
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

  // Admins and accountants can always edit (including invoices older than 1 day)
  if (user.role === "admin" || user.role === "accountant") {
    return true;
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

    // The invoice's own text is what it recorded, so paint it first and
    // unconditionally. Before this, an invoice naming a customer with no
    // record fell through every match below and opened with the customer and
    // vehicle boxes empty - which read as "the edit did not save".
    fillDocumentFields(data);

    // Find and select the customer based on name and phone
    const customerSelect = document.getElementById("customer-select");

    // The stored link is what the user actually picked; the name and phone
    // matching below is only for invoices written before that link existed.
    let customer = data.customer_id
      ? state.customers?.find((c) => c.id === data.customer_id)
      : null;

    // Try exact match first (name AND phone)
    if (!customer) {
      customer = state.customers?.find(
        (c) => c.name === data.customer_name && c.phone === data.customer_phone
      );
    }
    // Fallback: match by phone only
    if (!customer && data.customer_phone) {
      customer = state.customers?.find((c) => c.phone === data.customer_phone);
    }
    // Fallback: match by name only
    if (!customer && data.customer_name) {
      customer = state.customers?.find((c) => c.name === data.customer_name);
    }

    if (customer) {
      const customerDisplayText = `${customer.code ? customer.code + " · " : ""}${customer.name} - ${customer.phone}`;
      customerSelect.value = customerDisplayText;
      handleCustomerChange(customer.id);

      // Wait for car dropdown to be populated with customer's cars
      setTimeout(() => {
        const carSelect = document.getElementById("car-select");
        const car = resolveCarForDocument(data, customer);

        if (car) {
          const carDisplayText = `${car.make} ${car.model} - ${car.plate_no}`;
          carSelect.value = carDisplayText;
          handleCarChange(car.id);
          // handleCarChange paints the car's *current* details over the form.
          // This invoice recorded a mileage, and possibly an address, that were
          // true on the day it was written - put them back.
          fillDocumentFields(data);
        }
        document.getElementById("car-details").style.display = "block";
      }, 100);
    }

    // The quote form has no advance field - nothing is owed on a quote. Left
    // unguarded this threw, and everything below it (discount, tax, items,
    // totals) never ran, leaving the form half empty with no error shown.
    const advanceInput = document.querySelector(".advance");
    if (advanceInput) advanceInput.value = data.advance || 0;

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

/**
 * Paint the document's own stored values into the form.
 *
 * An invoice is a historical record: its mileage, address and vehicle details
 * are what were true the day it was written, not what the customer and car
 * records say today. Selecting a customer or car overwrites those boxes with
 * current details, so this puts the document's own values back.
 */
function fillDocumentFields(data) {
  const set = (id, value) => {
    const field = document.getElementById(id);
    if (field) field.value = value || "";
  };
  set("customer_name", data.customer_name);
  set("customer_address", data.customer_address);
  set("customer_phone", data.customer_phone);
  set("customer_reg", data.customer_reg_no);
  set("customer_made", data.customer_made);
  set("customer_mileage", data.customer_mileage);
  set("customer_vin", data.customer_vin);
  set("customer_color", data.customer_color);
  set("customer_chasis", data.customer_chasis);
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

    // Navigate to the invoice template page (id in URL so refresh re-fetches from API)
    window.location.href = `invoice-template.html?from=invoice&id=${editId}`;
  } catch (error) {
    console.error("Error:", error);
    const errorMessage = error.message || "Failed to update document.";
    alert(errorMessage);
  }
}
