/**
 * Centralized Customer and Car Management Utilities
 * 
 * This module provides shared functions for creating and managing customers and cars
 * across invoices/quotes and repair orders to prevent conflicts and ensure consistency.
 */

/**
 * Customer Management Functions
 */
const CustomerCarUtils = {
  /**
   * Load customers from API
   * @returns {Promise<Array>} Array of customers
   */
  async loadCustomers() {
    try {
      const data = await APIHelper.get("/api/customers");
      return data || [];
    } catch (error) {
      console.error("Error loading customers:", error);
      throw error;
    }
  },

  /**
   * Create a new customer
   * @param {Object} customerData - Customer data object
   * @param {string} customerData.name - Customer name (required)
   * @param {string} customerData.phone - Customer phone (required)
   * @param {string} customerData.address - Customer address
   * @returns {Promise<Object>} Created customer object
   */
  async createCustomer(customerData) {
    // All fields are optional - no validation required

    // Clean and prepare data - send "N/A" for empty optional fields
    const data = {
      name: customerData.name && String(customerData.name).trim() ? String(customerData.name).trim() : "N/A",
      phone: customerData.phone && String(customerData.phone).trim() ? String(customerData.phone).trim() : "N/A",
      address: customerData.address && String(customerData.address).trim() ? String(customerData.address).trim() : "N/A",
    };

    try {
      const result = await APIHelper.post("/api/customers", data);
      if (!result || !result.customer) {
        throw new Error("Failed to create customer");
      }
      return result.customer;
    } catch (error) {
      console.error("Error creating customer:", error);
      // Extract error message from API response if available
      if (error.response && error.response.data) {
        const errorMsg = error.response.data.details || error.response.data.error || error.message;
        throw new Error(errorMsg);
      }
      throw error;
    }
  },

  /**
   * Update an existing customer
   * @param {number} customerId - Customer ID
   * @param {Object} customerData - Updated customer data
   * @returns {Promise<Object>} Updated customer object
   */
  async updateCustomer(customerId, customerData) {
    if (!customerId) {
      throw new Error("Customer ID is required");
    }

    // Clean and prepare data - send "N/A" for empty optional fields
    const data = {
      name: customerData.name && String(customerData.name).trim() ? String(customerData.name).trim() : "N/A",
      phone: customerData.phone && String(customerData.phone).trim() ? String(customerData.phone).trim() : "N/A",
      address: customerData.address && String(customerData.address).trim() ? String(customerData.address).trim() : "N/A",
    };

    try {
      const result = await APIHelper.put(`/api/customers/${customerId}`, data);
      if (!result || !result.customer) {
        throw new Error("Failed to update customer");
      }
      return result.customer;
    } catch (error) {
      console.error("Error updating customer:", error);
      if (error.response && error.response.data) {
        const errorMsg = error.response.data.details || error.response.data.error || error.message;
        throw new Error(errorMsg);
      }
      throw error;
    }
  },

  /**
   * Load cars from API
   * @param {number} customerId - Optional customer ID to filter cars
   * @returns {Promise<Array>} Array of cars
   */
  async loadCars(customerId = null) {
    try {
      const endpoint = customerId 
        ? `/api/cars/customer/${customerId}`
        : "/api/cars";
      const data = await APIHelper.get(endpoint);
      // Handle different response formats
      if (Array.isArray(data)) {
        return data;
      } else if (data && data.cars) {
        return data.cars;
      }
      return [];
    } catch (error) {
      console.error("Error loading cars:", error);
      throw error;
    }
  },

  /**
   * Create a new car
   * @param {Object} carData - Car data object
   * @param {string} carData.make - Car make (required)
   * @param {string} carData.model - Car model
   * @param {string} carData.plate_no - Plate number (required)
   * @param {string} carData.mileage - Mileage
   * @param {string} carData.vin - VIN number
   * @param {string} carData.color - Car color
   * @param {string} carData.chasis_no - Chassis number
   * @param {number} carData.customer_id - Customer ID (optional)
   * @returns {Promise<Object>} Created car object
   */
  async createCar(carData) {
    // Only VIN is required
    if (!carData.vin || !carData.vin.trim()) {
      throw new Error("VIN is a required field");
    }

    // Clean and prepare data - send "N/A" for empty optional fields
    const data = {
      make: carData.make && String(carData.make).trim() ? String(carData.make).trim() : "N/A",
      model: carData.model && String(carData.model).trim() ? String(carData.model).trim() : "N/A",
      plate_no: carData.plate_no && String(carData.plate_no).trim() ? String(carData.plate_no).trim() : "N/A",
      mileage: carData.mileage && String(carData.mileage).trim() ? String(carData.mileage).trim() : "N/A",
      vin: String(carData.vin).trim(), // Required field
      color: carData.color && String(carData.color).trim() ? String(carData.color).trim() : "N/A",
      chasis_no: carData.chasis_no && String(carData.chasis_no).trim() ? String(carData.chasis_no).trim() : "N/A",
      customer_id: carData.customer_id ? parseInt(carData.customer_id) : null,
    };

    // Remove null customer_id if not provided
    if (!data.customer_id) delete data.customer_id;

    try {
      const result = await APIHelper.post("/api/cars", data);
      if (!result || !result.car) {
        throw new Error("Failed to create car");
      }
      return result.car;
    } catch (error) {
      console.error("Error creating car:", error);
      if (error.response && error.response.data) {
        const errorMsg = error.response.data.details || error.response.data.error || error.message;
        throw new Error(errorMsg);
      }
      throw error;
    }
  },

  /**
   * Update an existing car
   * @param {number} carId - Car ID
   * @param {Object} carData - Updated car data
   * @returns {Promise<Object>} Updated car object
   */
  async updateCar(carId, carData) {
    if (!carId) {
      throw new Error("Car ID is required");
    }

    // Only VIN is required
    if (!carData.vin || !carData.vin.trim()) {
      throw new Error("VIN is a required field");
    }

    // Clean and prepare data - send "N/A" for empty optional fields
    const data = {
      make: carData.make && String(carData.make).trim() ? String(carData.make).trim() : "N/A",
      model: carData.model && String(carData.model).trim() ? String(carData.model).trim() : "N/A",
      plate_no: carData.plate_no && String(carData.plate_no).trim() ? String(carData.plate_no).trim() : "N/A",
      mileage: carData.mileage && String(carData.mileage).trim() ? String(carData.mileage).trim() : "N/A",
      vin: String(carData.vin).trim(), // Required field
      color: carData.color && String(carData.color).trim() ? String(carData.color).trim() : "N/A",
      chasis_no: carData.chasis_no && String(carData.chasis_no).trim() ? String(carData.chasis_no).trim() : "N/A",
      customer_id: carData.customer_id ? parseInt(carData.customer_id) : null,
    };

    // Remove null customer_id if not provided
    if (!data.customer_id) delete data.customer_id;

    try {
      const result = await APIHelper.put(`/api/cars/${carId}`, data);
      if (!result || !result.car) {
        throw new Error("Failed to update car");
      }
      return result.car;
    } catch (error) {
      console.error("Error updating car:", error);
      if (error.response && error.response.data) {
        const errorMsg = error.response.data.details || error.response.data.error || error.message;
        throw new Error(errorMsg);
      }
      throw error;
    }
  },

  /**
   * Setup customer modal with consistent behavior
   * @param {Object} options - Configuration options
   * @param {string} options.modalId - Modal element ID
   * @param {string} options.formId - Form element ID
   * @param {string} options.nameFieldId - Name input field ID
   * @param {string} options.phoneFieldId - Phone input field ID
   * @param {string} options.addressFieldId - Address input field ID
   * @param {Function} options.onSuccess - Callback when customer is created
   * @param {Function} options.onClose - Callback when modal is closed
   */
  setupCustomerModal(options) {
    const {
      modalId = "customer-modal",
      formId = "customer-form",
      nameFieldId = "modal-customer-name",
      phoneFieldId = "modal-customer-phone",
      addressFieldId = "modal-customer-address",
      onSuccess = null,
      onClose = null,
    } = options;

    const modal = document.getElementById(modalId);
    const form = document.getElementById(formId);
    if (!modal || !form) {
      console.warn(`Customer modal elements not found: ${modalId}, ${formId}`);
      return;
    }

    // Handle form submission
    form.addEventListener("submit", async (e) => {
      e.preventDefault();

      const customerData = {
        name: document.getElementById(nameFieldId)?.value || "",
        phone: document.getElementById(phoneFieldId)?.value || "",
        address: document.getElementById(addressFieldId)?.value || "",
      };

      try {
        const newCustomer = await this.createCustomer(customerData);
        
        // Show success message
        if (typeof showNotification === "function") {
          showNotification("Customer created successfully!", "success");
        } else {
          alert("Customer created successfully!");
        }

        // Close modal
        this.closeCustomerModal(modalId, formId);

        // Call success callback
        if (onSuccess) {
          onSuccess(newCustomer);
        }
      } catch (error) {
        const errorMsg = error.message || "Failed to create customer";
        if (typeof showNotification === "function") {
          showNotification(errorMsg, "error");
        } else {
          alert("Error: " + errorMsg);
        }
      }
    });
  },

  /**
   * Setup car modal with consistent behavior
   * @param {Object} options - Configuration options
   * @param {string} options.modalId - Modal element ID
   * @param {string} options.formId - Form element ID
   * @param {string} options.customerSelectId - Customer select dropdown ID
   * @param {string} options.makeFieldId - Make input field ID
   * @param {string} options.modelFieldId - Model input field ID (optional)
   * @param {string} options.plateFieldId - Plate number input field ID
   * @param {string} options.mileageFieldId - Mileage input field ID
   * @param {string} options.vinFieldId - VIN input field ID
   * @param {string} options.colorFieldId - Color input field ID
   * @param {string} options.chasisFieldId - Chassis input field ID
   * @param {Function} options.onSuccess - Callback when car is created
   * @param {Function} options.onClose - Callback when modal is closed
   * @param {Function} options.getCustomers - Function to get customers list for dropdown
   */
  setupCarModal(options) {
    const {
      modalId = "car-modal",
      formId = "car-form",
      customerSelectId = "modal-car-customer",
      makeFieldId = "modal-car-make",
      modelFieldId = "modal-car-model",
      plateFieldId = "modal-car-plate",
      mileageFieldId = "modal-car-mileage",
      vinFieldId = "modal-car-vin",
      colorFieldId = "modal-car-color",
      chasisFieldId = "modal-car-chasis",
      onSuccess = null,
      onClose = null,
      getCustomers = null,
    } = options;

    const modal = document.getElementById(modalId);
    const form = document.getElementById(formId);
    if (!modal || !form) {
      console.warn(`Car modal elements not found: ${modalId}, ${formId}`);
      return;
    }

    // Handle form submission
    form.addEventListener("submit", async (e) => {
      e.preventDefault();

      const makeField = document.getElementById(makeFieldId);
      const plateField = document.getElementById(plateFieldId);
      
      // Handle combined make/model field (for repair orders)
      let make = makeField?.value || "";
      let model = "";
      
      if (modelFieldId && document.getElementById(modelFieldId)) {
        model = document.getElementById(modelFieldId).value || "";
      } else {
        // If no separate model field, try to parse from make field
        // This handles the "Make/Model" combined field in repair orders
        const makeModelParts = make.split(" ");
        if (makeModelParts.length > 1) {
          make = makeModelParts[0];
          model = makeModelParts.slice(1).join(" ");
        }
      }

      const carData = {
        customer_id: document.getElementById(customerSelectId)?.value || null,
        make: make.trim(),
        model: model.trim(),
        plate_no: plateField?.value || "",
        mileage: document.getElementById(mileageFieldId)?.value || "",
        vin: document.getElementById(vinFieldId)?.value || "",
        color: document.getElementById(colorFieldId)?.value || "",
        chasis_no: document.getElementById(chasisFieldId)?.value || "",
      };

      try {
        const newCar = await this.createCar(carData);
        
        // Show success message
        if (typeof showNotification === "function") {
          showNotification("Car created successfully!", "success");
        } else {
          alert("Car created successfully!");
        }

        // Close modal
        this.closeCarModal(modalId, formId);

        // Call success callback
        if (onSuccess) {
          onSuccess(newCar);
        }
      } catch (error) {
        const errorMsg = error.message || "Failed to create car";
        if (typeof showNotification === "function") {
          showNotification(errorMsg, "error");
        } else {
          alert("Error: " + errorMsg);
        }
      }
    });

    // Populate customer dropdown when modal opens
    const originalOpen = window.openCarModal;
    window.openCarModal = () => {
      if (getCustomers) {
        const customers = getCustomers();
        const customerSelect = document.getElementById(customerSelectId);
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
      if (originalOpen) originalOpen();
      modal.style.display = "block";
      modal.classList.add("active");
    };
  },

  /**
   * Open customer modal
   * @param {string} modalId - Modal element ID
   */
  openCustomerModal(modalId = "customer-modal") {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.style.display = "block";
      modal.classList.add("active");
    }
  },

  /**
   * Close customer modal
   * @param {string} modalId - Modal element ID
   * @param {string} formId - Form element ID
   */
  closeCustomerModal(modalId = "customer-modal", formId = "customer-form") {
    const modal = document.getElementById(modalId);
    const form = document.getElementById(formId);
    if (modal) {
      modal.style.display = "none";
      modal.classList.remove("active");
    }
    if (form) {
      form.reset();
    }
  },

  /**
   * Open car modal
   * @param {string} modalId - Modal element ID
   */
  openCarModal(modalId = "car-modal") {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.style.display = "block";
      modal.classList.add("active");
    }
  },

  /**
   * Close car modal
   * @param {string} modalId - Modal element ID
   * @param {string} formId - Form element ID
   */
  closeCarModal(modalId = "car-modal", formId = "car-form") {
    const modal = document.getElementById(modalId);
    const form = document.getElementById(formId);
    if (modal) {
      modal.style.display = "none";
      modal.classList.remove("active");
    }
    if (form) {
      form.reset();
    }
  },
};

// Export for use in modules
if (typeof module !== "undefined" && module.exports) {
  module.exports = CustomerCarUtils;
}

// Make available globally
window.CustomerCarUtils = CustomerCarUtils;
