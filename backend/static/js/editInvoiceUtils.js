// addItem function will be available globally

// Function to check if invoice is older than 1 day
function isInvoiceOlderThanOneDay(createdAtStr) {
  const createdDate = new Date(createdAtStr);
  const currentDate = new Date();
  const oneDayInMs = 24 * 60 * 60 * 1000; // 24 hours in milliseconds
  return currentDate - createdDate > oneDayInMs;
}

// Function to check if user can edit this invoice
function canUserEditInvoice(invoice) {
  // Get current user from auth system
  const userStr = localStorage.getItem("user");
  if (!userStr) return false;

  const user = JSON.parse(userStr);

  // Admins can always edit
  if (user.role === "admin") {
    return true;
  }

  // Accountants can always edit quotes, but invoices older than 1 day are restricted
  if (user.role === "accountant") {
    // If it's a quote, allow editing
    if (invoice.type_of.toLowerCase() === "quote") {
      return true;
    }
    // If it's an invoice, check if it's older than 1 day
    return !isInvoiceOlderThanOneDay(invoice.created_at);
  }

  // Other roles cannot edit
  return false;
}

export async function loadInvoiceForEdit(invoiceId) {
  try {
    const data = await APIHelper.get(`/api/invoice/${invoiceId}`);
    if (!data) {
      showError("Failed to fetch invoice for editing.");
      return;
    }

    // Check if user can edit this invoice based on role and time restrictions
    if (!canUserEditInvoice(data)) {
      showError(
        "You cannot edit invoices older than 1 day. Please contact an administrator."
      );
      window.history.back();
      return;
    }

    // Wait for customers and cars to be loaded
    await waitForData();

    // Wait for required functions to be available
    await waitForFunctions();

    // Find and select the customer based on name and phone
    const customerSelect = document.getElementById("customer-select");
    const customer = window.customers?.find(
      (c) => c.name === data.customer_name && c.phone === data.customer_phone
    );

    if (customer) {
      const customerDisplayText = `${customer.name} - ${customer.phone}`;
      customerSelect.value = customerDisplayText;
      // Trigger the customer change event to populate customer details and car dropdown
      handleCustomerChange(customer.id);

      // Wait a bit for the car dropdown to be populated
      setTimeout(() => {
        // Find and select the car based on registration number
        const carSelect = document.getElementById("car-select");
        const car = window.cars?.find(
          (c) => c.plate_no === data.customer_reg_no
        );

        if (car) {
          const carDisplayText = `${car.make} ${car.model} - ${car.plate_no}`;
          carSelect.value = carDisplayText;
          // Trigger the car change event to populate car details
          handleCarChange(car.id);
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
    window.counter = 0;

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
      lastLabour.querySelector(".labour-description").value =
        labour.description;
      lastLabour.querySelector(".price").value = labour.price;

      const hiddenInput = document.createElement("input");
      hiddenInput.type = "hidden";
      hiddenInput.classList.add("labour-id");
      hiddenInput.value = labour.id;
      lastLabour.appendChild(hiddenInput);
    });

    // Show only Update button
    prepareUpdateButton(data.type_of);

    // Hide the document type toggle when editing
    const documentTypeToggleContainer = document.querySelector(
      ".document-type-toggle"
    );
    if (documentTypeToggleContainer) {
      documentTypeToggleContainer.style.display = "none";
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

// Function to wait for customers and cars data to be loaded
function waitForData() {
  return new Promise((resolve) => {
    const checkData = () => {
      if (window.customers && window.cars) {
        resolve();
      } else {
        setTimeout(checkData, 50);
      }
    };
    checkData();
  });
}

// Function to wait for required functions to be available
function waitForFunctions() {
  return new Promise((resolve) => {
    const checkFunctions = () => {
      if (
        window.handleCustomerChange &&
        window.handleCarChange &&
        window.updateTotal &&
        window.updateTaxDisplay &&
        window.updateBalance
      ) {
        resolve();
      } else {
        setTimeout(checkFunctions, 50);
      }
    };
    checkFunctions();
  });
}

// Function to prepare Update Button
function prepareUpdateButton(docType) {
  const buttonContainer = document.querySelector(".btns-submit");
  buttonContainer.innerHTML = ""; // Clear old buttons

  const updateButton = document.createElement("button");
  updateButton.type = "submit";
  updateButton.className = "wide-btn-submit";

  // When editing, use the document type directly since toggle is hidden
  // Make the comparison case-insensitive
  const buttonText =
    docType.toLowerCase() === "invoice" ? "Update Invoice" : "Update Quote";

  updateButton.innerText = buttonText;
  buttonContainer.appendChild(updateButton);
}

// Using global updateTotal and updateBalance functions from script.js

// Function to update tax display
function updateTaxDisplay() {
  const taxToggle = document.getElementById("tax-toggle");
  const taxAmountDisplay = document.getElementById("tax-amount-display");
  const taxAmount = document.getElementById("tax-amount");

  if (taxToggle.checked) {
    const totalText = document.getElementById("total-amount").innerText;
    const total = parseFloat(totalText.replace(/[^\d.-]/g, ""));
    const taxValue = total * 0.17; // 17% tax

    taxAmount.textContent = `${taxValue.toFixed(2)} PKR`;
    taxAmountDisplay.style.display = "block";
  } else {
    taxAmountDisplay.style.display = "none";
  }
}

// Update balance function
function updateBalance() {
  const totalText = document.getElementById("total-amount").innerText;
  const total = parseFloat(totalText.replace(/[^\d.-]/g, ""));
  const advance = parseFloat(document.querySelector(".advance").value) || 0;
  const discount = parseFloat(document.getElementById("discount").value) || 0;
  const balance = total - advance - discount;

  document.getElementById(
    "total-balance"
  ).innerText = `Balance: ${balance.toFixed(2)} PKR`;
}

// Attach event listener to advance field AFTER DOM loaded
document.addEventListener("DOMContentLoaded", function () {
  document.querySelector(".advance").addEventListener("input", updateBalance);
  document.getElementById("discount").addEventListener("input", updateBalance);
});
