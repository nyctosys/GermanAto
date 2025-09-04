// ===== REPAIR ORDER FORM JAVASCRIPT =====

document.addEventListener("DOMContentLoaded", function () {
  // Set up smart back button logic
  const backBtn = document.getElementById("back-btn");
  const urlParams = new URLSearchParams(window.location.search);
  const fromPage =
    urlParams.get("from") ||
    localStorage.getItem("lastPage") ||
    "pending-quotes";
  const quoteId = urlParams.get("quoteId");
  const repairOrderId = urlParams.get("id");

  // Set back button destination
  if (fromPage === "pending-quotes") {
    backBtn.href = "pending-quotes.html";
  } else if (fromPage === "admin") {
    backBtn.href = "admin.html";
  } else if (fromPage === "invoiceSystem") {
    backBtn.href = "invoiceSystem.html";
  } else if (fromPage === "repair-orders-management") {
    backBtn.href = "repair-orders-management.html";
  } else {
    backBtn.href = "repair-orders-management.html"; // Default fallback
  }

  // Track current page for back button logic
  localStorage.setItem("lastPage", "repair-order");

  // Update page title and description based on source
  if (
    fromPage === "invoice-management" ||
    fromPage === "invoiceSystem" ||
    fromPage === "repair-orders-management"
  ) {
    document.getElementById("page-title").textContent =
      "Create New Repair Order";
    document.getElementById("page-description").textContent =
      "Create a new repair order from scratch";
  }

  // Initialize counters for parts and labour
  let partCounter = 0;
  let labourCounter = 0;

  // Get DOM elements
  const form = document.getElementById("repair-order-form");
  const addPartBtn = document.getElementById("add-part-btn");
  const addLabourBtn = document.getElementById("add-labour-btn");
  const partsContainer = document.getElementById("parts-container");
  const labourContainer = document.getElementById("labour-container");

  // Load quote data if quoteId is provided
  if (quoteId) {
    loadQuoteData(quoteId);
  }

  // Load repair order data if repairOrderId is provided (edit mode)
  if (repairOrderId) {
    loadRepairOrderData(repairOrderId);
  }

  // Add part button event listener
  addPartBtn.addEventListener("click", addPartItem);

  // Add labour button event listener
  addLabourBtn.addEventListener("click", addLabourItem);

  // Form submit event listener
  form.addEventListener("submit", handleFormSubmit);

  // ===== FUNCTIONS =====

  async function loadQuoteData(quoteId) {
    try {
      const response = await fetch(`/api/invoice/${quoteId}`);
      if (response.ok) {
        const quoteData = await response.json();
        populateFormWithQuoteData(quoteData);
      } else {
        console.error("Failed to load quote data");
      }
    } catch (error) {
      console.error("Error loading quote data:", error);
    }
  }

  function populateFormWithQuoteData(quoteData) {
    // Populate customer information
    document.getElementById("customer-name").value =
      quoteData.customer_name || "";
    document.getElementById("customer-phone").value =
      quoteData.customer_phone || "";
    document.getElementById("customer-address").value =
      quoteData.customer_address || "";
    document.getElementById("reg-number").value =
      quoteData.customer_reg_no || "";
    document.getElementById("made").value = quoteData.customer_made || "";
    document.getElementById("mileage").value = quoteData.customer_mileage || "";
    document.getElementById("vin").value = quoteData.customer_vin || "";
    document.getElementById("color").value = quoteData.customer_color || "";
    document.getElementById("chasis").value = quoteData.customer_chasis || "";

    // Populate parts from quote items
    if (quoteData.items && quoteData.items.length > 0) {
      quoteData.items.forEach((item) => {
        addPartItem({
          description: item.product_name,
          part_number: item.part_number || "",
          quantity: item.quantity,
          price: item.price,
          status: "Pending",
        });
      });

      // After adding all parts, set up search functionality and try to match items
      setTimeout(() => {
        matchQuoteItemsToInventory(quoteData.items);
      }, 100);
    }

    // Populate labour from quote labour
    if (quoteData.labours && quoteData.labours.length > 0) {
      quoteData.labours.forEach((labour, index) => {
        addLabourItem({
          description: labour.description,
          rate: labour.price,
          status: "Pending",
        });
      });
    }

    // Update totals
    updateTotals();
  }

  function addPartItem(existingData = null) {
    partCounter++;
    const partItem = document.createElement("div");
    partItem.className = "part-item";
    partItem.id = `part-${partCounter}`;

    partItem.innerHTML = `
            <button type="button" class="remove-btn" onclick="removeItem('part-${partCounter}')">×</button>
            <h4>Part ${partCounter}</h4>
            <div class="part-grid">
                <div class="form-group">
                    <label for="part-inventory-search-${partCounter}">Search Inventory</label>
                    <div class="searchable-dropdown">
                        <input type="text" id="part-inventory-search-${partCounter}" placeholder="Search parts..." class="inventory-search-input">
                        <input type="hidden" id="part-inventory-${partCounter}" name="parts[${partCounter}][inventory_id]">
                        <div class="dropdown-options" id="part-inventory-options-${partCounter}" style="display: none;">
                            <!-- Options will be populated dynamically -->
                        </div>
                    </div>
                </div>
                <div class="form-group">
                    <label for="part-description-${partCounter}">Description *</label>
                    <input type="text" id="part-description-${partCounter}" name="parts[${partCounter}][description]" required>
                </div>
                <div class="form-group">
                    <label for="part-number-${partCounter}">Part Number</label>
                    <input type="text" id="part-number-${partCounter}" name="parts[${partCounter}][part_number]" readonly>
                </div>
                <div class="form-group">
                    <label for="part-quantity-${partCounter}">Quantity *</label>
                    <input type="number" id="part-quantity-${partCounter}" name="parts[${partCounter}][quantity]" min="1" step="1" required>
                </div>
                <div class="form-group">
                    <label for="part-price-${partCounter}">Price (PKR) *</label>
                    <input type="number" id="part-price-${partCounter}" name="parts[${partCounter}][price]" min="0" step="0.01" required>
                </div>
                <div class="form-group">
                    <label for="part-status-${partCounter}">Status</label>
                    <select id="part-status-${partCounter}" name="parts[${partCounter}][status]">
                        <option value="Pending">Pending</option>
                        <option value="Ordered">Ordered</option>
                        <option value="Received">Received</option>
                        <option value="Installed">Installed</option>
                    </select>
                </div>
            </div>
        `;

    partsContainer.appendChild(partItem);

    // Set up search functionality for this new item
    setupInventorySearch(partCounter);

    // Populate with existing data if provided
    if (existingData) {
      document.getElementById(`part-description-${partCounter}`).value =
        existingData.description || "";
      document.getElementById(`part-number-${partCounter}`).value =
        existingData.part_number || "";
      document.getElementById(`part-quantity-${partCounter}`).value =
        existingData.quantity || "";
      document.getElementById(`part-price-${partCounter}`).value =
        existingData.price || "";
      document.getElementById(`part-status-${partCounter}`).value =
        existingData.status || "Pending";

      // If inventory_id is provided, set it in the dropdown
      if (existingData.inventory_id) {
        const dropdown = document.getElementById(
          `part-inventory-${partCounter}`
        );
        if (dropdown) {
          dropdown.value = existingData.inventory_id;
        }
      }
    }

    // Add event listeners for price calculation
    const quantityInput = document.getElementById(
      `part-quantity-${partCounter}`
    );
    const priceInput = document.getElementById(`part-price-${partCounter}`);

    quantityInput.addEventListener("input", updateTotals);
    priceInput.addEventListener("input", updateTotals);
  }

  function addLabourItem(existingData = null) {
    labourCounter++;
    const labourItem = document.createElement("div");
    labourItem.className = "labour-item";
    labourItem.id = `labour-${labourCounter}`;

    labourItem.innerHTML = `
            <button type="button" class="remove-btn" onclick="removeItem('labour-${labourCounter}')">×</button>
            <h4>Labour Task ${labourCounter}</h4>
            <div class="labour-grid">
                <div class="form-group">
                    <label for="labour-description-${labourCounter}">Description *</label>
                    <input type="text" id="labour-description-${labourCounter}" name="labour[${labourCounter}][description]" required>
                </div>

                <div class="form-group">
                    <label for="labour-rate-${labourCounter}">Rate (PKR) *</label>
                    <input type="number" id="labour-rate-${labourCounter}" name="labour[${labourCounter}][rate]" min="0" step="0.01" required>
                </div>
                <div class="form-group">
                    <label for="labour-status-${labourCounter}">Status</label>
                    <select id="labour-status-${labourCounter}" name="labour[${labourCounter}][status]">
                        <option value="Pending">Pending</option>
                        <option value="In Progress">In Progress</option>
                        <option value="Completed">Completed</option>
                    </select>
                </div>
            </div>
        `;

    labourContainer.appendChild(labourItem);

    // Populate with existing data if provided
    if (existingData) {
      document.getElementById(`labour-description-${labourCounter}`).value =
        existingData.description || "";

      document.getElementById(`labour-rate-${labourCounter}`).value =
        existingData.rate || "";
      document.getElementById(`labour-status-${labourCounter}`).value =
        existingData.status || "Pending";
    }

    // Add event listeners for price calculation
    const rateInput = document.getElementById(`labour-rate-${labourCounter}`);

    rateInput.addEventListener("input", updateTotals);
  }

  function removeItem(itemId) {
    const item = document.getElementById(itemId);
    if (item) {
      item.remove();
      updateTotals();
    }
  }

  function updateTotals() {
    let partsTotal = 0;
    let labourTotal = 0;

    // Calculate parts total
    for (let i = 1; i <= partCounter; i++) {
      const quantityElement = document.getElementById(`part-quantity-${i}`);
      const priceElement = document.getElementById(`part-price-${i}`);

      if (quantityElement && priceElement) {
        const quantity = parseFloat(quantityElement.value) || 0;
        const price = parseFloat(priceElement.value) || 0;
        partsTotal += quantity * price;
      }
    }

    // Calculate labour total
    for (let i = 1; i <= labourCounter; i++) {
      const rateElement = document.getElementById(`labour-rate-${i}`);

      if (rateElement) {
        const rate = parseFloat(rateElement.value) || 0;
        labourTotal += rate;
      }
    }

    // Update display
    document.getElementById("parts-total").textContent = `${partsTotal.toFixed(
      2
    )} PKR`;
    document.getElementById(
      "labour-total"
    ).textContent = `${labourTotal.toFixed(2)} PKR`;
    document.getElementById("total-estimate").textContent = `${(
      partsTotal + labourTotal
    ).toFixed(2)} PKR`;
  }

  async function loadRepairOrderData(repairOrderId) {
    try {
      const response = await fetch(`/api/repair-orders/${repairOrderId}`);
      if (response.ok) {
        const repairOrderData = await response.json();
        setEditMode();

        // Ensure inventory items are loaded before populating form
        if (inventoryItems.length === 0) {
          loadInventoryItems();
        }

        // Small delay to ensure form is ready
        setTimeout(() => {
          populateFormWithRepairOrderData(repairOrderData);
        }, 100);
      } else {
        console.error("Failed to load repair order data");
        alert("Failed to load repair order data");
      }
    } catch (error) {
      console.error("Error loading repair order data:", error);
      alert("Error loading repair order data");
    }
  }

  function populateFormWithRepairOrderData(repairOrderData) {
    // Populate customer information (read-only in edit mode)
    const customerNameField = document.getElementById("customer-name");
    const customerPhoneField = document.getElementById("customer-phone");
    const customerAddressField = document.getElementById("customer-address");
    const regNumberField = document.getElementById("reg-number");
    const madeField = document.getElementById("made");
    const mileageField = document.getElementById("mileage");
    const vinField = document.getElementById("vin");
    const colorField = document.getElementById("color");
    const chasisField = document.getElementById("chasis");

    if (customerNameField)
      customerNameField.value = repairOrderData.customer_name || "";
    if (customerPhoneField)
      customerPhoneField.value = repairOrderData.customer_phone || "";
    if (customerAddressField)
      customerAddressField.value = repairOrderData.customer_address || "";
    if (regNumberField)
      regNumberField.value = repairOrderData.customer_reg_no || "";
    if (madeField) madeField.value = repairOrderData.customer_made || "";
    if (mileageField)
      mileageField.value = repairOrderData.customer_mileage || "";
    if (vinField) vinField.value = repairOrderData.customer_vin || "";
    if (colorField) colorField.value = repairOrderData.customer_color || "";
    if (chasisField) chasisField.value = repairOrderData.customer_chasis || "";

    // Populate problem description
    const problemDescField = document.getElementById("problem-description");
    if (problemDescField)
      problemDescField.value = repairOrderData.problem_description || "";

    // Populate worker name
    const workerNameField = document.getElementById("worker-name");
    if (workerNameField)
      workerNameField.value = repairOrderData.worker_name || "";

    // Populate parts
    if (repairOrderData.parts && repairOrderData.parts.length > 0) {
      repairOrderData.parts.forEach((part) => {
        addPartItem({
          description: part.description,
          part_number: part.part_number || "",
          quantity: part.quantity,
          price: part.price,
          status: part.status || "Pending",
          inventory_id: part.inventory_id || null,
        });
      });

      // After adding all parts, set up search functionality and try to match items
      setTimeout(() => {
        matchRepairOrderPartsToInventory(repairOrderData.parts);
      }, 200); // Increased timeout to ensure search is ready
    }

    // Populate labour
    if (repairOrderData.labour && repairOrderData.labour.length > 0) {
      repairOrderData.labour.forEach((labour) => {
        addLabourItem({
          description: labour.description,
          rate: labour.rate,
          status: labour.status || "Pending",
        });
      });
    }

    // Update totals
    updateTotals();
  }

  function setEditMode() {
    // Update page title and description
    document.getElementById("page-title").textContent = "Edit Repair Order";
    document.getElementById("page-description").textContent =
      "Update repair order details";
    document.getElementById("submit-btn").textContent = "Update Repair Order";

    // Disable customer and vehicle information fields
    const customerFields = [
      "customer-name",
      "customer-phone",
      "customer-address",
      "reg-number",
      "made",
      "mileage",
      "vin",
      "color",
      "chasis",
    ];

    customerFields.forEach((fieldId) => {
      const field = document.getElementById(fieldId);
      if (field) {
        field.disabled = true;
        field.classList.add("disabled-field");
      }
    });
  }

  async function handleFormSubmit(event) {
    event.preventDefault();

    // Validate form
    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }

    // Collect form data
    const formData = new FormData(form);
    const repairOrderData = {
      customer_name: formData.get("customer_name"),
      customer_phone: formData.get("customer_phone"),
      customer_address: formData.get("customer_address"),
      customer_reg_no: formData.get("customer_reg_no"),
      customer_made: formData.get("customer_made"),
      customer_mileage: formData.get("customer_mileage"),
      customer_vin: formData.get("customer_vin"),
      customer_color: formData.get("customer_color"),
      customer_chasis: formData.get("customer_chasis"),
      problem_description: formData.get("problem_description"),
      worker_name: formData.get("worker_name"),
      parts: [],
      labour: [],
    };

    // If in edit mode, preserve original values for disabled fields
    if (repairOrderId) {
      // Get the original repair order data from the page
      repairOrderData.customer_name =
        document.getElementById("customer-name").value ||
        repairOrderData.customer_name;
      repairOrderData.customer_phone =
        document.getElementById("customer-phone").value ||
        repairOrderData.customer_phone;
      repairOrderData.customer_address =
        document.getElementById("customer-address").value ||
        repairOrderData.customer_address;
      repairOrderData.customer_reg_no =
        document.getElementById("reg-number").value ||
        repairOrderData.customer_reg_no;
      repairOrderData.customer_made =
        document.getElementById("made").value || repairOrderData.customer_made;
      repairOrderData.customer_mileage =
        document.getElementById("mileage").value ||
        repairOrderData.customer_mileage;
      repairOrderData.customer_vin =
        document.getElementById("vin").value || repairOrderData.customer_vin;
      repairOrderData.customer_color =
        document.getElementById("color").value ||
        repairOrderData.customer_color;
      repairOrderData.customer_chasis =
        document.getElementById("chasis").value ||
        repairOrderData.customer_chasis;
    }

    // Collect parts data
    for (let i = 1; i <= partCounter; i++) {
      const descriptionElement = document.getElementById(
        `part-description-${i}`
      );
      if (descriptionElement && descriptionElement.value.trim()) {
        const partData = {
          inventory_id:
            document.getElementById(`part-inventory-${i}`).value || null,
          description: descriptionElement.value,
          part_number: document.getElementById(`part-number-${i}`).value,
          quantity:
            parseFloat(document.getElementById(`part-quantity-${i}`).value) ||
            0,
          price:
            parseFloat(document.getElementById(`part-price-${i}`).value) || 0,
          status: document.getElementById(`part-status-${i}`).value,
        };
        repairOrderData.parts.push(partData);
      }
    }

    // Collect labour data
    for (let i = 1; i <= labourCounter; i++) {
      const descriptionElement = document.getElementById(
        `labour-description-${i}`
      );
      if (descriptionElement && descriptionElement.value.trim()) {
        const labourData = {
          description: descriptionElement.value,
          rate:
            parseFloat(document.getElementById(`labour-rate-${i}`).value) || 0,
          status: document.getElementById(`labour-status-${i}`).value,
        };
        repairOrderData.labour.push(labourData);
      }
    }

    // Calculate totals
    const partsTotal = repairOrderData.parts.reduce(
      (sum, part) => sum + part.quantity * part.price,
      0
    );
    const labourTotal = repairOrderData.labour.reduce(
      (sum, labour) => sum + labour.rate,
      0
    );

    repairOrderData.parts_total = partsTotal;
    repairOrderData.labour_total = labourTotal;
    repairOrderData.total_estimate = partsTotal + labourTotal;

    try {
      let response;
      let result;

      if (repairOrderId) {
        // Update existing repair order
        response = await fetch(`/api/repair-orders/${repairOrderId}`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(repairOrderData),
        });
        result = await response.json();

        if (response.ok) {
          // Check for inventory warnings
          if (
            result.inventory_warnings &&
            result.inventory_warnings.length > 0
          ) {
            const warningMessage =
              "Repair order updated successfully!\n\nInventory warnings:\n" +
              result.inventory_warnings.join("\n");
            alert(warningMessage);
          } else {
            alert("Repair order updated successfully!");
          }
          // Redirect back to repair orders management
          window.location.href = "repair-orders-management.html";
        } else {
          // Check for inventory errors
          if (result.inventory_errors && result.inventory_errors.length > 0) {
            const errorMessage =
              "Failed to update repair order due to inventory issues:\n" +
              result.inventory_errors.join("\n");
            alert(errorMessage);
          } else {
            alert(
              "Error: " + (result.error || "Failed to update repair order")
            );
          }
        }
      } else {
        // Create new repair order
        response = await fetch("/api/repair-orders", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(repairOrderData),
        });
        result = await response.json();

        if (response.ok) {
          // Check for inventory warnings
          if (
            result.inventory_warnings &&
            result.inventory_warnings.length > 0
          ) {
            const warningMessage =
              "Repair order created successfully!\n\nInventory warnings:\n" +
              result.inventory_warnings.join("\n");
            alert(warningMessage);
          }

          // Store repair order data for template
          sessionStorage.setItem(
            "repairOrderData",
            JSON.stringify(repairOrderData)
          );
          sessionStorage.setItem("repairOrderId", result.repair_order_id);

          // Redirect to repair order template
          window.location.href = "repair-order-template.html?from=repair-order";
        } else {
          // Check for inventory errors
          if (result.inventory_errors && result.inventory_errors.length > 0) {
            const errorMessage =
              "Failed to create repair order due to inventory issues:\n" +
              result.inventory_errors.join("\n");
            alert(errorMessage);
          } else {
            alert(
              "Error: " + (result.error || "Failed to create repair order")
            );
          }
        }
      }
    } catch (error) {
      console.error("Error saving repair order:", error);
      alert("Error: Failed to save repair order. Please try again.");
    }
  }

  // Make removeItem function globally accessible
  window.removeItem = removeItem;

  // Global inventory data
  let inventoryItems = [];

  // Load inventory items for dropdowns
  async function loadInventoryItems() {
    try {
      const response = await fetch("/api/inventory");
      if (response.ok) {
        inventoryItems = await response.json();
        populateInventoryDropdowns();
      } else {
        console.error("Failed to load inventory items");
      }
    } catch (error) {
      console.error("Error loading inventory items:", error);
    }
  }

  // Populate all inventory dropdowns
  function populateInventoryDropdowns() {
    const dropdowns = document.querySelectorAll(
      'select[id^="part-inventory-"]'
    );
    dropdowns.forEach((dropdown) => {
      populateInventoryDropdown(dropdown);
    });
  }

  // Populate a single inventory dropdown
  function populateInventoryDropdown(dropdown) {
    // Clear existing options except the first one
    dropdown.innerHTML =
      '<option value="">-- Select Inventory Item --</option>';

    // Add inventory items
    inventoryItems.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = `${item.part_number} - ${item.name} (Stock: ${item.quantity})`;
      option.dataset.item = JSON.stringify(item);
      dropdown.appendChild(option);
    });
  }

  // Handle inventory selection
  window.onInventorySelect = function (partCounter) {
    const dropdown = document.getElementById(`part-inventory-${partCounter}`);
    const selectedOption = dropdown.options[dropdown.selectedIndex];

    if (selectedOption.value) {
      const item = JSON.parse(selectedOption.dataset.item);

      // Populate form fields with inventory item data
      document.getElementById(`part-description-${partCounter}`).value =
        item.name;
      document.getElementById(`part-number-${partCounter}`).value =
        item.part_number;
      document.getElementById(`part-price-${partCounter}`).value = item.price;

      // Preserve existing quantity if it's already set (for edit mode)
      const quantityField = document.getElementById(
        `part-quantity-${partCounter}`
      );
      if (!quantityField.value || quantityField.value === "0") {
        // Only set quantity to 1 if it's not already set
        quantityField.value = "1";
      }

      // Update totals
      updateTotals();
    } else {
      // Clear form fields if no item selected
      document.getElementById(`part-description-${partCounter}`).value = "";
      document.getElementById(`part-number-${partCounter}`).value = "";
      document.getElementById(`part-price-${partCounter}`).value = "";
      updateTotals();
    }
  };

  // Match quote items to inventory items
  function matchQuoteItemsToInventory(quoteItems) {
    quoteItems.forEach((quoteItem, index) => {
      const partCounter = index + 1;
      const searchInput = document.getElementById(
        `part-inventory-search-${partCounter}`
      );
      const hiddenInput = document.getElementById(
        `part-inventory-${partCounter}`
      );

      if (searchInput && hiddenInput && quoteItem.part_number) {
        // Try to find matching inventory item by part number
        const matchingItem = inventoryItems.find(
          (item) => item.part_number === quoteItem.part_number
        );

        if (matchingItem) {
          searchInput.value = `${matchingItem.part_number} - ${matchingItem.name}`;
          hiddenInput.value = matchingItem.id;
        }
      }
    });
  }

  // Match repair order parts to inventory items
  function matchRepairOrderPartsToInventory(parts) {
    parts.forEach((part, index) => {
      const partCounter = index + 1;
      const searchInput = document.getElementById(
        `part-inventory-search-${partCounter}`
      );
      const hiddenInput = document.getElementById(
        `part-inventory-${partCounter}`
      );

      if (!searchInput || !hiddenInput) {
        return;
      }

      if (part.inventory_id) {
        // Find the inventory item
        const item = inventoryItems.find(
          (item) => item.id == part.inventory_id
        );
        if (item) {
          // Set the search input value
          searchInput.value = `${item.part_number} - ${item.name}`;
          hiddenInput.value = item.id;
        }
      } else if (part.part_number) {
        // Try to find matching inventory item by part number
        const matchingItem = inventoryItems.find(
          (item) => item.part_number === part.part_number
        );

        if (matchingItem) {
          searchInput.value = `${matchingItem.part_number} - ${matchingItem.name}`;
          hiddenInput.value = matchingItem.id;
        }
      }
    });
  }

  // Populate inventory data for a part without overriding quantity
  function populateInventoryDataForPart(
    partCounter,
    inventoryId,
    existingPartData
  ) {
    const item = inventoryItems.find((item) => item.id == inventoryId);
    if (item) {
      // Populate form fields with inventory item data
      document.getElementById(`part-description-${partCounter}`).value =
        item.name;
      document.getElementById(`part-number-${partCounter}`).value =
        item.part_number;
      document.getElementById(`part-price-${partCounter}`).value = item.price;

      // Preserve the original quantity from the repair order
      if (existingPartData && existingPartData.quantity) {
        document.getElementById(`part-quantity-${partCounter}`).value =
          existingPartData.quantity;
      }

      // Update totals
      updateTotals();
    }
  }

  // Set up search functionality for inventory items
  function setupInventorySearch(partCounter) {
    const searchInput = document.getElementById(
      `part-inventory-search-${partCounter}`
    );
    const optionsContainer = document.getElementById(
      `part-inventory-options-${partCounter}`
    );
    const hiddenInput = document.getElementById(
      `part-inventory-${partCounter}`
    );

    if (!searchInput || !optionsContainer || !hiddenInput) {
      return;
    }

    // Populate options if inventory items are available
    if (inventoryItems.length > 0) {
      populateSearchOptions(partCounter);
    } else {
      // Load inventory items first
      loadInventoryItems().then(() => {
        populateSearchOptions(partCounter);
      });
    }

    // Search input event listeners
    searchInput.addEventListener("input", function () {
      const searchTerm = this.value.toLowerCase();
      filterSearchOptions(partCounter, searchTerm);
    });

    searchInput.addEventListener("focus", function () {
      optionsContainer.style.display = "block";
      if (this.value === "") {
        showAllOptions(partCounter);
      }
    });

    // Keyboard navigation
    searchInput.addEventListener("keydown", function (e) {
      const options = optionsContainer.querySelectorAll(".dropdown-option");
      const visibleOptions = Array.from(options).filter(
        (option) => option.style.display !== "none"
      );

      if (e.key === "ArrowDown") {
        e.preventDefault();
        const currentIndex = visibleOptions.findIndex((option) =>
          option.classList.contains("selected")
        );
        const nextIndex =
          currentIndex < visibleOptions.length - 1 ? currentIndex + 1 : 0;

        visibleOptions.forEach((option) => option.classList.remove("selected"));
        if (visibleOptions[nextIndex]) {
          visibleOptions[nextIndex].classList.add("selected");
        }
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        const currentIndex = visibleOptions.findIndex((option) =>
          option.classList.contains("selected")
        );
        const prevIndex =
          currentIndex > 0 ? currentIndex - 1 : visibleOptions.length - 1;

        visibleOptions.forEach((option) => option.classList.remove("selected"));
        if (visibleOptions[prevIndex]) {
          visibleOptions[prevIndex].classList.add("selected");
        }
      } else if (e.key === "Enter") {
        e.preventDefault();
        const selectedOption = visibleOptions.find((option) =>
          option.classList.contains("selected")
        );
        if (selectedOption) {
          const item = JSON.parse(selectedOption.dataset.item);
          selectInventoryItem(partCounter, item);
        }
      } else if (e.key === "Escape") {
        optionsContainer.style.display = "none";
        searchInput.blur();
      }
    });

    // Close dropdown when clicking outside
    document.addEventListener("click", function (e) {
      if (
        !searchInput.contains(e.target) &&
        !optionsContainer.contains(e.target)
      ) {
        optionsContainer.style.display = "none";
      }
    });
  }

  // Populate search options for a specific part
  function populateSearchOptions(partCounter) {
    const optionsContainer = document.getElementById(
      `part-inventory-options-${partCounter}`
    );
    if (!optionsContainer) return;

    optionsContainer.innerHTML = "";

    inventoryItems.forEach((item) => {
      const option = document.createElement("div");
      option.className = "dropdown-option";
      option.dataset.value = item.id;
      option.dataset.item = JSON.stringify(item);
      option.textContent = `${item.part_number} - ${item.name} (Stock: ${item.quantity})`;

      option.addEventListener("click", function () {
        selectInventoryItem(partCounter, item);
      });

      optionsContainer.appendChild(option);
    });
  }

  // Filter search options based on search term
  function filterSearchOptions(partCounter, searchTerm) {
    const optionsContainer = document.getElementById(
      `part-inventory-options-${partCounter}`
    );
    if (!optionsContainer) return;

    const options = optionsContainer.querySelectorAll(".dropdown-option");

    options.forEach((option) => {
      const text = option.textContent.toLowerCase();
      if (text.includes(searchTerm)) {
        option.style.display = "block";
      } else {
        option.style.display = "none";
      }
    });
  }

  // Show all options
  function showAllOptions(partCounter) {
    const optionsContainer = document.getElementById(
      `part-inventory-options-${partCounter}`
    );
    if (!optionsContainer) return;

    const options = optionsContainer.querySelectorAll(".dropdown-option");
    options.forEach((option) => {
      option.style.display = "block";
    });
  }

  // Select an inventory item
  function selectInventoryItem(partCounter, item) {
    const searchInput = document.getElementById(
      `part-inventory-search-${partCounter}`
    );
    const hiddenInput = document.getElementById(
      `part-inventory-${partCounter}`
    );
    const optionsContainer = document.getElementById(
      `part-inventory-options-${partCounter}`
    );

    if (searchInput && hiddenInput) {
      searchInput.value = `${item.part_number} - ${item.name}`;
      hiddenInput.value = item.id;

      // Populate other fields
      document.getElementById(`part-description-${partCounter}`).value =
        item.name;
      document.getElementById(`part-number-${partCounter}`).value =
        item.part_number;
      document.getElementById(`part-price-${partCounter}`).value = item.price;

      // Set quantity to 1 if not already set
      const quantityField = document.getElementById(
        `part-quantity-${partCounter}`
      );
      if (!quantityField.value || quantityField.value === "0") {
        quantityField.value = "1";
      }

      // Hide dropdown
      optionsContainer.style.display = "none";

      // Update totals
      updateTotals();
    }
  }

  // Update the onInventorySelect function to work with search
  window.onInventorySelect = function (partCounter) {
    // This function is now handled by selectInventoryItem
  };

  // Load inventory items when page loads and wait for it to complete
  loadInventoryItems()
    .then(() => {
      console.log("Inventory items loaded successfully");
    })
    .catch((error) => {
      console.error("Failed to load inventory items:", error);
    });
});
