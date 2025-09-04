import { loadInvoiceForEdit } from "./editInvoiceUtils.js";
import { openInvoiceTemplate } from "./invoiceTemplateUtils.js";

let editId = 0;
let customers = [];
let cars = [];
let inventoryItems = [];
let selectedCustomerId = null;

document.addEventListener("DOMContentLoaded", () => {
  const params = new URLSearchParams(window.location.search);
  editId = params.get("id");

  // Load customers, cars, and inventory on page load
  loadCustomers();
  loadCars();
  loadInventory();

  if (editId) {
    loadInvoiceForEdit(editId);
  }

  // Add event listeners for searchable dropdowns
  setupSearchableDropdowns();

  // Add event listeners for modal buttons
  document
    .getElementById("add-customer-btn")
    .addEventListener("click", openCustomerModal);
  document
    .getElementById("add-car-btn")
    .addEventListener("click", openCarModal);

  // Modal close buttons
  document
    .getElementById("close-customer-modal")
    .addEventListener("click", closeCustomerModal);
  document
    .getElementById("close-car-modal")
    .addEventListener("click", closeCarModal);
  document
    .getElementById("cancel-customer")
    .addEventListener("click", closeCustomerModal);
  document
    .getElementById("cancel-car")
    .addEventListener("click", closeCarModal);

  // Modal form submissions
  document
    .getElementById("customer-form")
    .addEventListener("submit", handleCustomerSubmit);
  document
    .getElementById("car-form")
    .addEventListener("submit", handleCarSubmit);

  // Close modal when clicking outside
  window.addEventListener("click", function (event) {
    const customerModal = document.getElementById("customer-modal");
    const carModal = document.getElementById("car-modal");

    if (event.target === customerModal) {
      closeCustomerModal();
    }
    if (event.target === carModal) {
      closeCarModal();
    }
  });

  // Tax toggle functionality
  document
    .getElementById("tax-toggle")
    .addEventListener("change", updateTaxDisplay);

  // Document type toggle functionality
  document
    .getElementById("direct-invoice-toggle")
    .addEventListener("change", updateDocumentTypeToggle);

  // Inventory deduction button functionality
  document
    .getElementById("deduct-inventory-btn")
    .addEventListener("click", handleInventoryDeduction);

  // Set up searchable dropdowns
  setupSearchableDropdowns();

  // Set initial state of inventory deduction section (hidden by default in Quote Mode)
  const inventoryDeductionSection = document.querySelector(
    ".inventory-deduction-section"
  );
  if (inventoryDeductionSection) {
    inventoryDeductionSection.style.display = "none";
  }

  // Ensure quote mode is properly set on page load
  const toggle = document.getElementById("direct-invoice-toggle");
  if (toggle && !toggle.checked) {
    // Force update to ensure proper initial state
    updateDocumentTypeToggle();
  }
});

// Load customers from database
async function loadCustomers() {
  try {
    const response = await fetch("/api/customers");
    const data = await response.json();

    if (response.ok) {
      customers = data;
      window.customers = data; // Make available globally for edit functionality
      populateCustomerSelect();
    } else {
      console.error("Failed to load customers:", data.error);
    }
  } catch (error) {
    console.error("Error loading customers:", error);
  }
}

// Load cars from database
async function loadCars() {
  try {
    const response = await fetch("/api/cars");
    const data = await response.json();

    if (response.ok) {
      cars = data;
      window.cars = data; // Make available globally for edit functionality
      populateCarSelect();
    } else {
      console.error("Failed to load cars:", data.error);
    }
  } catch (error) {
    console.error("Error loading cars:", error);
  }
}

// Load inventory items from database
async function loadInventory() {
  try {
    const response = await fetch("/api/inventory");
    const data = await response.json();

    if (response.ok) {
      inventoryItems = data;
      window.inventoryItems = data; // Make available globally for edit functionality
    } else {
      console.error("Failed to load inventory:", data.error);
    }
  } catch (error) {
    console.error("Error loading inventory:", error);
  }
}

// Populate customer dropdown
function populateCustomerSelect() {
  const customerInput = document.getElementById("customer-select");
  const customerDropdown = document.getElementById("customer-dropdown-options");

  customerDropdown.innerHTML = "";

  customers.forEach((customer) => {
    const option = document.createElement("div");
    option.className = "dropdown-option";
    option.setAttribute("data-value", customer.id);
    option.textContent = `${customer.name} - ${customer.phone}`;
    customerDropdown.appendChild(option);
  });
}

// Populate car dropdown
function populateCarSelect() {
  const carInput = document.getElementById("car-select");
  const carDropdown = document.getElementById("car-dropdown-options");

  carDropdown.innerHTML = "";

  if (selectedCustomerId) {
    // Filter cars by selected customer
    const customerCars = cars.filter(
      (car) => car.customer_id === selectedCustomerId
    );
    customerCars.forEach((car) => {
      const option = document.createElement("div");
      option.className = "dropdown-option";
      option.setAttribute("data-value", car.id);
      option.textContent = `${car.make} ${car.model} - ${car.plate_no}`;
      carDropdown.appendChild(option);
    });
  }
}

// Set up searchable dropdowns
function setupSearchableDropdowns() {
  // Customer dropdown
  const customerInput = document.getElementById("customer-select");
  const customerDropdown = document.getElementById("customer-dropdown-options");

  // Show dropdown when input is clicked
  customerInput.addEventListener("click", function () {
    customerDropdown.style.display = "block";
    this.readOnly = false;
    this.removeAttribute("readonly");
    this.focus();
    // Force focus for mobile keyboard
    setTimeout(() => this.focus(), 100);
  });

  // Ensure keyboard opens on mobile touch
  customerInput.addEventListener("touchstart", function () {
    this.readOnly = false;
    this.removeAttribute("readonly");
    // Force focus for mobile keyboard
    setTimeout(() => this.focus(), 100);
  });

  // Handle search functionality for customers
  customerInput.addEventListener("input", function () {
    const searchTerm = this.value.toLowerCase();
    const options = customerDropdown.querySelectorAll(".dropdown-option");

    options.forEach((option) => {
      const text = option.textContent.toLowerCase();
      if (text.includes(searchTerm)) {
        option.style.display = "block";
      } else {
        option.style.display = "none";
      }
    });
  });

  // Handle option selection for customers
  customerDropdown.addEventListener("click", function (e) {
    if (e.target.classList.contains("dropdown-option")) {
      const selectedValue = e.target.getAttribute("data-value");
      const selectedText = e.target.textContent;

      customerInput.value = selectedText;
      customerDropdown.style.display = "none";
      // Don't set readonly - allow editing
      customerInput.readOnly = false;
      customerInput.removeAttribute("readonly");

      // Trigger customer change
      handleCustomerChange(parseInt(selectedValue));
    }
  });

  // Car dropdown
  const carInput = document.getElementById("car-select");
  const carDropdown = document.getElementById("car-dropdown-options");

  // Show dropdown when input is clicked
  carInput.addEventListener("click", function () {
    carDropdown.style.display = "block";
    this.readOnly = false;
    this.removeAttribute("readonly");
    this.focus();
    // Force focus for mobile keyboard
    setTimeout(() => this.focus(), 100);
  });

  // Ensure keyboard opens on mobile touch
  carInput.addEventListener("touchstart", function () {
    this.readOnly = false;
    this.removeAttribute("readonly");
    // Force focus for mobile keyboard
    setTimeout(() => this.focus(), 100);
  });

  // Handle search functionality for cars
  carInput.addEventListener("input", function () {
    const searchTerm = this.value.toLowerCase();
    const options = carDropdown.querySelectorAll(".dropdown-option");

    options.forEach((option) => {
      const text = option.textContent.toLowerCase();
      if (text.includes(searchTerm)) {
        option.style.display = "block";
      } else {
        option.style.display = "none";
      }
    });
  });

  // Handle option selection for cars
  carDropdown.addEventListener("click", function (e) {
    if (e.target.classList.contains("dropdown-option")) {
      const selectedValue = e.target.getAttribute("data-value");
      const selectedText = e.target.textContent;

      carInput.value = selectedText;
      carDropdown.style.display = "none";
      // Don't set readonly - allow editing
      carInput.readOnly = false;
      carInput.removeAttribute("readonly");

      // Trigger car change
      handleCarChange(parseInt(selectedValue));
    }
  });

  // Close dropdowns when clicking outside
  document.addEventListener("click", function (e) {
    if (
      !customerInput.contains(e.target) &&
      !customerDropdown.contains(e.target)
    ) {
      customerDropdown.style.display = "none";
      // Don't set readonly - allow editing
      customerInput.readOnly = false;
      customerInput.removeAttribute("readonly");
    }
    if (!carInput.contains(e.target) && !carDropdown.contains(e.target)) {
      carDropdown.style.display = "none";
      // Don't set readonly - allow editing
      carInput.readOnly = false;
      carInput.removeAttribute("readonly");
    }
  });
}

// Handle customer selection change
function handleCustomerChange(customerId) {
  selectedCustomerId = customerId;

  if (customerId) {
    const customer = customers.find((c) => c.id === customerId);
    if (customer) {
      // Populate customer details
      document.getElementById("customer_name").value = customer.name;
      document.getElementById("customer_address").value = customer.address;
      document.getElementById("customer_phone").value = customer.phone;
      document.getElementById("customer-details").style.display = "block";
    }

    // Reset car selection and populate car dropdown
    document.getElementById("car-select").value = "";
    document.getElementById("car-details").style.display = "none";
    populateCarSelect();
  } else {
    // Clear customer details
    document.getElementById("customer_name").value = "";
    document.getElementById("customer_address").value = "";
    document.getElementById("customer_phone").value = "";
    document.getElementById("customer-details").style.display = "none";

    // Clear car selection
    document.getElementById("car-select").value = "";
    document.getElementById("car-details").style.display = "none";
    populateCarSelect();
  }
}

// Make functions globally available for editInvoiceUtils.js
window.handleCustomerChange = handleCustomerChange;

// Handle car selection change
function handleCarChange(carId) {
  if (carId) {
    const car = cars.find((c) => c.id === carId);
    if (car) {
      // Populate car details
      document.getElementById("customer_reg").value = car.plate_no;
      document.getElementById(
        "customer_made"
      ).value = `${car.make} ${car.model}`;
      document.getElementById("customer_mileage").value = car.mileage;
      document.getElementById("customer_vin").value = car.vin || "";
      document.getElementById("customer_color").value = car.color || "";
      document.getElementById("customer_chasis").value = car.chasis_no || "";
      document.getElementById("car-details").style.display = "block";
    }
  } else {
    // Clear car details
    document.getElementById("customer_reg").value = "";
    document.getElementById("customer_made").value = "";
    document.getElementById("customer_mileage").value = "";
    document.getElementById("customer_vin").value = "";
    document.getElementById("customer_color").value = "";
    document.getElementById("customer_chasis").value = "";
    document.getElementById("car-details").style.display = "none";
  }
}

// Make functions globally available for editInvoiceUtils.js
window.handleCarChange = handleCarChange;

let counter = 0;

// Add labour
document.getElementById("add-labour").addEventListener("click", function () {
  addItem("labour");
});

// Add item
document.getElementById("add-item").addEventListener("click", function () {
  addItem("item");
});

export function addItem(type) {
  counter++;
  const itemContainer = document.createElement("div");
  itemContainer.classList.add("item");

  let htmlContent = `<p><i>${counter}:</i></p>`;

  if (type === "item") {
    htmlContent += `
      <div class="searchable-dropdown">
        <input type="text" class="product-name input-fields" placeholder="Search Part/Lubricant..." required readonly>
        <div class="dropdown-options" style="display: none;">
          ${inventoryItems
            .map(
              (item) =>
                `<div class="dropdown-option" data-value="${
                  item.name
                }" data-price="${item.price}" data-part-number="${
                  item.part_number || ""
                }">${item.part_number ? item.part_number + " - " : ""}${
                  item.name
                } - PKR ${item.price.toFixed(2)}</div>`
            )
            .join("")}
        </div>
      </div>
      <input type="text" placeholder="Part Number" class="part-number input-fields" readonly>
      <input type="number" placeholder="Quantity" class="quantity input-fields" min="1" required>
      <input type="number" placeholder="Price" class="price input-fields" min="0" step="0.01" required>
      <button type="button" class="delete-btn">Delete</button>
    `;
  } else {
    htmlContent += `
      <input type="text" placeholder="Labour Description" class="labour-description input-fields" required>
      <input type="number" placeholder="Price" class="price input-fields" min="0" step="0.01" required>
      <button type="button" class="delete-btn">Delete</button>
    `;
  }

  itemContainer.innerHTML = htmlContent;
  document.getElementById("items-container").appendChild(itemContainer);

  if (type === "item") {
    // Add event listeners for searchable dropdown
    const productInput = itemContainer.querySelector(".product-name");
    const dropdownOptions = itemContainer.querySelector(".dropdown-options");
    const priceInput = itemContainer.querySelector(".price");

    // Show dropdown when input is clicked
    productInput.addEventListener("click", function () {
      dropdownOptions.style.display = "block";
      this.readOnly = false;
      this.focus();
    });

    // Handle search functionality
    productInput.addEventListener("input", function () {
      const searchTerm = this.value.toLowerCase();
      const options = dropdownOptions.querySelectorAll(".dropdown-option");

      options.forEach((option) => {
        const text = option.textContent.toLowerCase();
        if (text.includes(searchTerm)) {
          option.style.display = "block";
        } else {
          option.style.display = "none";
        }
      });
    });

    // Handle option selection
    dropdownOptions.addEventListener("click", function (e) {
      if (e.target.classList.contains("dropdown-option")) {
        const selectedValue = e.target.getAttribute("data-value");
        const selectedPrice = e.target.getAttribute("data-price");
        const selectedPartNumber = e.target.getAttribute("data-part-number");

        productInput.value = selectedValue;
        priceInput.value = selectedPrice;

        // Populate part number field
        const partNumberInput = itemContainer.querySelector(".part-number");
        if (partNumberInput) {
          partNumberInput.value = selectedPartNumber || "";
        }

        dropdownOptions.style.display = "none";
        productInput.readOnly = true;
        updateTotal();
      }
    });

    // Close dropdown when clicking outside
    document.addEventListener("click", function (e) {
      if (!itemContainer.contains(e.target)) {
        dropdownOptions.style.display = "none";
        productInput.readOnly = true;
      }
    });

    itemContainer
      .querySelector(".quantity")
      .addEventListener("input", updateTotal);
    itemContainer
      .querySelector(".price")
      .addEventListener("input", updateTotal);
  } else {
    itemContainer
      .querySelector(".price")
      .addEventListener("input", updateTotal);
  }

  itemContainer
    .querySelector(".delete-btn")
    .addEventListener("click", function () {
      itemContainer.remove();
      updateTotal();
      updateBalance();
      counter--;
    });

  const inputs = itemContainer.querySelectorAll("input");
  inputs[inputs.length - 1].addEventListener("keydown", function (e) {
    if (e.key === "Tab" && !e.shiftKey) {
      e.preventDefault();
      if (type === "item") {
        addItem("item");
      } else {
        addItem("labour");
      }
      const newInputs = document
        .querySelectorAll(".item")
        [document.querySelectorAll(".item").length - 1].querySelectorAll(
          "input"
        );
      newInputs[0].focus();
    }
  });
}

// Update total cost
function updateTotal() {
  let total = 0;

  document.querySelectorAll(".item").forEach((item) => {
    const quantityInput = item.querySelector(".quantity");
    const price = parseFloat(item.querySelector(".price")?.value) || 0;

    if (quantityInput) {
      const quantity = parseInt(quantityInput.value) || 0;
      total += quantity * price;
    } else {
      total += price;
    }
  });

  document.getElementById(
    "total-amount"
  ).innerText = `Net Total: ${total.toFixed(2)} PKR`;
  updateBalance();
  updateTaxDisplay();
}

// Make functions globally available for editInvoiceUtils.js
window.updateTotal = updateTotal;

// Update tax display
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

// Make functions globally available for editInvoiceUtils.js
window.updateTaxDisplay = updateTaxDisplay;

// Update document type toggle
function updateDocumentTypeToggle() {
  const toggle = document.getElementById("direct-invoice-toggle");
  const descriptionText = document.getElementById("toggle-description-text");
  const submitButtons = document.querySelectorAll(".wide-btn-submit");
  const inventoryDeductionSection = document.querySelector(
    ".inventory-deduction-section"
  );

  if (toggle.checked) {
    // Direct Invoice Mode
    descriptionText.textContent =
      "Direct Invoice Mode: Generate invoices immediately";
    descriptionText.style.color = "#28a745";

    // Show inventory deduction section
    if (inventoryDeductionSection) {
      inventoryDeductionSection.style.display = "block";
    }

    // Update submit buttons to show invoice mode
    submitButtons.forEach((button) => {
      if (button.getAttribute("data-type") === "invoice") {
        button.style.display = "block";
        button.innerHTML = "Generate<br/>Invoice";
        button.style.backgroundColor = "#28a745";
      } else if (button.getAttribute("data-type") === "quote") {
        button.style.display = "none";
      }
    });
  } else {
    // Quote Mode
    descriptionText.textContent =
      "Quote Mode: Generate quotes for customer approval";
    descriptionText.style.color = "#6c757d";

    // Hide inventory deduction section
    if (inventoryDeductionSection) {
      inventoryDeductionSection.style.display = "none";
    }

    // Update submit buttons to show quote mode
    submitButtons.forEach((button) => {
      if (button.getAttribute("data-type") === "invoice") {
        button.style.display = "none";
      } else if (button.getAttribute("data-type") === "quote") {
        button.style.display = "block";
        button.innerHTML = "Generate<br/>Quote";
        button.style.backgroundColor = "#6c757d";
      }
    });
  }
}

// Handle inventory deduction button click
async function handleInventoryDeduction() {
  try {
    const items = [];
    document.querySelectorAll(".item").forEach((item) => {
      const productSelect = item.querySelector(".product-name");
      const productName = productSelect?.value.trim();
      const partNumberInput = item.querySelector(".part-number");
      const partNumber = partNumberInput?.value.trim();
      const quantity = parseInt(item.querySelector(".quantity")?.value) || 0;
      const price = parseFloat(item.querySelector(".price")?.value) || 0;

      if (productName && quantity > 0 && price >= 0) {
        items.push({
          product_name: productName,
          part_number: partNumber || null,
          quantity: quantity,
          price: price,
        });
      }
    });

    if (items.length === 0) {
      alert("No items found to deduct from inventory.");
      return;
    }

    const stockCheckResponse = await fetch("/api/inventory/check-stock", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ items: items }),
    });

    const stockCheckResult = await stockCheckResponse.json();

    if (!stockCheckResponse.ok) {
      alert(`Error checking inventory: ${stockCheckResult.error}`);
      return;
    }

    const { insufficient_items, available_items } = stockCheckResult;

    // Check if any available items have insufficient stock
    const itemsWithInsufficientStock = available_items.filter(
      (item) => item.insufficient_stock
    );

    // Show warning if there are items with insufficient stock or items not found
    if (
      itemsWithInsufficientStock.length > 0 ||
      insufficient_items.length > 0
    ) {
      let warningMessage = "⚠️ Inventory Status:\n\n";

      if (itemsWithInsufficientStock.length > 0) {
        warningMessage += "Items with insufficient stock:\n";
        itemsWithInsufficientStock.forEach((item) => {
          const partNumberText = item.inventory_part_number
            ? ` (${item.inventory_part_number})`
            : item.part_number
            ? ` (${item.part_number})`
            : "";
          warningMessage += `• ${item.product_name}${partNumberText}: Required ${item.quantity}, Available ${item.available_quantity}\n`;
        });
        warningMessage += "\n";
      }

      if (insufficient_items.length > 0) {
        warningMessage += "Items not found in inventory:\n";
        insufficient_items.forEach((item) => {
          const partNumberText = item.part_number
            ? ` (${item.part_number})`
            : "";
          warningMessage += `• ${item.product_name}${partNumberText}: Required ${item.quantity}\n`;
        });
        warningMessage += "\n";
      }

      const itemsWithSufficientStock = available_items.filter(
        (item) => !item.insufficient_stock
      );
      if (itemsWithSufficientStock.length > 0) {
        warningMessage += "✅ Items with sufficient stock:\n";
        itemsWithSufficientStock.forEach((item) => {
          const partNumberText = item.inventory_part_number
            ? ` (${item.inventory_part_number})`
            : item.part_number
            ? ` (${item.part_number})`
            : "";
          warningMessage += `• ${item.product_name}${partNumberText}: ${item.quantity} units\n`;
        });
        warningMessage += "\n";
      }

      warningMessage +=
        "⚠️ WARNING: Proceeding will attempt to deduct ALL items. Items with insufficient stock will go negative, and items not found will be skipped.\n\nDo you want to proceed?";

      const proceed = confirm(warningMessage);
      if (!proceed) {
        return;
      }
    }

    const deductionResponse = await fetch("/api/inventory/deduct-items", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        items: items, // Always use original items list to ensure all items are attempted
      }),
    });

    const deductionResult = await deductionResponse.json();

    if (!deductionResponse.ok) {
      alert(`Error deducting inventory: ${deductionResult.error}`);
      return;
    }

    // Show success message
    let successMessage = "✅ Inventory deduction completed!\n\n";

    if (deductionResult.deducted_items.length > 0) {
      successMessage += "Successfully deducted:\n";
      deductionResult.deducted_items.forEach((item) => {
        const partNumberText = item.inventory_part_number
          ? ` (${item.inventory_part_number})`
          : item.part_number
          ? ` (${item.part_number})`
          : "";
        const newQuantityText =
          item.new_quantity !== undefined
            ? ` (New stock: ${item.new_quantity})`
            : "";
        successMessage += `• ${item.product_name}${partNumberText}: ${item.quantity} units${newQuantityText}\n`;
      });
    }

    if (
      deductionResult.failed_items &&
      deductionResult.failed_items.length > 0
    ) {
      successMessage += "\n⚠️ Could not deduct:\n";
      deductionResult.failed_items.forEach((item) => {
        const partNumberText = item.part_number ? ` (${item.part_number})` : "";
        successMessage += `• ${item.product_name}${partNumberText}: ${item.reason}\n`;
      });
    }

    alert(successMessage);
  } catch (error) {
    console.error("Error handling inventory deduction:", error);
    console.error("Error details:", {
      message: error.message,
      stack: error.stack,
      name: error.name,
    });
    alert(`Error during inventory deduction: ${error.message}`);
  }
}

// Update balance
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

// Make functions globally available for editInvoiceUtils.js
window.updateBalance = updateBalance;
window.updateDocumentTypeToggle = updateDocumentTypeToggle;

// Attach event listener for advance input
document.querySelector(".advance").addEventListener("input", updateBalance);

// Attach event listener for discount input
document.getElementById("discount").addEventListener("input", updateBalance);

// Handle form submission
document
  .getElementById("invoice-form")
  .addEventListener("submit", async function (event) {
    event.preventDefault();

    const submitButton = event.submitter;
    const directInvoiceToggle = document.getElementById(
      "direct-invoice-toggle"
    );

    // Determine document type based on toggle and button clicked
    let documentType;

    // If we're editing an existing invoice, preserve the original document type
    if (window.editingInvoiceId) {
      // Get the original document type from sessionStorage or use the stored type
      const originalType =
        window.editingDocumentType || sessionStorage.getItem("documentType");
      if (originalType) {
        documentType = originalType.toLowerCase();
      } else {
        // Fallback to "invoice" if original type not found
        documentType = "invoice";
      }
    } else {
      // For new documents, use the toggle and button logic
      if (directInvoiceToggle.checked) {
        // Direct Invoice Mode - always create invoice
        documentType = "invoice";
      } else {
        // Quote Mode - use the button that was clicked
        documentType = submitButton.getAttribute("data-type") || "quote";
      }
    }

    const customerName = document.getElementById("customer_name").value.trim();
    const customerAddress = document
      .getElementById("customer_address")
      .value.trim();
    const customerPhone = document
      .getElementById("customer_phone")
      .value.trim();
    const customerReg = document.getElementById("customer_reg").value.trim();
    const customerMade = document.getElementById("customer_made").value.trim();
    const customerMileage = document
      .getElementById("customer_mileage")
      .value.trim();
    const customerVin = document.getElementById("customer_vin").value.trim();
    const advance = parseFloat(document.querySelector(".advance").value) || 0;
    const discount = parseFloat(document.getElementById("discount").value) || 0;

    let items = [];
    let labours = [];

    document.querySelectorAll(".item").forEach((item) => {
      const productSelect = item.querySelector(".product-name");
      const productName = productSelect?.value.trim();
      const partNumber = item.querySelector(".part-number")?.value.trim();
      const quantity = parseInt(item.querySelector(".quantity")?.value) || 0;
      const price = parseFloat(item.querySelector(".price")?.value) || 0;
      const labourDescription = item
        .querySelector(".labour-description")
        ?.value.trim();

      if (productName && quantity > 0 && price >= 0) {
        items.push({
          product_name: productName,
          part_number: partNumber || null,
          quantity,
          price,
        });
      } else if (labourDescription && price >= 0) {
        labours.push({ description: labourDescription, price });
      }
    });

    // Check if customer and car are selected
    const customerSelect = document.getElementById("customer-select");
    const carSelect = document.getElementById("car-select");

    if (!customerSelect.value) {
      alert("Please select a customer.");
      return;
    }

    if (!carSelect.value) {
      alert("Please select a car.");
      return;
    }

    if (
      !customerName ||
      !customerAddress ||
      !customerPhone ||
      !customerReg ||
      !customerMade ||
      !customerMileage ||
      (items.length === 0 && labours.length === 0)
    ) {
      alert(
        "Please ensure all customer and car details are filled, and add at least one valid item or labour."
      );
      return;
    }

    // Get tax information
    const taxToggle = document.getElementById("tax-toggle");
    const includeTax = taxToggle.checked;
    const taxAmount = includeTax
      ? parseFloat(
          document
            .getElementById("tax-amount")
            .textContent.replace(/[^\d.-]/g, "")
        )
      : 0;

    // Calculate net total (base amount without tax)
    const totalText = document.getElementById("total-amount").innerText;
    const netTotal = parseFloat(totalText.replace(/[^\d.-]/g, ""));

    // Calculate final balance (with or without tax)
    const finalBalance = parseFloat(
      document.getElementById("total-balance").innerText.replace(/[^\d.-]/g, "")
    );

    // Get selected car's color and chasis from form fields
    let customerColor = document.getElementById("customer_color").value || "";
    let customerChasis = document.getElementById("customer_chasis").value || "";

    // Store invoice data in sessionStorage for the template page
    const invoiceData = {
      customer_name: customerName,
      customer_address: customerAddress,
      customer_phone: customerPhone,
      customer_reg_no: customerReg,
      customer_made: customerMade,
      customer_mileage: customerMileage,
      customer_vin: customerVin,
      balance: finalBalance,
      advance: advance,
      discount: discount,
      type_of: documentType === "invoice" ? "Invoice" : "Quote",
      items: items,
      labours: labours,
      include_tax: includeTax,
      tax_amount: taxAmount,
      net_total: netTotal, // Store the base net total (without tax)
      customer_color: customerColor,
      customer_chasis: customerChasis,
    };

    try {
      let response;
      if (editId) {
        response = await fetch(`/api/invoice/${editId}/update`, {
          method: "PUT",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(invoiceData),
        });
      } else {
        response = await fetch("/api/add", {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(invoiceData),
        });
      }

      const result = await response.json();
      if (response.ok) {
        // Store invoice data in sessionStorage for the template page
        sessionStorage.setItem("invoiceData", JSON.stringify(invoiceData));
        sessionStorage.setItem("invoiceId", result.invoice_id);
        sessionStorage.setItem("documentType", documentType);

        // Navigate to the invoice template page with source parameter
        window.location.href = "invoice-template.html?from=invoice";

        document.getElementById("invoice-form").reset();
        document.getElementById("total-amount").innerText =
          "Net Total: 0.00 PKR";
        document.getElementById("total-balance").innerText =
          "Balance: 0.00 PKR";
        document.getElementById("items-container").innerHTML = ``;
        counter = 0;

        // Reset dropdowns and details
        document.getElementById("customer-details").style.display = "none";
        document.getElementById("car-details").style.display = "none";
        selectedCustomerId = null;
      } else {
        if (result.details && Array.isArray(result.details)) {
          alert("Validation failed:\n" + result.details.join("\n"));
        } else {
          alert("Error: " + result.error);
        }
      }
    } catch (error) {
      console.error("Error:", error);
      alert("Failed to create document.");
    }
  });

// ===== MODAL FUNCTIONS =====

// Customer Modal Functions
function openCustomerModal() {
  const modal = document.getElementById("customer-modal");
  const form = document.getElementById("customer-form");
  form.reset();
  modal.classList.add("active");
}

function closeCustomerModal() {
  const modal = document.getElementById("customer-modal");
  modal.classList.remove("active");
}

async function handleCustomerSubmit(e) {
  e.preventDefault();

  const customerData = {
    name: document.getElementById("modal-customer-name").value.trim() || "N/A",
    phone:
      document.getElementById("modal-customer-phone").value.trim() || "N/A",
    address:
      document.getElementById("modal-customer-address").value.trim() || "N/A",
  };

  try {
    const response = await fetch("/api/customers", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(customerData),
    });

    const data = await response.json();

    if (response.ok) {
      alert("Customer created successfully!");
      closeCustomerModal();
      await loadCustomers(); // Reload customers

      // Auto-select the newly created customer
      const newCustomer = data.customer;
      const customerDisplayText = `${newCustomer.name} - ${newCustomer.phone}`;
      document.getElementById("customer-select").value = customerDisplayText;

      // Trigger customer change with the correct ID
      handleCustomerChange(newCustomer.id);
    } else {
      alert(
        "Failed to create customer: " +
          (data.details ? data.details.join(", ") : data.error)
      );
    }
  } catch (error) {
    alert("Error creating customer: " + error.message);
  }
}

// Car Modal Functions
function openCarModal() {
  const modal = document.getElementById("car-modal");
  const form = document.getElementById("car-form");
  const customerSelect = document.getElementById("modal-car-customer");

  // Populate customer dropdown in modal
  customerSelect.innerHTML = '<option value="">Select Customer</option>';
  customers.forEach((customer) => {
    const option = document.createElement("option");
    option.value = customer.id;
    option.textContent = `${customer.name} - ${customer.phone}`;
    customerSelect.appendChild(option);
  });

  form.reset();
  modal.classList.add("active");
}

function closeCarModal() {
  const modal = document.getElementById("car-modal");
  modal.classList.remove("active");
}

async function handleCarSubmit(e) {
  e.preventDefault();

  const carData = {
    customer_id:
      parseInt(document.getElementById("modal-car-customer").value) || null,
    make: document.getElementById("modal-car-make").value.trim() || "N/A",
    model: document.getElementById("modal-car-model").value.trim() || "N/A",
    plate_no: document.getElementById("modal-car-plate").value.trim() || "N/A",
    mileage: document.getElementById("modal-car-mileage").value.trim() || "N/A",
    vin: document.getElementById("modal-car-vin").value.trim() || "N/A",
    color: document.getElementById("modal-car-color").value.trim() || "N/A",
    chasis_no:
      document.getElementById("modal-car-chasis").value.trim() || "N/A",
  };

  try {
    const response = await fetch("/api/cars", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(carData),
    });

    const data = await response.json();

    if (response.ok) {
      alert("Car created successfully!");
      closeCarModal();
      await loadCars(); // Reload cars

      // If a customer is selected, refresh the car dropdown
      if (selectedCustomerId) {
        populateCarSelect();

        // Auto-select the newly created car if it belongs to the selected customer
        const newCar = data.car;
        if (newCar.customer_id === selectedCustomerId) {
          const carDisplayText = `${newCar.make} ${newCar.model} - ${newCar.plate_no}`;
          document.getElementById("car-select").value = carDisplayText;

          // Trigger car change with the correct ID
          handleCarChange(newCar.id);
        }
      }
    } else {
      alert(
        "Failed to create car: " +
          (data.details ? data.details.join(", ") : data.error)
      );
    }
  } catch (error) {
    alert("Error creating car: " + error.message);
  }
}
