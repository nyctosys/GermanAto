// ===== REPAIR ORDER FORM JAVASCRIPT =====

// Global variables
let customers = [];
let cars = [];
let workers = [];
let selectedCustomerId = null;
let selectedCarId = null;
let selectedWorkerId = null;

document.addEventListener("DOMContentLoaded", function () {
  // Check authentication and page access
  if (!auth.requirePageAccess("repair-order")) {
    return;
  }

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

  // Load customers and setup customer selection
  loadCustomers();
  loadCars();
  loadWorkers();
  setupSearchableDropdowns();
  setupCustomerModal();
  setupCarModal();
  
  // Setup edit button event listeners
  const editCustomerBtn = document.getElementById("edit-customer-btn");
  if (editCustomerBtn) {
    editCustomerBtn.addEventListener("click", function() {
      if (typeof window.openEditCustomerModal === "function") {
        window.openEditCustomerModal();
      } else {
        console.error("openEditCustomerModal function not found");
      }
    });
  }
  
  const editCarBtn = document.getElementById("edit-car-btn");
  if (editCarBtn) {
    editCarBtn.addEventListener("click", function() {
      console.log("Edit car button clicked, selectedCarId:", selectedCarId);
      if (typeof window.openEditCarModal === "function") {
        window.openEditCarModal();
      } else {
        console.error("openEditCarModal function not found");
      }
    });
  } else {
    console.warn("edit-car-btn element not found");
  }

  // ===== FUNCTIONS =====

  async function loadQuoteData(quoteId) {
    try {
      const quoteData = await APIHelper.get(`/api/invoice/${quoteId}`);
      if (quoteData) {
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
          status: "Pending",
        });
      });
    }
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
                    <input type="text" id="part-description-${partCounter}" name="parts[${partCounter}][description]" required readonly>
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

    // Add event listeners for quantity calculation
    const quantityInput = document.getElementById(
      `part-quantity-${partCounter}`
    );
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

      document.getElementById(`labour-status-${labourCounter}`).value =
        existingData.status || "Pending";
    }

    // No event listeners needed for labour items without pricing
  }

  function removeItem(itemId) {
    const item = document.getElementById(itemId);
    if (item) {
      item.remove();
    }
  }

  async function loadRepairOrderData(repairOrderId) {
    try {
      const repairOrderData = await APIHelper.get(
        `/api/repair-orders/${repairOrderId}`
      );
      if (repairOrderData) {
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
    // Find and select customer from dropdown if available
    const customerSelect = document.getElementById("customer-select");
    if (customerSelect && customers.length > 0) {
      // Try to find customer by name and phone
      let customer = customers.find(
        (c) => c.name === repairOrderData.customer_name && c.phone === repairOrderData.customer_phone
      );
      // Fallback: match by phone only
      if (!customer && repairOrderData.customer_phone) {
        customer = customers.find((c) => c.phone === repairOrderData.customer_phone);
      }
      // Fallback: match by name only
      if (!customer && repairOrderData.customer_name) {
        customer = customers.find((c) => c.name === repairOrderData.customer_name);
      }
      
      if (customer) {
        const customerDisplayText = `${customer.name} - ${customer.phone}`;
        customerSelect.value = customerDisplayText;
        handleCustomerChange(customer.id);
        
        // Wait for car dropdown to be populated, then select car
        setTimeout(() => {
          const carSelect = document.getElementById("car-select");
          if (carSelect && cars.length > 0 && repairOrderData.customer_reg_no) {
            // Find car by plate number, but only from the selected customer's cars
            const car = cars.find(
              (c) => c.plate_no === repairOrderData.customer_reg_no && c.customer_id === customer.id
            );
            
            if (car) {
              const carDisplayText = `${car.make} ${car.model || ""} - ${car.plate_no}`;
              carSelect.value = carDisplayText;
              handleCarChange(car.id);
            }
          }
        }, 100);
      }
    }
    
    // Populate customer information (now editable in edit mode)
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

    // Populate multiple workers selection
    selectedWorkerIds = [];
    if (repairOrderData.workers_json && repairOrderData.workers_json.length > 0) {
      repairOrderData.workers_json.forEach(w => {
        if (w.id) selectedWorkerIds.push(w.id);
      });
    } else if (repairOrderData.worker_id) {
      // Fallback for single worker compatibility
      selectedWorkerIds.push(repairOrderData.worker_id);
    }
    
    renderSelectedWorkers();
    updateHiddenWorkerFields();
    
    // Clear search input so it doesn't show old singular worker text
    const workerSelect = document.getElementById("worker-select");
    if (workerSelect) {
      workerSelect.value = "";
    }
    
    // Check if repair order is completed and user is not admin - edit lock!
    const currentUser = JSON.parse(localStorage.getItem("user") || "{}");
    if (repairOrderData.current_status === "complete" && currentUser.role !== "admin") {
      // Lock down the entire form!
      const form = document.getElementById("repair-order-form");
      if (form) {
        // Disable all inputs, textareas, selects, and buttons
        form.querySelectorAll("input, textarea, select, button").forEach(el => {
          el.disabled = true;
          if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
            el.readOnly = true;
          }
        });
        
        // Show warning banner
        const warningBanner = document.createElement("div");
        warningBanner.className = "alert alert-warning";
        warningBanner.style.background = "#fff5f5";
        warningBanner.style.border = "1px solid #fed7d7";
        warningBanner.style.color = "#c53030";
        warningBanner.style.padding = "16px";
        warningBanner.style.borderRadius = "8px";
        warningBanner.style.marginBottom = "20px";
        warningBanner.style.fontWeight = "600";
        warningBanner.style.gridColumn = "1 / -1";
        warningBanner.textContent = "This repair order is Completed and Locked. Only administrators can make edits.";
        form.insertBefore(warningBanner, form.firstChild);
      }
    }

    // Populate parts
    if (repairOrderData.parts && repairOrderData.parts.length > 0) {
      repairOrderData.parts.forEach((part) => {
        addPartItem({
          description: part.description,
          part_number: part.part_number || "",
          quantity: part.quantity,
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
          status: labour.status || "Pending",
        });
      });
    }
  }

  function setEditMode() {
    // Update page title and description
    document.getElementById("page-title").textContent = "Edit Repair Order";
    document.getElementById("page-description").textContent =
      "Update repair order details";
    document.getElementById("submit-btn").textContent = "Update Repair Order";

    // Keep customer and vehicle information fields editable in edit mode
    // Removed the code that disabled these fields
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
      worker_id: formData.get("worker_id") || null,
      worker_name: formData.get("worker_name") || null,
      worker_ids: selectedWorkerIds,
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
          status: document.getElementById(`labour-status-${i}`).value,
        };
        repairOrderData.labour.push(labourData);
      }
    }

    // Price-related fields removed - no totals needed

    try {
      // Update customer record if a customer was selected - Using centralized utility
      if (selectedCustomerId) {
        try {
          const customerData = {
            name: repairOrderData.customer_name,
            phone: repairOrderData.customer_phone,
            address: repairOrderData.customer_address,
          };
          await CustomerCarUtils.updateCustomer(selectedCustomerId, customerData);
          console.log("Customer updated successfully");
        } catch (error) {
          console.error("Failed to update customer:", error);
          // Continue with repair order creation even if customer update fails
        }
      }

      // Update car record if a car was selected - Using centralized utility
      if (selectedCarId) {
        try {
          // Parse make and model from made field (user may have entered both)
          const makeModelParts = repairOrderData.customer_made.split(" ");
          const make = makeModelParts[0] || "";
          const model = makeModelParts.slice(1).join(" ") || "";

          const carData = {
            make: make,
            model: model,
            plate_no: repairOrderData.customer_reg_no,
            mileage: repairOrderData.customer_mileage || null,
            vin: repairOrderData.customer_vin || null,
            color: repairOrderData.customer_color || null,
            chasis_no: repairOrderData.customer_chasis || null,
            customer_id: selectedCustomerId || null,
          };
          await CustomerCarUtils.updateCar(selectedCarId, carData);
          console.log("Car updated successfully");
        } catch (error) {
          console.error("Failed to update car:", error);
          // Continue with repair order creation even if car update fails
        }
      }

      let response;
      let result;

      if (repairOrderId) {
        // Update existing repair order
        result = await APIHelper.put(
          `/api/repair-orders/${repairOrderId}`,
          repairOrderData
        );

        if (result) {
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
        result = await APIHelper.post("/api/repair-orders", repairOrderData);

        if (result) {
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

  // Load inventory items for dropdowns (legacy function - now using database search)
  async function loadInventoryItems() {
    try {
      const data = await APIHelper.get("/api/inventory");
      if (data) {
        inventoryItems = data.items || data; // Handle both array and object with items property
        // Note: No longer automatically populating dropdowns - using database search instead
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
    const items = Array.isArray(inventoryItems) ? inventoryItems : [];
    items.forEach((item) => {
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

      // Preserve existing quantity if it's already set (for edit mode)
      const quantityField = document.getElementById(
        `part-quantity-${partCounter}`
      );
      if (!quantityField.value || quantityField.value === "0") {
        // Only set quantity to 1 if it's not already set
        quantityField.value = "1";
      }

      // Update totals
    } else {
      // Clear form fields if no item selected
      document.getElementById(`part-description-${partCounter}`).value = "";
      document.getElementById(`part-number-${partCounter}`).value = "";
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
        const items = Array.isArray(inventoryItems) ? inventoryItems : [];
        const matchingItem = items.find(
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
    const items = Array.isArray(inventoryItems) ? inventoryItems : [];
    const item = items.find((item) => item.id == inventoryId);
    if (item) {
      // Populate form fields with inventory item data
      document.getElementById(`part-description-${partCounter}`).value =
        item.name;
      document.getElementById(`part-number-${partCounter}`).value =
        item.part_number;

      // Preserve the original quantity from the repair order
      if (existingPartData && existingPartData.quantity) {
        document.getElementById(`part-quantity-${partCounter}`).value =
          existingPartData.quantity;
      }

      // Update totals
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

    // Search input event listeners with database search
    let searchTimeout;
    searchInput.addEventListener("input", function () {
      const searchTerm = this.value.trim();

      // Clear previous timeout
      if (searchTimeout) {
        clearTimeout(searchTimeout);
      }

      // Clear dropdown if search term is empty
      if (!searchTerm) {
        optionsContainer.style.display = "none";
        return;
      }

      // Only search if we have at least 2 characters to avoid too many results
      if (searchTerm.length < 2) {
        return;
      }

      // Debounce the search - wait 300ms after user stops typing
      searchTimeout = setTimeout(async () => {
        await searchInventoryItems(partCounter, searchTerm);
      }, 300);
    });

    searchInput.addEventListener("focus", function () {
      if (this.value.trim().length >= 2) {
        optionsContainer.style.display = "block";
        searchInventoryItems(partCounter, this.value.trim());
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

  // Search inventory items using database query
  async function searchInventoryItems(partCounter, searchTerm) {
    const optionsContainer = document.getElementById(
      `part-inventory-options-${partCounter}`
    );
    if (!optionsContainer) return;

    try {
      // Show loading state
      optionsContainer.innerHTML =
        '<div class="dropdown-option">Searching...</div>';
      optionsContainer.style.display = "block";

      // Call the database search endpoint
      const result = await APIHelper.get(
        `/api/inventory/search?q=${encodeURIComponent(searchTerm)}`
      );

      if (result && result.results) {
        populateSearchOptionsFromResults(partCounter, result.results);
      } else {
        optionsContainer.innerHTML =
          '<div class="dropdown-option">No items found</div>';
      }
    } catch (error) {
      console.error("Error searching inventory:", error);
      optionsContainer.innerHTML =
        '<div class="dropdown-option">Error searching items</div>';
    }
  }

  // Populate search options from database search results
  function populateSearchOptionsFromResults(partCounter, items) {
    const optionsContainer = document.getElementById(
      `part-inventory-options-${partCounter}`
    );
    if (!optionsContainer) return;

    optionsContainer.innerHTML = "";

    if (items.length === 0) {
      optionsContainer.innerHTML =
        '<div class="dropdown-option">No items found</div>';
      return;
    }

    items.forEach((item) => {
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

  // Populate search options for a specific part (legacy function for backward compatibility)
  function populateSearchOptions(partCounter) {
    const optionsContainer = document.getElementById(
      `part-inventory-options-${partCounter}`
    );
    if (!optionsContainer) return;

    optionsContainer.innerHTML = "";

    // Ensure inventoryItems is an array
    const items = Array.isArray(inventoryItems) ? inventoryItems : [];
    items.forEach((item) => {
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

  // Show all options (legacy function - now triggers search)
  function showAllOptions(partCounter) {
    const searchInput = document.getElementById(
      `part-inventory-search-${partCounter}`
    );
    if (searchInput && searchInput.value.trim().length >= 2) {
      // If there's a search term, trigger search
      searchInventoryItems(partCounter, searchInput.value.trim());
    } else {
      // If no search term, hide the dropdown
      const optionsContainer = document.getElementById(
        `part-inventory-options-${partCounter}`
      );
      if (optionsContainer) {
        optionsContainer.style.display = "none";
      }
    }
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
    }
  }

  // Update the onInventorySelect function to work with search
  window.onInventorySelect = function (partCounter) {
    // This function is now handled by selectInventoryItem
  };

  // Load inventory items when page loads and wait for it to complete
  loadInventoryItems()
    .then(() => {})
    .catch((error) => {
      console.error("Failed to load inventory items:", error);
    });

  // ===== CUSTOMER FUNCTIONS =====

  // Load customers from API - Using centralized utility
  async function loadCustomers() {
    try {
      const data = await CustomerCarUtils.loadCustomers();
      if (data) {
        customers = data;
        populateCustomerSelect();
        // Also update car modal customer dropdown
        updateCarModalCustomerDropdown();
      }
    } catch (error) {
      console.error("Error loading customers:", error);
    }
  }

  // Populate customer dropdown
  function populateCustomerSelect() {
    const customerInput = document.getElementById("customer-select");
    const customerDropdown = document.getElementById(
      "customer-dropdown-options"
    );

    customerDropdown.innerHTML = "";

    customers.forEach((customer) => {
      const option = document.createElement("div");
      option.className = "dropdown-option";
      option.setAttribute("data-value", customer.id);
      option.textContent = `${customer.name} - ${customer.phone}`;
      customerDropdown.appendChild(option);
    });
  }

  // Set up searchable dropdowns
  function setupSearchableDropdowns() {
    // Customer dropdown
    const customerInput = document.getElementById("customer-select");
    const customerDropdown = document.getElementById(
      "customer-dropdown-options"
    );

    // Show dropdown when input is clicked
    customerInput.addEventListener("click", function () {
      customerDropdown.style.display = "block";
      this.readOnly = false;
      // Add dropdown-active class to parent section-card
      const sectionCard = this.closest(".section-card");
      if (sectionCard) {
        sectionCard.classList.add("dropdown-active");
      }
    });

    // Hide dropdown when clicking outside
    document.addEventListener("click", function (e) {
      if (
        !customerInput.contains(e.target) &&
        !customerDropdown.contains(e.target)
      ) {
        customerDropdown.style.display = "none";
        // Remove dropdown-active class from parent section-card
        const sectionCard = customerInput.closest(".section-card");
        if (sectionCard) {
          sectionCard.classList.remove("dropdown-active");
        }
      }
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

    // Handle option selection
    customerDropdown.addEventListener("click", function (e) {
      if (e.target.classList.contains("dropdown-option")) {
        const selectedValue = e.target.getAttribute("data-value");
        const selectedText = e.target.textContent;

        customerInput.value = selectedText;
        customerDropdown.style.display = "none";
        customerInput.readOnly = false;
        customerInput.removeAttribute("readonly");

        // Remove dropdown-active class from parent section-card
        const sectionCard = customerInput.closest(".section-card");
        if (sectionCard) {
          sectionCard.classList.remove("dropdown-active");
        }

        // Trigger customer change
        handleCustomerChange(parseInt(selectedValue));
      }
    });

    // Car dropdown
    const carInput = document.getElementById("car-select");
    const carDropdown = document.getElementById("car-dropdown-options");

    if (carInput && carDropdown) {
      // Show dropdown when input is clicked
      carInput.addEventListener("click", function () {
        // Check if a customer is selected
        if (!selectedCustomerId) {
          alert("Please select a customer first before selecting a car.");
          return;
        }
        
        // Refresh car list to show only selected customer's cars
        populateCarSelect();
        
        carDropdown.style.display = "block";
        this.readOnly = false;
        // Add dropdown-active class to parent section-card
        const sectionCard = this.closest(".section-card");
        if (sectionCard) {
          sectionCard.classList.add("dropdown-active");
        }
      });

      // Handle search functionality for cars
      carInput.addEventListener("input", function () {
        // If no customer is selected, show message
        if (!selectedCustomerId) {
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

      // Handle option selection
      carDropdown.addEventListener("click", function (e) {
        if (e.target.classList.contains("dropdown-option")) {
          const selectedValue = e.target.getAttribute("data-value");
          const selectedText = e.target.textContent;

          carInput.value = selectedText;
          carDropdown.style.display = "none";
          carInput.readOnly = false;
          carInput.removeAttribute("readonly");

          // Remove dropdown-active class from parent section-card
          const sectionCard = carInput.closest(".section-card");
          if (sectionCard) {
            sectionCard.classList.remove("dropdown-active");
          }

          // Trigger car change
          handleCarChange(parseInt(selectedValue));
        }
      });
    }

    // Worker dropdown
    const workerInput = document.getElementById("worker-select");
    const workerDropdown = document.getElementById("worker-dropdown-options");

    if (workerInput && workerDropdown) {
      // Show dropdown when input is clicked
      workerInput.addEventListener("click", function () {
        workerDropdown.style.display = "block";
        this.readOnly = false;
        // Add dropdown-active class to parent section-card
        const sectionCard = this.closest(".section-card");
        if (sectionCard) {
          sectionCard.classList.add("dropdown-active");
        }
      });

      // Handle search functionality for workers
      workerInput.addEventListener("input", function () {
        const searchTerm = this.value.toLowerCase();
        const options = workerDropdown.querySelectorAll(".dropdown-option");

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
      workerDropdown.addEventListener("click", function (e) {
        if (e.target.classList.contains("dropdown-option")) {
          const selectedValue = e.target.getAttribute("data-value");
          const selectedText = e.target.textContent;

          workerInput.value = "";
          workerDropdown.style.display = "none";
          workerInput.readOnly = false;
          workerInput.removeAttribute("readonly");

          // Remove dropdown-active class from parent section-card
          const sectionCard = workerInput.closest(".section-card");
          if (sectionCard) {
            sectionCard.classList.remove("dropdown-active");
          }

          // Trigger worker change
          handleWorkerChange(parseInt(selectedValue));
        }
      });
    }

    // Hide dropdowns when clicking outside
    document.addEventListener("click", function (e) {
      if (
        !customerInput.contains(e.target) &&
        !customerDropdown.contains(e.target)
      ) {
        customerDropdown.style.display = "none";
        // Remove dropdown-active class from parent section-card
        const sectionCard = customerInput.closest(".section-card");
        if (sectionCard) {
          sectionCard.classList.remove("dropdown-active");
        }
      }
      if (
        carInput &&
        !carInput.contains(e.target) &&
        carDropdown &&
        !carDropdown.contains(e.target)
      ) {
        carDropdown.style.display = "none";
        // Remove dropdown-active class from parent section-card
        const sectionCard = carInput.closest(".section-card");
        if (sectionCard) {
          sectionCard.classList.remove("dropdown-active");
        }
      }
      if (
        workerInput &&
        !workerInput.contains(e.target) &&
        workerDropdown &&
        !workerDropdown.contains(e.target)
      ) {
        workerDropdown.style.display = "none";
        // Remove dropdown-active class from parent section-card
        const sectionCard = workerInput.closest(".section-card");
        if (sectionCard) {
          sectionCard.classList.remove("dropdown-active");
        }
      }
    });
  }

  // Handle customer selection change
  function handleCustomerChange(customerId) {
    selectedCustomerId = customerId;
    
    // Clear car selection when customer changes
    selectedCarId = null;

    if (customerId) {
      const customer = customers.find((c) => c.id === customerId);
      if (customer) {
        // Populate customer fields
        document.getElementById("customer-name").value = customer.name;
        document.getElementById("customer-phone").value = customer.phone;
        document.getElementById("customer-address").value =
          customer.address || "";
        
        // Show edit button
        const editBtn = document.getElementById("edit-customer-btn");
        if (editBtn) {
          editBtn.style.display = "flex";
        }
      }
      
      // Clear car input and refresh car dropdown
      const carSelect = document.getElementById("car-select");
      if (carSelect) {
        carSelect.value = "";
      }
      
      // Clear car details fields if they exist
      const carReg = document.getElementById("car-reg");
      const carMake = document.getElementById("car-make");
      const carModel = document.getElementById("car-model");
      const carMileage = document.getElementById("car-mileage");
      const carVin = document.getElementById("car-vin");
      const carColor = document.getElementById("car-color");
      const carChasis = document.getElementById("car-chasis");
      
      if (carReg) carReg.value = "";
      if (carMake) carMake.value = "";
      if (carModel) carModel.value = "";
      if (carMileage) carMileage.value = "";
      if (carVin) carVin.value = "";
      if (carColor) carColor.value = "";
      if (carChasis) carChasis.value = "";
      
      // Refresh car dropdown to show only this customer's cars
      populateCarSelect();
    } else {
      // Clear customer fields
      document.getElementById("customer-name").value = "";
      document.getElementById("customer-phone").value = "";
      document.getElementById("customer-address").value = "";
      
      // Hide edit button
      const editBtn = document.getElementById("edit-customer-btn");
      if (editBtn) {
        editBtn.style.display = "none";
      }
      
      // Clear car input and refresh car dropdown
      const carSelect = document.getElementById("car-select");
      if (carSelect) {
        carSelect.value = "";
      }
      
      // Refresh car dropdown (will show "Please select a customer first" message)
      populateCarSelect();
    }
  }

  // Set up customer modal
  function setupCustomerModal() {
    const customerModal = document.getElementById("customer-modal");
    const closeBtn = document.getElementById("close-customer-modal");
    const cancelBtn = document.getElementById("cancel-customer");
    const customerForm = document.getElementById("customer-form");

    // Open modal for creating new customer
    window.openCustomerModal = function () {
      window.editingCustomerId = null;
      const modalTitle = document.getElementById("customer-modal-title");
      if (modalTitle) {
        modalTitle.textContent = "Add Customer";
      }
      customerForm.reset();
      customerModal.style.display = "block";
    };

    // Open modal for editing existing customer
    window.openEditCustomerModal = function () {
      if (!selectedCustomerId) {
        alert("Please select a customer first.");
        return;
      }

      const customer = customers.find((c) => c.id === selectedCustomerId);
      if (!customer) {
        alert("Customer not found.");
        return;
      }

      window.editingCustomerId = selectedCustomerId;
      const modalTitle = document.getElementById("customer-modal-title");
      if (modalTitle) {
        modalTitle.textContent = "Edit Customer";
      }

      // Populate form with customer data
      document.getElementById("modal-customer-name").value = customer.name || "";
      document.getElementById("modal-customer-phone").value = customer.phone || "";
      document.getElementById("modal-customer-address").value = customer.address || "";

      customerModal.style.display = "block";
    };

    // Close modal
    function closeModal() {
      customerModal.style.display = "none";
      customerForm.reset();
      window.editingCustomerId = null;
    }

    closeBtn.addEventListener("click", closeModal);
    cancelBtn.addEventListener("click", closeModal);

    // Close modal when clicking outside
    customerModal.addEventListener("click", function (e) {
      if (e.target === customerModal) {
        closeModal();
      }
    });

    // Handle form submission - Using centralized utilities
    customerForm.addEventListener("submit", async function (e) {
      e.preventDefault();

      const formData = new FormData(customerForm);
      const customerData = {
        name: formData.get("modal-customer-name"),
        phone: formData.get("modal-customer-phone"),
        address: formData.get("modal-customer-address"),
      };

      try {
        let updatedCustomer;
        const isEditing = window.editingCustomerId;

        if (isEditing) {
          // Update existing customer
          updatedCustomer = await CustomerCarUtils.updateCustomer(window.editingCustomerId, customerData);
          
          // Update in customers array
          const index = customers.findIndex((c) => c.id === window.editingCustomerId);
          if (index !== -1) {
            customers[index] = updatedCustomer;
          }
          
          if (typeof showNotification === "function") {
            showNotification("Customer updated successfully!", "success");
          } else {
            alert("Customer updated successfully!");
          }
        } else {
          // Create new customer
          updatedCustomer = await CustomerCarUtils.createCustomer(customerData);
          
          // Add to customers array
          customers.push(updatedCustomer);
          
          if (typeof showNotification === "function") {
            showNotification("Customer created successfully!", "success");
          } else {
            alert("Customer created successfully!");
          }
        }

        // Update form fields
        document.getElementById("customer-name").value = updatedCustomer.name;
        document.getElementById("customer-phone").value = updatedCustomer.phone;
        document.getElementById("customer-address").value = updatedCustomer.address || "";

        const customerDisplayText = `${updatedCustomer.name} - ${updatedCustomer.phone}`;
        document.getElementById("customer-select").value = customerDisplayText;

        populateCustomerSelect();

        // Update selected customer ID
        if (isEditing && selectedCustomerId === window.editingCustomerId) {
          selectedCustomerId = updatedCustomer.id;
        } else if (!isEditing) {
          handleCustomerChange(updatedCustomer.id);
        }

        // Update car modal customer dropdown if it exists
        updateCarModalCustomerDropdown();

        closeModal();
      } catch (error) {
        console.error("Error saving customer:", error);
        const errorMsg = error.message || (window.editingCustomerId ? "Failed to update customer" : "Failed to create customer");
        if (typeof showNotification === "function") {
          showNotification(errorMsg, "error");
        } else {
          alert("Error: " + errorMsg);
        }
      }
    });
  }

  // ===== CAR FUNCTIONS =====

  // Load cars from API - Using centralized utility
  async function loadCars() {
    try {
      const data = await CustomerCarUtils.loadCars();
      if (data) {
        cars = data;
        populateCarSelect();
      }
    } catch (error) {
      console.error("Error loading cars:", error);
    }
  }

  // Load workers from API
  async function loadWorkers() {
    try {
      const data = await APIHelper.get("/api/workers");
      if (!data) return;

      workers = data.workers || data;
      populateWorkerSelect();
    } catch (error) {
      console.error("Error loading workers:", error);
    }
  }

  // Populate car dropdown - filtered by selected customer
  function populateCarSelect() {
    const carInput = document.getElementById("car-select");
    const carDropdown = document.getElementById("car-dropdown-options");

    if (!carInput || !carDropdown) return;

    carDropdown.innerHTML = "";

    if (selectedCustomerId) {
      // Filter cars by selected customer
      const customerCars = cars.filter(
        (car) => car.customer_id === selectedCustomerId
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
          option.textContent = `${car.make} ${car.model || ""} - ${car.plate_no}`;
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

  // Populate worker dropdown
  function populateWorkerSelect() {
    const workerInput = document.getElementById("worker-select");
    const workerDropdown = document.getElementById("worker-dropdown-options");

    if (!workerInput || !workerDropdown) return;

    workerDropdown.innerHTML = "";

    workers.forEach((worker) => {
      const option = document.createElement("div");
      option.className = "dropdown-option";
      option.setAttribute("data-value", worker.id);
      option.textContent = `${worker.first_name} ${worker.last_name} - ${
        worker.position || "Worker"
      }`;
      workerDropdown.appendChild(option);
    });
  }

  // Handle car selection change
  function handleCarChange(carId) {
    selectedCarId = carId;

    if (carId) {
      const car = cars.find((c) => c.id === carId);
      if (car) {
        // Verify car belongs to selected customer
        if (selectedCustomerId && car.customer_id !== selectedCustomerId) {
          console.warn("Selected car does not belong to selected customer");
          // Clear car selection if it doesn't match
          selectedCarId = null;
          const carSelect = document.getElementById("car-select");
          if (carSelect) {
            carSelect.value = "";
          }
          alert("This car does not belong to the selected customer. Please select a car from the customer's vehicles.");
          return;
        }
        
        // Populate car fields
        document.getElementById("reg-number").value = car.plate_no || "";
        document.getElementById("made").value = `${car.make || ""} ${car.model || ""}`.trim();
        document.getElementById("mileage").value = car.mileage || "";
        document.getElementById("vin").value = car.vin || "";
        document.getElementById("color").value = car.color || "";
        document.getElementById("chasis").value = car.chasis_no || "";
        
        // Show edit button
        const editBtn = document.getElementById("edit-car-btn");
        if (editBtn) {
          editBtn.style.display = "flex";
        }
      }
    } else {
      // Clear car fields when car is deselected
      document.getElementById("reg-number").value = "";
      document.getElementById("made").value = "";
      document.getElementById("mileage").value = "";
      document.getElementById("vin").value = "";
      document.getElementById("color").value = "";
      document.getElementById("chasis").value = "";
      
      // Hide edit button
      const editBtn = document.getElementById("edit-car-btn");
      if (editBtn) {
        editBtn.style.display = "none";
      }
    }
  }

  let selectedWorkerIds = [];

  function renderSelectedWorkers() {
    const container = document.getElementById("selected-workers-container");
    if (!container) return;
    container.innerHTML = "";

    selectedWorkerIds.forEach((workerId) => {
      const worker = workers.find((w) => w.id === workerId);
      if (worker) {
        const tag = document.createElement("span");
        tag.className = "role-badge role-accountant";
        tag.style.display = "inline-flex";
        tag.style.alignItems = "center";
        tag.style.gap = "6px";
        tag.style.padding = "6px 12px";
        tag.style.borderRadius = "20px";
        tag.style.background = "#ebf8ff";
        tag.style.color = "#2b6cb0";
        tag.style.fontSize = "0.85rem";
        tag.style.fontWeight = "600";
        tag.innerHTML = `
          <span>${worker.first_name} ${worker.last_name}</span>
          <span class="remove-worker" data-id="${worker.id}" style="cursor: pointer; font-size: 1.1rem; line-height: 1; color: #e53e3e;">&times;</span>
        `;
        container.appendChild(tag);
      }
    });

    // Attach click events to "x" buttons
    container.querySelectorAll(".remove-worker").forEach(btn => {
      btn.addEventListener("click", (e) => {
        const idToRemove = parseInt(e.target.getAttribute("data-id"));
        selectedWorkerIds = selectedWorkerIds.filter(id => id !== idToRemove);
        renderSelectedWorkers();
        updateHiddenWorkerFields();
      });
    });
  }

  function updateHiddenWorkerFields() {
    const workerIdField = document.getElementById("worker-id");
    const workerNameField = document.getElementById("worker-name");
    
    if (selectedWorkerIds.length > 0) {
      const firstWorker = workers.find(w => w.id === selectedWorkerIds[0]);
      if (workerIdField && firstWorker) {
        workerIdField.value = firstWorker.id;
      }
      
      if (workerNameField) {
        const allNames = selectedWorkerIds
          .map(id => workers.find(w => w.id === id))
          .filter(Boolean)
          .map(w => `${w.first_name} ${w.last_name}`)
          .join(", ");
        workerNameField.value = allNames;
      }
    } else {
      if (workerIdField) workerIdField.value = "";
      if (workerNameField) workerNameField.value = "";
    }
  }

  // Handle worker selection change
  function handleWorkerChange(workerId) {
    if (workerId && !selectedWorkerIds.includes(workerId)) {
      selectedWorkerIds.push(workerId);
      renderSelectedWorkers();
      updateHiddenWorkerFields();
      
      // Clear the search input
      const workerSelect = document.getElementById("worker-select");
      if (workerSelect) {
        workerSelect.value = "";
        workerSelect.blur();
      }
    }
  }

  // Set up car modal
  function setupCarModal() {
    const carModal = document.getElementById("car-modal");
    const closeBtn = document.getElementById("close-car-modal");
    const cancelBtn = document.getElementById("cancel-car");
    const carForm = document.getElementById("car-form");
    const customerSelect = document.getElementById("modal-car-customer");

    // Function to populate customer dropdown
    function populateCustomerDropdown() {
      if (customerSelect) {
        customerSelect.innerHTML = '<option value="">Select Customer</option>';
        customers.forEach((customer) => {
          const option = document.createElement("option");
          option.value = customer.id;
          option.textContent = `${customer.name} - ${customer.phone}`;
          customerSelect.appendChild(option);
        });
        
        // Auto-select customer if one is already selected in the form
        if (selectedCustomerId) {
          customerSelect.value = selectedCustomerId;
        }
      }
    }

    // Open modal for creating new car
    window.openCarModal = function () {
      window.editingCarId = null;
      const modalTitle = document.getElementById("car-modal-title");
      if (modalTitle) {
        modalTitle.textContent = "Add Car";
      }
      
      // Populate customer dropdown when opening modal
      populateCustomerDropdown();
      
      // Reset form but preserve customer selection
      const preservedCustomerId = selectedCustomerId;
      carForm.reset();
      
      // Re-set the customer selection after reset (reset clears it)
      if (preservedCustomerId && customerSelect) {
        customerSelect.value = preservedCustomerId;
      }
      
      carModal.style.display = "block";
      carModal.classList.add("active");
    };

    // Open modal for editing existing car
    window.openEditCarModal = function () {
      console.log("openEditCarModal called, selectedCarId:", selectedCarId);
      
      if (!selectedCarId) {
        alert("Please select a car first.");
        return;
      }

      const car = cars.find((c) => c.id === selectedCarId);
      if (!car) {
        alert("Car not found.");
        return;
      }

      console.log("Car found:", car);

      window.editingCarId = selectedCarId;
      const modalTitle = document.getElementById("car-modal-title");
      if (modalTitle) {
        modalTitle.textContent = "Edit Car";
      }

      // Populate customer dropdown
      populateCustomerDropdown();

      // Populate form with car data
      if (customerSelect) {
        customerSelect.value = car.customer_id || "";
      }
      const makeField = document.getElementById("modal-car-make");
      const modelField = document.getElementById("modal-car-model");
      const plateField = document.getElementById("modal-car-plate");
      const mileageField = document.getElementById("modal-car-mileage");
      const vinField = document.getElementById("modal-car-vin");
      const colorField = document.getElementById("modal-car-color");
      const chassisField = document.getElementById("modal-car-chassis");
      
      if (makeField) makeField.value = car.make || "";
      if (modelField) modelField.value = car.model || "";
      if (plateField) plateField.value = car.plate_no || "";
      if (mileageField) mileageField.value = car.mileage || "";
      if (vinField) vinField.value = car.vin || "";
      if (colorField) colorField.value = car.color || "";
      if (chassisField) chassisField.value = car.chasis_no || "";

      // Get modal element to ensure it exists
      const carModalElement = document.getElementById("car-modal");
      if (carModalElement) {
        carModalElement.style.display = "block";
        carModalElement.classList.add("active");
        console.log("Car modal opened");
      } else {
        console.error("Car modal element not found");
        alert("Error: Car modal not found");
      }
    };

    // Close modal
    function closeModal() {
      carModal.style.display = "none";
      carModal.classList.remove("active");
      carForm.reset();
      window.editingCarId = null;
    }

    closeBtn.addEventListener("click", closeModal);
    cancelBtn.addEventListener("click", closeModal);

    // Close modal when clicking outside
    carModal.addEventListener("click", function (e) {
      if (e.target === carModal) {
        closeModal();
      }
    });

    // Handle form submission - Using centralized utilities
    carForm.addEventListener("submit", async function (e) {
      e.preventDefault();

      const formData = new FormData(carForm);
      // Get make and model from separate fields
      const make = formData.get("modal-car-make")?.trim() || "";
      const model = formData.get("modal-car-model")?.trim() || "";

      const carData = {
        customer_id: formData.get("modal-car-customer"),
        plate_no: formData.get("modal-car-plate"),
        make: make,
        model: model,
        mileage: formData.get("modal-car-mileage"),
        vin: formData.get("modal-car-vin"),
        color: formData.get("modal-car-color"),
        chasis_no: formData.get("modal-car-chassis"),
      };

      try {
        let updatedCar;
        const isEditing = window.editingCarId;

        if (isEditing) {
          // Update existing car
          updatedCar = await CustomerCarUtils.updateCar(window.editingCarId, carData);
          
          // Update in cars array
          const index = cars.findIndex((c) => c.id === window.editingCarId);
          if (index !== -1) {
            cars[index] = updatedCar;
          }
          
          if (typeof showNotification === "function") {
            showNotification("Vehicle updated successfully!", "success");
          } else {
            alert("Vehicle updated successfully!");
          }
        } else {
          // Create new car
          updatedCar = await CustomerCarUtils.createCar(carData);
          
          // Add to cars array
          cars.push(updatedCar);
          
          if (typeof showNotification === "function") {
            showNotification("Vehicle created successfully!", "success");
          } else {
            alert("Vehicle created successfully!");
          }
        }

        // Update form fields
        document.getElementById("reg-number").value = updatedCar.plate_no || "";
        document.getElementById("made").value = `${updatedCar.make || ""} ${updatedCar.model || ""}`.trim();
        document.getElementById("mileage").value = updatedCar.mileage || "";
        document.getElementById("vin").value = updatedCar.vin || "";
        document.getElementById("color").value = updatedCar.color || "";
        document.getElementById("chasis").value = updatedCar.chasis_no || "";

        const carDisplayText = `${updatedCar.make}${updatedCar.model ? " " + updatedCar.model : ""} - ${updatedCar.plate_no}`;
        document.getElementById("car-select").value = carDisplayText;

        populateCarSelect();

        // Update selected car ID
        if (isEditing && selectedCarId === window.editingCarId) {
          selectedCarId = updatedCar.id;
        } else if (!isEditing && updatedCar.customer_id === selectedCustomerId) {
          handleCarChange(updatedCar.id);
        }

        closeModal();
      } catch (error) {
        console.error("Error saving vehicle:", error);
        const errorMsg = error.message || (window.editingCarId ? "Failed to update vehicle" : "Failed to create vehicle");
        if (typeof showNotification === "function") {
          showNotification(errorMsg, "error");
        } else {
          alert("Error: " + errorMsg);
        }
      }
    });
  }

  // Update car modal customer dropdown
  function updateCarModalCustomerDropdown() {
    const customerSelect = document.getElementById("modal-car-customer");
    if (customerSelect) {
      customerSelect.innerHTML = '<option value="">Select Customer</option>';
      customers.forEach((customer) => {
        const option = document.createElement("option");
        option.value = customer.id;
        option.textContent = `${customer.name} - ${customer.phone}`;
        customerSelect.appendChild(option);
      });
    }
  }
});
