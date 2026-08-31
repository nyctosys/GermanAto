/**
 * Invoice Shared Utilities
 * Common functions used by both createInvoice.js and editInvoice.js
 */

// ===== STATE MANAGEMENT =====
export const state = {
  customers: [],
  cars: [],
  inventoryItems: [],
  selectedCustomerId: null,
  selectedCarId: null,
  counter: 0,
};

// ===== DATA LOADING =====

// Load customers from database
export async function loadCustomers() {
  try {
    const data = await CustomerCarUtils.loadCustomers();
    if (!data) return;

    state.customers = data;
    window.customers = data; // Make available globally
    populateCustomerSelect();
  } catch (error) {
    console.error("Error loading customers:", error);
  }
}

// Load cars from database
export async function loadCars() {
  try {
    const data = await CustomerCarUtils.loadCars();
    if (!data) return;

    state.cars = data;
    window.cars = data; // Make available globally
    populateCarSelect();
  } catch (error) {
    console.error("Error loading cars:", error);
  }
}

// Load inventory items from database
export async function loadInventory() {
  try {
    const data = await APIHelper.get("/api/inventory");

    if (!data) {
      return;
    }

    state.inventoryItems = data.items || data;
    window.inventoryItems = data.items || data; // Make available globally

    // Refresh any existing item dropdowns
    const itemContainers = document.querySelectorAll(".item");
    itemContainers.forEach((container) => {
      if (container.refreshDropdownOptions) {
        container.refreshDropdownOptions();
      }
    });
  } catch (error) {
    console.error("Error loading inventory:", error);
  }
}

// ===== DROPDOWN POPULATION =====

// Populate customer dropdown
export function populateCustomerSelect() {
  const customerDropdown = document.getElementById("customer-dropdown-options");
  if (!customerDropdown) return;

  customerDropdown.innerHTML = "";

  state.customers.forEach((customer) => {
    const option = document.createElement("div");
    option.className = "dropdown-option";
    option.setAttribute("data-value", customer.id);
    option.textContent = `${customer.name} - ${customer.phone}`;
    customerDropdown.appendChild(option);
  });
}

// Populate car dropdown
export function populateCarSelect() {
  const carDropdown = document.getElementById("car-dropdown-options");
  const carInput = document.getElementById("car-select");
  if (!carDropdown) return;

  carDropdown.innerHTML = "";

  if (state.selectedCustomerId) {
    // Filter cars by selected customer
    const customerCars = state.cars.filter(
      (car) => car.customer_id === state.selectedCustomerId
    );
    
    if (customerCars.length === 0) {
      // Show message if no cars found for this customer
      const noCarsOption = document.createElement("div");
      noCarsOption.className = "dropdown-option";
      noCarsOption.style.color = "#666";
      noCarsOption.style.fontStyle = "italic";
      noCarsOption.textContent = "No cars found for this customer";
      carDropdown.appendChild(noCarsOption);
    } else {
      customerCars.forEach((car) => {
        const option = document.createElement("div");
        option.className = "dropdown-option";
        option.setAttribute("data-value", car.id);
        option.textContent = `${car.make} ${car.model} - ${car.plate_no}`;
        carDropdown.appendChild(option);
      });
    }
  } else {
    // Show message if no customer is selected
    const noCustomerOption = document.createElement("div");
    noCustomerOption.className = "dropdown-option";
    noCustomerOption.style.color = "#666";
    noCustomerOption.style.fontStyle = "italic";
    noCustomerOption.textContent = "Please select a customer first";
    carDropdown.appendChild(noCustomerOption);
    
    // Clear car input if no customer is selected
    if (carInput) {
      carInput.value = "";
    }
  }
}

// ===== SEARCHABLE DROPDOWNS =====

// Set up searchable dropdowns for customer and car
export function setupSearchableDropdowns() {
  // Customer dropdown
  const customerInput = document.getElementById("customer-select");
  const customerDropdown = document.getElementById("customer-dropdown-options");

  if (!customerInput || !customerDropdown) return;

  // Show dropdown when input is clicked
  customerInput.addEventListener("click", function () {
    customerDropdown.style.display = "block";
    this.readOnly = false;
    this.removeAttribute("readonly");
    this.focus();
    setTimeout(() => this.focus(), 100);
    const sectionCard = this.closest(".section-card");
    if (sectionCard) {
      sectionCard.classList.add("dropdown-active");
    }
  });

  // Ensure keyboard opens on mobile touch
  customerInput.addEventListener("touchstart", function () {
    this.readOnly = false;
    this.removeAttribute("readonly");
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
      customerInput.readOnly = false;
      customerInput.removeAttribute("readonly");

      const sectionCard = customerInput.closest(".section-card");
      if (sectionCard) {
        sectionCard.classList.remove("dropdown-active");
      }

      handleCustomerChange(parseInt(selectedValue));
    }
  });

  // Car dropdown
  const carInput = document.getElementById("car-select");
  const carDropdown = document.getElementById("car-dropdown-options");

  if (!carInput || !carDropdown) return;

  // Show dropdown when input is clicked
  carInput.addEventListener("click", function () {
    // Check if a customer is selected
    if (!state.selectedCustomerId) {
      alert("Please select a customer first before selecting a car.");
      return;
    }
    
    // Refresh car list to show only selected customer's cars
    populateCarSelect();
    
    carDropdown.style.display = "block";
    this.readOnly = false;
    this.removeAttribute("readonly");
    this.focus();
    setTimeout(() => this.focus(), 100);
    const sectionCard = this.closest(".section-card");
    if (sectionCard) {
      sectionCard.classList.add("dropdown-active");
    }
  });

  // Ensure keyboard opens on mobile touch
  carInput.addEventListener("touchstart", function () {
    // Check if a customer is selected
    if (!state.selectedCustomerId) {
      alert("Please select a customer first before selecting a car.");
      return;
    }
    
    // Refresh car list to show only selected customer's cars
    populateCarSelect();
    
    this.readOnly = false;
    this.removeAttribute("readonly");
    setTimeout(() => this.focus(), 100);
  });

  // Handle search functionality for cars
  carInput.addEventListener("input", function () {
    // If no customer is selected, show message
    if (!state.selectedCustomerId) {
      populateCarSelect();
      carDropdown.style.display = "block";
      return;
    }
    
    const searchTerm = this.value.toLowerCase();
    
    // Refresh car list first to ensure we're showing only customer's cars
    populateCarSelect();
    
    // Then filter by search term
    const options = carDropdown.querySelectorAll(".dropdown-option");
    options.forEach((option) => {
      const text = option.textContent.toLowerCase();
      if (text.includes(searchTerm)) {
        option.style.display = "block";
      } else {
        option.style.display = "none";
      }
    });
    
    // Show dropdown if there are visible options
    const visibleOptions = Array.from(options).filter(opt => opt.style.display !== "none");
    if (visibleOptions.length > 0) {
      carDropdown.style.display = "block";
    }
  });

  // Handle option selection for cars
  carDropdown.addEventListener("click", function (e) {
    if (e.target.classList.contains("dropdown-option")) {
      const selectedValue = e.target.getAttribute("data-value");
      const selectedText = e.target.textContent;

      carInput.value = selectedText;
      carDropdown.style.display = "none";
      carInput.readOnly = false;
      carInput.removeAttribute("readonly");

      const sectionCard = carInput.closest(".section-card");
      if (sectionCard) {
        sectionCard.classList.remove("dropdown-active");
      }

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
      customerInput.readOnly = false;
      customerInput.removeAttribute("readonly");
      const sectionCard = customerInput.closest(".section-card");
      if (sectionCard) {
        sectionCard.classList.remove("dropdown-active");
      }
    }
    if (!carInput.contains(e.target) && !carDropdown.contains(e.target)) {
      carDropdown.style.display = "none";
      carInput.readOnly = false;
      carInput.removeAttribute("readonly");
      const sectionCard = carInput.closest(".section-card");
      if (sectionCard) {
        sectionCard.classList.remove("dropdown-active");
      }
    }
  });
}

// ===== CUSTOMER/CAR CHANGE HANDLERS =====

// Handle customer selection change
export function handleCustomerChange(customerId) {
  state.selectedCustomerId = customerId;
  
  // Clear car selection when customer changes
  state.selectedCarId = null;

  if (customerId) {
    const customer = state.customers.find((c) => c.id === customerId);
    if (customer) {
      document.getElementById("customer_name").value = customer.name;
      document.getElementById("customer_address").value = customer.address;
      document.getElementById("customer_phone").value = customer.phone;
      document.getElementById("customer-details").style.display = "block";
    }

    // Clear car input and details
    const carSelect = document.getElementById("car-select");
    if (carSelect) {
      carSelect.value = "";
    }
    document.getElementById("car-details").style.display = "none";
    
    // Clear car details fields
    document.getElementById("customer_reg").value = "";
    document.getElementById("customer_made").value = "";
    document.getElementById("customer_mileage").value = "";
    document.getElementById("customer_vin").value = "";
    document.getElementById("customer_color").value = "";
    document.getElementById("customer_chasis").value = "";
    
    // Refresh car dropdown to show only this customer's cars
    populateCarSelect();
  } else {
    document.getElementById("customer_name").value = "";
    document.getElementById("customer_address").value = "";
    document.getElementById("customer_phone").value = "";
    document.getElementById("customer-details").style.display = "none";

    // Clear car input and details
    const carSelect = document.getElementById("car-select");
    if (carSelect) {
      carSelect.value = "";
    }
    document.getElementById("car-details").style.display = "none";
    
    // Clear car details fields
    document.getElementById("customer_reg").value = "";
    document.getElementById("customer_made").value = "";
    document.getElementById("customer_mileage").value = "";
    document.getElementById("customer_vin").value = "";
    document.getElementById("customer_color").value = "";
    document.getElementById("customer_chasis").value = "";
    
    // Refresh car dropdown (will show "Please select a customer first" message)
    populateCarSelect();
  }
}

// Handle car selection change
export function handleCarChange(carId) {
  state.selectedCarId = carId;

  if (carId) {
    const car = state.cars.find((c) => c.id === carId);
    if (car) {
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
    state.selectedCarId = null;
    document.getElementById("customer_reg").value = "";
    document.getElementById("customer_made").value = "";
    document.getElementById("customer_mileage").value = "";
    document.getElementById("customer_vin").value = "";
    document.getElementById("customer_color").value = "";
    document.getElementById("customer_chasis").value = "";
    document.getElementById("car-details").style.display = "none";
  }
}

// Make functions globally available
window.handleCustomerChange = handleCustomerChange;
window.handleCarChange = handleCarChange;

// ===== ITEM/LABOUR MANAGEMENT =====

// Add item or labour to the invoice
export function addItem(type) {
  state.counter++;
  const itemContainer = document.createElement("div");
  itemContainer.classList.add("item");

  let htmlContent = `<p><i>${state.counter}:</i></p>`;

  if (type === "item") {
    htmlContent += `
      <div class="searchable-dropdown">
        <input type="text" class="product-name input-fields" placeholder="Search Part/Lubricant..." required readonly>
        <div class="dropdown-options" style="display: none;">
          <div class="dropdown-option">Type to search for items...</div>
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
    setupItemDropdown(itemContainer);
  } else {
    itemContainer.querySelector(".price").addEventListener("input", updateTotal);
  }

  itemContainer.querySelector(".delete-btn").addEventListener("click", function () {
    itemContainer.remove();
    updateTotal();
    updateBalance();
    state.counter--;
  });

  const inputs = itemContainer.querySelectorAll("input");
  inputs[inputs.length - 1].addEventListener("keydown", function (e) {
    if (e.key === "Tab" && !e.shiftKey) {
      e.preventDefault();
      addItem(type);
      const newInputs = document
        .querySelectorAll(".item")
        [document.querySelectorAll(".item").length - 1].querySelectorAll("input");
      newInputs[0].focus();
    }
  });
}

// Set up item dropdown with inventory search
function setupItemDropdown(itemContainer) {
  const productInput = itemContainer.querySelector(".product-name");
  const dropdownOptions = itemContainer.querySelector(".dropdown-options");
  const priceInput = itemContainer.querySelector(".price");

  productInput.addEventListener("click", function () {
    dropdownOptions.style.display = "block";
    this.readOnly = false;
    this.focus();
  });

  productInput.addEventListener("focus", function () {
    if (this.value.trim().length >= 2) {
      dropdownOptions.style.display = "block";
      this.readOnly = false;
      searchInventoryItemsForInvoice(itemContainer, this.value.trim());
    }
  });

  let searchTimeout;
  productInput.addEventListener("input", function () {
    const searchTerm = this.value.trim();

    if (searchTimeout) {
      clearTimeout(searchTimeout);
    }

    if (!searchTerm) {
      dropdownOptions.style.display = "none";
      return;
    }

    if (searchTerm.length < 2) {
      return;
    }

    searchTimeout = setTimeout(async () => {
      await searchInventoryItemsForInvoice(itemContainer, searchTerm);
    }, 300);
  });

  dropdownOptions.addEventListener("click", function (e) {
    if (e.target.classList.contains("dropdown-option")) {
      const selectedValue = e.target.getAttribute("data-value");
      const selectedPrice = e.target.getAttribute("data-price");
      const selectedPartNumber = e.target.getAttribute("data-part-number");

      productInput.value = selectedValue;
      priceInput.value = selectedPrice;

      const partNumberInput = itemContainer.querySelector(".part-number");
      if (partNumberInput) {
        partNumberInput.value = selectedPartNumber || "";
      }

      dropdownOptions.style.display = "none";
      productInput.readOnly = true;
      updateTotal();
    }
  });

  document.addEventListener("click", function (e) {
    if (!itemContainer.contains(e.target)) {
      dropdownOptions.style.display = "none";
      productInput.readOnly = true;
    }
  });

  itemContainer.querySelector(".quantity").addEventListener("input", updateTotal);
  itemContainer.querySelector(".price").addEventListener("input", updateTotal);


  // Function to refresh dropdown options
  const refreshDropdownOptions = () => {
    const items = Array.isArray(state.inventoryItems) ? state.inventoryItems : [];
    const dropdownOpts = itemContainer.querySelector(".dropdown-options");

    if (dropdownOpts) {
      if (items.length > 0) {
        dropdownOpts.innerHTML = items
          .map(
            (item) =>
              `<div class="dropdown-option" data-value="${item.name}" data-price="${item.price}" data-part-number="${item.part_number || ""}">${inventoryOptionLabel(item)}</div>`
          )
          .join("");
      } else {
        dropdownOpts.innerHTML =
          '<div class="dropdown-option" style="color: #666;">No inventory items available</div>';
      }
    }
  };

  itemContainer.refreshDropdownOptions = refreshDropdownOptions;
}

// Make addItem globally available
window.addItem = addItem;

// ===== CALCULATIONS =====

// Update total cost
export function updateTotal() {
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

  document.getElementById("total-amount").innerText = `Net Total: ${total.toFixed(2)} PKR`;
  updateBalance();
  updateTaxDisplay();
}

// Update balance
export function updateBalance() {
  const totalText = document.getElementById("total-amount").innerText;
  const total = parseFloat(totalText.replace(/[^\d.-]/g, ""));
  const advance = parseFloat(document.querySelector(".advance").value) || 0;
  const discount = parseFloat(document.getElementById("discount").value) || 0;
  const balance = total - advance - discount;

  document.getElementById("total-balance").innerText = `Balance: ${balance.toFixed(2)} PKR`;
}

// Update tax display
export function updateTaxDisplay() {
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

// Make functions globally available
window.updateTotal = updateTotal;
window.updateBalance = updateBalance;
window.updateTaxDisplay = updateTaxDisplay;

// ===== DOCUMENT TYPE TOGGLE =====

// Update document type toggle (Quote/Invoice mode)
export function updateDocumentTypeToggle() {
  const toggle = document.getElementById("direct-invoice-toggle");
  const descriptionText = document.getElementById("toggle-description-text");
  const submitButtons = document.querySelectorAll(".wide-btn-submit");
  const inventoryDeductionSection = document.querySelector(".inventory-deduction-section");

  if (toggle.checked) {
    // Direct Invoice Mode
    descriptionText.textContent = "Direct Invoice Mode: Generate invoices immediately";
    descriptionText.style.color = "#28a745";

    if (inventoryDeductionSection) {
      inventoryDeductionSection.style.display = "block";
    }

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
    descriptionText.textContent = "Quote Mode: Generate quotes for customer approval";
    descriptionText.style.color = "#6c757d";

    if (inventoryDeductionSection) {
      inventoryDeductionSection.style.display = "none";
    }

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

window.updateDocumentTypeToggle = updateDocumentTypeToggle;

// ===== INVENTORY SEARCH =====

// Search inventory items for invoice
/**
 * How a stock item reads in a picker.
 *
 * The manufacturer code is what actually identifies a part - after the codes
 * were moved out of the names, thirteen different filters are all called
 * "BMW OIL FILTER", so the name alone cannot tell them apart.
 */
function inventoryOptionLabel(item) {
  const code = (item.manufacturer_part_number || "").trim();
  const bits = [item.name];
  if (code) bits.push(code);
  // 116 items carry no price, and "PKR 0.00" reads as broken rather than blank.
  const price = Number(item.price || 0);
  if (price > 0) bits.push(`PKR ${price.toFixed(2)}`);
  return bits.join("  \u00b7  ");
}

export async function searchInventoryItemsForInvoice(itemContainer, searchTerm) {
  const dropdownOptions = itemContainer.querySelector(".dropdown-options");
  if (!dropdownOptions) return;

  try {
    dropdownOptions.innerHTML = '<div class="dropdown-option">Searching...</div>';
    dropdownOptions.style.display = "block";

    const result = await APIHelper.get(
      `/api/inventory/search?q=${encodeURIComponent(searchTerm)}`
    );

    if (result && result.results) {
      populateInvoiceDropdownOptions(dropdownOptions, result.results);
    } else {
      dropdownOptions.innerHTML = '<div class="dropdown-option">No items found</div>';
    }
  } catch (error) {
    console.error("Error searching inventory:", error);
    dropdownOptions.innerHTML = '<div class="dropdown-option">Error searching items</div>';
  }
}

// Populate invoice dropdown options from search results
export function populateInvoiceDropdownOptions(dropdownOptions, items) {
  dropdownOptions.innerHTML = "";

  if (items.length === 0) {
    dropdownOptions.innerHTML = '<div class="dropdown-option">No items found</div>';
    return;
  }

  items.forEach((item) => {
    const option = document.createElement("div");
    option.className = "dropdown-option";
    option.setAttribute("data-value", item.name);
    option.setAttribute("data-price", item.price);
    option.setAttribute("data-part-number", item.part_number || "");
    option.textContent = inventoryOptionLabel(item);
    dropdownOptions.appendChild(option);
  });
}

// ===== INVENTORY DEDUCTION =====

// Handle inventory deduction button click
export async function handleInventoryDeduction() {
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
      const errorFn = typeof showError === 'function' ? showError : alert;
      errorFn("No items found to deduct from inventory.");
      return;
    }

    const stockCheckResult = await APIHelper.post("/api/inventory/check-stock", { items: items });
    if (!stockCheckResult) return;

    const { insufficient_items, available_items } = stockCheckResult;

    const itemsWithInsufficientStock = available_items.filter((item) => item.insufficient_stock);

    if (itemsWithInsufficientStock.length > 0 || insufficient_items.length > 0) {
      let warningMessage = "Inventory Status:\n\n";

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
          const partNumberText = item.part_number ? ` (${item.part_number})` : "";
          warningMessage += `• ${item.product_name}${partNumberText}: Required ${item.quantity}\n`;
        });
        warningMessage += "\n";
      }

      const itemsWithSufficientStock = available_items.filter((item) => !item.insufficient_stock);
      if (itemsWithSufficientStock.length > 0) {
        warningMessage += "Items with sufficient stock:\n";
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
        "WARNING: Proceeding will attempt to deduct ALL items. Items with insufficient stock will go negative, and items not found will be skipped.\n\nDo you want to proceed?";

      const proceed = confirm(warningMessage);
      if (!proceed) {
        return;
      }
    }

    const deductionResult = await APIHelper.post("/api/inventory/deduct-items", { items: items });
    if (!deductionResult) return;

    let successMessage = "Inventory deduction completed!\n\n";

    if (deductionResult.deducted_items.length > 0) {
      successMessage += "Successfully deducted:\n";
      deductionResult.deducted_items.forEach((item) => {
        const partNumberText = item.inventory_part_number
          ? ` (${item.inventory_part_number})`
          : item.part_number
          ? ` (${item.part_number})`
          : "";
        const newQuantityText =
          item.new_quantity !== undefined ? ` (New stock: ${item.new_quantity})` : "";
        successMessage += `• ${item.product_name}${partNumberText}: ${item.quantity} units${newQuantityText}\n`;
      });
    }

    if (deductionResult.failed_items && deductionResult.failed_items.length > 0) {
      successMessage += "\nCould not deduct:\n";
      deductionResult.failed_items.forEach((item) => {
        const partNumberText = item.part_number ? ` (${item.part_number})` : "";
        successMessage += `• ${item.product_name}${partNumberText}: ${item.reason}\n`;
      });
    }

    alert(successMessage);
  } catch (error) {
    console.error("Error handling inventory deduction:", error);
    alert(`Error during inventory deduction: ${error.message}`);
  }
}

// ===== MODAL FUNCTIONS =====

// Customer Modal Functions
export function openCustomerModal() {
  // Reset modal to create mode
  window.editingCustomerId = null;
  const modalTitle = document.getElementById("customer-modal-title");
  if (modalTitle) {
    modalTitle.textContent = "Add Customer";
  }
  const form = document.getElementById("customer-form");
  if (form) {
    form.reset();
  }
  CustomerCarUtils.openCustomerModal("customer-modal");
}

export function openEditCustomerModal() {
  if (!state.selectedCustomerId) {
    alert("Please select a customer first.");
    return;
  }

  const customer = state.customers.find((c) => c.id === state.selectedCustomerId);
  if (!customer) {
    alert("Customer not found.");
    return;
  }

  // Set modal to edit mode
  window.editingCustomerId = state.selectedCustomerId;
  const modalTitle = document.getElementById("customer-modal-title");
  if (modalTitle) {
    modalTitle.textContent = "Edit Customer";
  }

  // Populate form with customer data
  document.getElementById("modal-customer-name").value = customer.name || "";
  document.getElementById("modal-customer-phone").value = customer.phone || "";
  document.getElementById("modal-customer-address").value = customer.address || "";

  CustomerCarUtils.openCustomerModal("customer-modal");
}

export function closeCustomerModal() {
  CustomerCarUtils.closeCustomerModal("customer-modal", "customer-form");
  window.editingCustomerId = null;
}

export async function handleCustomerSubmit(e) {
  e.preventDefault();

  const customerData = {
    name: document.getElementById("modal-customer-name").value.trim(),
    phone: document.getElementById("modal-customer-phone").value.trim(),
    address: document.getElementById("modal-customer-address").value.trim(),
  };

  try {
    let updatedCustomer;
    const isEditing = window.editingCustomerId;

    if (isEditing) {
      // Update existing customer
      updatedCustomer = await CustomerCarUtils.updateCustomer(window.editingCustomerId, customerData);
      
      if (typeof showNotification === "function") {
        showNotification("Customer updated successfully!", "success");
      } else {
        alert("Customer updated successfully!");
      }
    } else {
      // Create new customer
      updatedCustomer = await CustomerCarUtils.createCustomer(customerData);
      
      if (typeof showNotification === "function") {
        showNotification("Customer created successfully!", "success");
      } else {
        alert("Customer created successfully!");
      }
    }

    closeCustomerModal();
    await loadCustomers();

    // Update form fields with new/updated data
    document.getElementById("customer_name").value = updatedCustomer.name;
    document.getElementById("customer_address").value = updatedCustomer.address;
    document.getElementById("customer_phone").value = updatedCustomer.phone;

    const customerDisplayText = `${updatedCustomer.name} - ${updatedCustomer.phone}`;
    document.getElementById("customer-select").value = customerDisplayText;

    // Update selected customer ID if it changed
    if (isEditing && state.selectedCustomerId === window.editingCustomerId) {
      // Customer already selected, just refresh
      handleCustomerChange(updatedCustomer.id);
    } else if (!isEditing) {
      // New customer, select it
      handleCustomerChange(updatedCustomer.id);
    }
  } catch (error) {
    const errorMsg = error.message || (window.editingCustomerId ? "Failed to update customer" : "Failed to create customer");
    if (typeof showNotification === "function") {
      showNotification(errorMsg, "error");
    } else {
      alert("Error: " + errorMsg);
    }
  }
}

// Car Modal Functions
export function openCarModal() {
  // Reset modal to create mode
  window.editingCarId = null;
  const modalTitle = document.getElementById("car-modal-title");
  if (modalTitle) {
    modalTitle.textContent = "Add Car";
  }

  const form = document.getElementById("car-form");
  const customerSelect = document.getElementById("modal-car-customer");

  customerSelect.innerHTML = '<option value="">Select Customer</option>';
  state.customers.forEach((customer) => {
    const option = document.createElement("option");
    option.value = customer.id;
    option.textContent = `${customer.name} - ${customer.phone}`;
    customerSelect.appendChild(option);
  });

  // Auto-select customer if one is already selected in the form
  if (state.selectedCustomerId) {
    customerSelect.value = state.selectedCustomerId;
  }

  form.reset();
  
  // Re-set the customer selection after reset (reset clears it)
  if (state.selectedCustomerId) {
    customerSelect.value = state.selectedCustomerId;
  }
  
  CustomerCarUtils.openCarModal("car-modal");
}

export function openEditCarModal() {
  if (!state.selectedCarId) {
    alert("Please select a car first.");
    return;
  }

  const car = state.cars.find((c) => c.id === state.selectedCarId);
  if (!car) {
    alert("Car not found.");
    return;
  }

  // Set modal to edit mode
  window.editingCarId = state.selectedCarId;
  const modalTitle = document.getElementById("car-modal-title");
  if (modalTitle) {
    modalTitle.textContent = "Edit Car";
  }

  const customerSelect = document.getElementById("modal-car-customer");
  customerSelect.innerHTML = '<option value="">Select Customer</option>';
  state.customers.forEach((customer) => {
    const option = document.createElement("option");
    option.value = customer.id;
    option.textContent = `${customer.name} - ${customer.phone}`;
    customerSelect.appendChild(option);
  });

  // Populate form with car data
  customerSelect.value = car.customer_id || "";
  document.getElementById("modal-car-make").value = car.make || "";
  document.getElementById("modal-car-model").value = car.model || "";
  document.getElementById("modal-car-plate").value = car.plate_no || "";
  document.getElementById("modal-car-mileage").value = car.mileage || "";
  document.getElementById("modal-car-vin").value = car.vin || "";
  document.getElementById("modal-car-color").value = car.color || "";
  document.getElementById("modal-car-chasis").value = car.chasis_no || "";

  CustomerCarUtils.openCarModal("car-modal");
}

export function closeCarModal() {
  CustomerCarUtils.closeCarModal("car-modal", "car-form");
  window.editingCarId = null;
}

export async function handleCarSubmit(e) {
  e.preventDefault();

  const carData = {
    customer_id: parseInt(document.getElementById("modal-car-customer").value) || null,
    make: document.getElementById("modal-car-make").value.trim(),
    model: document.getElementById("modal-car-model").value.trim(),
    plate_no: document.getElementById("modal-car-plate").value.trim(),
    mileage: document.getElementById("modal-car-mileage").value.trim(),
    vin: document.getElementById("modal-car-vin").value.trim(),
    color: document.getElementById("modal-car-color").value.trim(),
    chasis_no: document.getElementById("modal-car-chasis").value.trim(),
  };

  try {
    let updatedCar;
    const isEditing = window.editingCarId;

    if (isEditing) {
      // Update existing car
      updatedCar = await CustomerCarUtils.updateCar(window.editingCarId, carData);
      
      if (typeof showNotification === "function") {
        showNotification("Car updated successfully!", "success");
      } else {
        alert("Car updated successfully!");
      }
    } else {
      // Create new car
      updatedCar = await CustomerCarUtils.createCar(carData);
      
      if (typeof showNotification === "function") {
        showNotification("Car created successfully!", "success");
      } else {
        alert("Car created successfully!");
      }
    }

    closeCarModal();
    await loadCars();

    // Update form fields with new/updated data
    document.getElementById("customer_reg").value = updatedCar.plate_no || "";
    document.getElementById("customer_made").value = `${updatedCar.make || ""} ${updatedCar.model || ""}`.trim();
    document.getElementById("customer_mileage").value = updatedCar.mileage || "";
    document.getElementById("customer_vin").value = updatedCar.vin || "";
    document.getElementById("customer_color").value = updatedCar.color || "";
    document.getElementById("customer_chasis").value = updatedCar.chasis_no || "";

    if (state.selectedCustomerId) {
      populateCarSelect();

      // Update car selection if it's the same car or a new car for the selected customer
      if ((isEditing && state.selectedCarId === window.editingCarId) || 
          (!isEditing && updatedCar.customer_id === state.selectedCustomerId)) {
        const carDisplayText = `${updatedCar.make} ${updatedCar.model || ""} - ${updatedCar.plate_no}`.trim();
        document.getElementById("car-select").value = carDisplayText;
        handleCarChange(updatedCar.id);
      }
    }
  } catch (error) {
    const errorMsg = error.message || (window.editingCarId ? "Failed to update car" : "Failed to create car");
    if (typeof showNotification === "function") {
      showNotification(errorMsg, "error");
    } else {
      alert("Error: " + errorMsg);
    }
  }
}

// ===== EVENT LISTENER SETUP =====

// Setup common event listeners used by both create and edit
export function setupCommonEventListeners() {
  // Modal buttons
  document.getElementById("add-customer-btn")?.addEventListener("click", openCustomerModal);
  document.getElementById("add-car-btn")?.addEventListener("click", openCarModal);
  
  // Edit buttons
  document.getElementById("edit-customer-btn")?.addEventListener("click", openEditCustomerModal);
  document.getElementById("edit-car-btn")?.addEventListener("click", openEditCarModal);

  // Modal close buttons
  document.getElementById("close-customer-modal")?.addEventListener("click", closeCustomerModal);
  document.getElementById("close-car-modal")?.addEventListener("click", closeCarModal);
  document.getElementById("cancel-customer")?.addEventListener("click", closeCustomerModal);
  document.getElementById("cancel-car")?.addEventListener("click", closeCarModal);

  // Modal form submissions
  document.getElementById("customer-form")?.addEventListener("submit", handleCustomerSubmit);
  document.getElementById("car-form")?.addEventListener("submit", handleCarSubmit);

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

  // Tax toggle
  document.getElementById("tax-toggle")?.addEventListener("change", updateTaxDisplay);

  // Add item/labour buttons
  document.getElementById("add-labour")?.addEventListener("click", function () {
    addItem("labour");
  });
  document.getElementById("add-item")?.addEventListener("click", function () {
    addItem("item");
  });

  // Advance and discount inputs
  document.querySelector(".advance")?.addEventListener("input", updateBalance);
  document.getElementById("discount")?.addEventListener("input", updateBalance);
}

// ===== FORM DATA COLLECTION =====

// Collect form data for submission
export function collectFormData() {
  const customerName = document.getElementById("customer_name").value.trim();
  const customerAddress = document.getElementById("customer_address").value.trim();
  const customerPhone = document.getElementById("customer_phone").value.trim();
  const customerReg = document.getElementById("customer_reg").value.trim();
  const customerMade = document.getElementById("customer_made").value.trim();
  const customerMileage = document.getElementById("customer_mileage").value.trim();
  const customerVin = document.getElementById("customer_vin").value.trim();
  const customerColor = document.getElementById("customer_color").value || "";
  const customerChasis = document.getElementById("customer_chasis").value || "";
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
    const labourDescription = item.querySelector(".labour-description")?.value.trim();

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

  // Get tax information
  const taxToggle = document.getElementById("tax-toggle");
  const includeTax = taxToggle.checked;
  const taxAmount = includeTax
    ? parseFloat(document.getElementById("tax-amount").textContent.replace(/[^\d.-]/g, ""))
    : 0;

  // Calculate totals
  const totalText = document.getElementById("total-amount").innerText;
  const netTotal = parseFloat(totalText.replace(/[^\d.-]/g, ""));
  const finalBalance = parseFloat(
    document.getElementById("total-balance").innerText.replace(/[^\d.-]/g, "")
  );

  return {
    customer_name: customerName,
    customer_address: customerAddress,
    customer_phone: customerPhone,
    customer_reg_no: customerReg,
    customer_made: customerMade,
    customer_mileage: customerMileage,
    customer_vin: customerVin,
    customer_color: customerColor,
    customer_chasis: customerChasis,
    balance: finalBalance,
    advance: advance,
    discount: discount,
    items: items,
    labours: labours,
    include_tax: includeTax,
    tax_amount: taxAmount,
    net_total: netTotal,
  };
}

// Validate form data before submission
export function validateFormData(formData) {
  const customerSelect = document.getElementById("customer-select");
  const carSelect = document.getElementById("car-select");

  if (!customerSelect.value) {
    alert("Please select a customer.");
    return false;
  }

  if (!carSelect.value) {
    alert("Please select a car.");
    return false;
  }

  if (
    !formData.customer_name ||
    !formData.customer_address ||
    !formData.customer_phone ||
    !formData.customer_reg_no ||
    !formData.customer_made ||
    !formData.customer_mileage ||
    (formData.items.length === 0 && formData.labours.length === 0)
  ) {
    alert(
      "Please ensure all customer and car details are filled, and add at least one valid item or labour."
    );
    return false;
  }

  return true;
}

// Update customer and car records
export async function updateCustomerAndCarRecords(formData) {
  // Update customer record if a customer was selected
  if (state.selectedCustomerId) {
    try {
      const customerData = {
        name: formData.customer_name,
        phone: formData.customer_phone,
        address: formData.customer_address,
      };
      await CustomerCarUtils.updateCustomer(state.selectedCustomerId, customerData);
      console.log("Customer updated successfully");
    } catch (error) {
      console.error("Failed to update customer:", error);
    }
  }

  // Update car record if a car was selected
  if (state.selectedCarId) {
    try {
      const makeModelParts = formData.customer_made.split(" ");
      const make = makeModelParts[0] || "";
      const model = makeModelParts.slice(1).join(" ") || "";

      const carData = {
        make: make,
        model: model,
        plate_no: formData.customer_reg_no,
        mileage: formData.customer_mileage || null,
        vin: formData.customer_vin || null,
        color: formData.customer_color || null,
        chasis_no: formData.customer_chasis || null,
        customer_id: state.selectedCustomerId || null,
      };
      await CustomerCarUtils.updateCar(state.selectedCarId, carData);
      console.log("Car updated successfully");
    } catch (error) {
      console.error("Failed to update car:", error);
    }
  }
}

// Reset form after successful submission
export function resetForm() {
  document.getElementById("invoice-form").reset();
  document.getElementById("total-amount").innerText = "Net Total: 0.00 PKR";
  document.getElementById("total-balance").innerText = "Balance: 0.00 PKR";
  document.getElementById("items-container").innerHTML = "";
  state.counter = 0;

  document.getElementById("customer-details").style.display = "none";
  document.getElementById("car-details").style.display = "none";
  state.selectedCustomerId = null;
  state.selectedCarId = null;
}
