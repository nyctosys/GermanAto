// Global variables
let currentCarId = null;
let currentCustomerId = null;
let customers = [];
let cars = [];

// DOM elements
const carModal = document.getElementById("car-modal");
const customerModal = document.getElementById("customer-modal");
const customerCarsModal = document.getElementById("customer-cars-modal");
const carForm = document.getElementById("car-form");
const customerForm = document.getElementById("customer-form");
const carSearchInput = document.getElementById("car-search");
const customerSearchInput = document.getElementById("customer-search");

// Initialize the application
document.addEventListener("DOMContentLoaded", function () {
  // Set up smart back button logic
  const backBtn = document.getElementById("back-btn");
  const urlParams = new URLSearchParams(window.location.search);
  const fromPage =
    urlParams.get("from") || localStorage.getItem("lastPage") || "admin";

  // Set back button destination based on where user came from
  if (fromPage === "admin") {
    backBtn.href = "admin.html";
  } else if (fromPage === "home") {
    backBtn.href = "home.html";
  } else if (fromPage === "invoiceSystem") {
    backBtn.href = "invoiceSystem.html";
  } else {
    backBtn.href = "admin.html"; // Default fallback
  }

  // Track current page for back button logic
  localStorage.setItem("lastPage", "car");

  initializeTabs();
  initializeEventListeners();
  loadCustomers();
  loadCars();
});

// Tab functionality
function initializeTabs() {
  const tabButtons = document.querySelectorAll(".tab-button");
  const tabContents = document.querySelectorAll(".tab-content");

  tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const targetTab = button.getAttribute("data-tab");

      // Update active tab button
      tabButtons.forEach((btn) => btn.classList.remove("active"));
      button.classList.add("active");

      // Update active tab content
      tabContents.forEach((content) => content.classList.remove("active"));
      document.getElementById(`${targetTab}-tab`).classList.add("active");
    });
  });
}

// Event listeners
function initializeEventListeners() {
  // Car modal events
  document
    .getElementById("add-car-btn")
    .addEventListener("click", () => openCarModal());
  document
    .getElementById("close-car-modal")
    .addEventListener("click", closeCarModal);
  document
    .getElementById("cancel-car")
    .addEventListener("click", closeCarModal);
  carForm.addEventListener("submit", handleCarSubmit);

  // Customer modal events
  document
    .getElementById("add-customer-btn")
    .addEventListener("click", () => openCustomerModal());
  document
    .getElementById("close-customer-modal")
    .addEventListener("click", closeCustomerModal);
  document
    .getElementById("cancel-customer")
    .addEventListener("click", closeCustomerModal);
  customerForm.addEventListener("submit", handleCustomerSubmit);

  // Customer cars modal events
  document
    .getElementById("close-customer-cars-modal")
    .addEventListener("click", closeCustomerCarsModal);

  // Search events
  document
    .getElementById("car-search-btn")
    .addEventListener("click", () => searchCars());
  document
    .getElementById("customer-search-btn")
    .addEventListener("click", () => searchCustomers());

  // Modal backdrop clicks
  carModal.addEventListener("click", (e) => {
    if (e.target === carModal) closeCarModal();
  });

  customerModal.addEventListener("click", (e) => {
    if (e.target === customerModal) closeCustomerModal();
  });

  customerCarsModal.addEventListener("click", (e) => {
    if (e.target === customerCarsModal) closeCustomerCarsModal();
  });

  // Search input enter key
  carSearchInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") searchCars();
  });

  customerSearchInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") searchCustomers();
  });
}

// API Functions - Cars
async function loadCars() {
  try {
    showLoading("cars-tbody");
    const response = await fetch("/api/cars");
    const data = await response.json();

    if (response.ok) {
      cars = data;
      renderCarsTable(cars);
    } else {
      showError("Failed to load cars: " + data.error);
    }
  } catch (error) {
    showError("Error loading cars: " + error.message);
  }
}

async function createCar(carData) {
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
      showSuccess("Car created successfully");
      closeCarModal();
      loadCars();
    } else {
      showError(
        "Failed to create car: " +
          (data.details ? data.details.join(", ") : data.error)
      );
    }
  } catch (error) {
    showError("Error creating car: " + error.message);
  }
}

async function updateCar(carId, carData) {
  try {
    const response = await fetch(`/api/cars/${carId}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(carData),
    });

    const data = await response.json();

    if (response.ok) {
      showSuccess("Car updated successfully");
      closeCarModal();
      loadCars();
    } else {
      showError(
        "Failed to update car: " +
          (data.details ? data.details.join(", ") : data.error)
      );
    }
  } catch (error) {
    showError("Error updating car: " + error.message);
  }
}

async function deleteCar(carId) {
  if (!confirm("Are you sure you want to delete this car?")) return;

  try {
    const response = await fetch(`/api/cars/${carId}`, {
      method: "DELETE",
    });

    const data = await response.json();

    if (response.ok) {
      showSuccess("Car deleted successfully");
      loadCars();
    } else {
      showError("Failed to delete car: " + data.error);
    }
  } catch (error) {
    showError("Error deleting car: " + error.message);
  }
}

async function searchCars() {
  const query = carSearchInput.value.trim();
  if (!query) {
    loadCars();
    return;
  }

  try {
    showLoading("cars-tbody");
    const response = await fetch(
      `/api/cars/search?q=${encodeURIComponent(query)}`
    );
    const data = await response.json();

    if (response.ok) {
      cars = data.results;
      renderCarsTable(cars);
    } else {
      showError("Failed to search cars: " + data.error);
    }
  } catch (error) {
    showError("Error searching cars: " + error.message);
  }
}

// API Functions - Customers
async function loadCustomers() {
  try {
    showLoading("customers-tbody");
    const response = await fetch("/api/customers");
    const data = await response.json();

    if (response.ok) {
      customers = data;
      renderCustomersTable(customers);
      updateCustomerSelect();
    } else {
      showError("Failed to load customers: " + data.error);
    }
  } catch (error) {
    showError("Error loading customers: " + error.message);
  }
}

async function createCustomer(customerData) {
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
      showSuccess("Customer created successfully");
      closeCustomerModal();
      loadCustomers();
    } else {
      showError(
        "Failed to create customer: " +
          (data.details ? data.details.join(", ") : data.error)
      );
    }
  } catch (error) {
    showError("Error creating customer: " + error.message);
  }
}

async function updateCustomer(customerId, customerData) {
  try {
    const response = await fetch(`/api/customers/${customerId}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(customerData),
    });

    const data = await response.json();

    if (response.ok) {
      showSuccess("Customer updated successfully");
      closeCustomerModal();
      loadCustomers();
    } else {
      showError(
        "Failed to update customer: " +
          (data.details ? data.details.join(", ") : data.error)
      );
    }
  } catch (error) {
    showError("Error updating customer: " + error.message);
  }
}

async function deleteCustomer(customerId) {
  if (
    !confirm(
      "Are you sure you want to delete this customer? This will also delete all associated cars."
    )
  )
    return;

  try {
    const response = await fetch(`/api/customers/${customerId}`, {
      method: "DELETE",
    });

    const data = await response.json();

    if (response.ok) {
      showSuccess("Customer deleted successfully");
      loadCustomers();
      loadCars(); // Reload cars as some might have been deleted
    } else {
      showError("Failed to delete customer: " + data.error);
    }
  } catch (error) {
    showError("Error deleting customer: " + error.message);
  }
}

async function searchCustomers() {
  const query = customerSearchInput.value.trim();
  if (!query) {
    loadCustomers();
    return;
  }

  try {
    showLoading("customers-tbody");
    const response = await fetch(
      `/api/customers/search?q=${encodeURIComponent(query)}`
    );
    const data = await response.json();

    if (response.ok) {
      customers = data.results;
      renderCustomersTable(customers);
    } else {
      showError("Failed to search customers: " + data.error);
    }
  } catch (error) {
    showError("Error searching customers: " + error.message);
  }
}

async function loadCustomerCars(customerId) {
  try {
    const response = await fetch(`/api/cars/customer/${customerId}`);
    const data = await response.json();

    if (response.ok) {
      renderCustomerCarsModal(data);
    } else {
      showError("Failed to load customer cars: " + data.error);
    }
  } catch (error) {
    showError("Error loading customer cars: " + error.message);
  }
}

// Render Functions
function renderCarsTable(carsData) {
  const tbody = document.getElementById("cars-tbody");

  if (carsData.length === 0) {
    tbody.innerHTML = `
            <tr>
                <td colspan="9" class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M19 17H5C3.89543 17 3 16.1046 3 15V7C3 5.89543 3.89543 5 5 5H19C20.1046 5 21 5.89543 21 7V15C21 16.1046 20.1046 17 19 17Z" stroke="currentColor" stroke-width="2"/>
                        <path d="M7 9H17M7 13H13" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                    <h3>No cars found</h3>
                    <p>Add your first car to get started</p>
                </td>
            </tr>
        `;
    return;
  }

  tbody.innerHTML = carsData
    .map(
      (car) => `
        <tr>
            <td>${escapeHtml(car.make)}</td>
            <td>${escapeHtml(car.model)}</td>
            <td>${escapeHtml(car.plate_no)}</td>
            <td>${escapeHtml(car.mileage)}</td>
            <td>${escapeHtml(car.vin || "-")}</td>
            <td>${escapeHtml(car.color || "-")}</td>
            <td>${escapeHtml(car.chasis_no || "-")}</td>
            <td>${escapeHtml(car.customer_name)}</td>
            <td>
                <div class="action-buttons">
                    <button class="btn-edit" onclick="editCar(${
                      car.id
                    })">Edit</button>
                    <button class="btn-delete" onclick="deleteCar(${
                      car.id
                    })">Delete</button>
                </div>
            </td>
        </tr>
    `
    )
    .join("");
}

function renderCustomersTable(customersData) {
  const tbody = document.getElementById("customers-tbody");

  if (customersData.length === 0) {
    tbody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M20 21V19C20 17.9391 19.5786 16.9217 18.8284 16.1716C18.0783 15.4214 17.0609 15 16 15H8C6.93913 15 5.92172 15.4214 5.17157 16.1716C4.42143 16.9217 4 17.9391 4 19V21" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        <circle cx="12" cy="7" r="4" stroke="currentColor" stroke-width="2"/>
                    </svg>
                    <h3>No customers found</h3>
                    <p>Add your first customer to get started</p>
                </td>
            </tr>
        `;
    return;
  }

  tbody.innerHTML = customersData
    .map(
      (customer) => `
        <tr>
            <td>${escapeHtml(customer.name)}</td>
            <td>${escapeHtml(customer.phone)}</td>
            <td>${escapeHtml(customer.address)}</td>
            <td>
                <button class="btn-view" onclick="viewCustomerCars(${
                  customer.id
                })">View Cars</button>
            </td>
            <td>
                <div class="action-buttons">
                    <button class="btn-edit" onclick="editCustomer(${
                      customer.id
                    })">Edit</button>
                    <button class="btn-delete" onclick="deleteCustomer(${
                      customer.id
                    })">Delete</button>
                </div>
            </td>
        </tr>
    `
    )
    .join("");
}

function renderCustomerCarsModal(data) {
  const { customer, cars } = data;

  document.getElementById("customer-cars-title").textContent = "Customer Cars";
  document.getElementById("customer-cars-name").textContent = customer.name;
  document.getElementById("customer-cars-phone").textContent = customer.phone;
  document.getElementById("customer-cars-address").textContent =
    customer.address;

  const tbody = document.getElementById("customer-cars-tbody");

  if (cars.length === 0) {
    tbody.innerHTML = `
            <tr>
                <td colspan="8" class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M19 17H5C3.89543 17 3 16.1046 3 15V7C3 5.89543 3.89543 5 5 5H19C20.1046 5 21 5.89543 21 7V15C21 16.1046 20.1046 17 19 17Z" stroke="currentColor" stroke-width="2"/>
                        <path d="M7 9H17M7 13H13" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                    <h3>No cars found</h3>
                    <p>This customer has no cars registered</p>
                </td>
            </tr>
        `;
  } else {
    tbody.innerHTML = cars
      .map(
        (car) => `
            <tr>
                <td>${escapeHtml(car.make)}</td>
                <td>${escapeHtml(car.model)}</td>
                <td>${escapeHtml(car.plate_no)}</td>
                <td>${escapeHtml(car.mileage)}</td>
                <td>${escapeHtml(car.vin || "-")}</td>
                <td>${escapeHtml(car.color || "-")}</td>
                <td>${escapeHtml(car.chasis_no || "-")}</td>
                <td>
                    <div class="action-buttons">
                        <button class="btn-edit" onclick="editCar(${
                          car.id
                        })">Edit</button>
                        <button class="btn-delete" onclick="deleteCar(${
                          car.id
                        })">Delete</button>
                    </div>
                </td>
            </tr>
        `
      )
      .join("");
  }

  customerCarsModal.classList.add("active");
}

// Modal Functions
function openCarModal(carId = null) {
  currentCarId = carId;
  const title = carId ? "Edit Car" : "Add Car";
  document.getElementById("car-modal-title").textContent = title;

  if (carId) {
    const car = cars.find((c) => c.id === carId);
    if (car) {
      document.getElementById("car-make").value = car.make;
      document.getElementById("car-model").value = car.model;
      document.getElementById("car-plate").value = car.plate_no;
      document.getElementById("car-mileage").value = car.mileage;
      document.getElementById("car-vin").value = car.vin || "";
      document.getElementById("car-color").value = car.color || "";
      document.getElementById("car-chasis").value = car.chasis_no || "";
      document.getElementById("car-customer").value = car.customer_id;
    }
  } else {
    carForm.reset();
  }

  carModal.classList.add("active");
}

function closeCarModal() {
  carModal.classList.remove("active");
  currentCarId = null;
  carForm.reset();
}

function openCustomerModal(customerId = null) {
  currentCustomerId = customerId;
  const title = customerId ? "Edit Customer" : "Add Customer";
  document.getElementById("customer-modal-title").textContent = title;

  if (customerId) {
    const customer = customers.find((c) => c.id === customerId);
    if (customer) {
      document.getElementById("customer-name").value = customer.name;
      document.getElementById("customer-phone").value = customer.phone;
      document.getElementById("customer-address").value = customer.address;
    }
  } else {
    customerForm.reset();
  }

  customerModal.classList.add("active");
}

function closeCustomerModal() {
  customerModal.classList.remove("active");
  currentCustomerId = null;
  customerForm.reset();
}

function closeCustomerCarsModal() {
  customerCarsModal.classList.remove("active");
}

// Form Handlers
function handleCarSubmit(e) {
  e.preventDefault();

  const carData = {
    make: document.getElementById("car-make").value.trim(),
    model: document.getElementById("car-model").value.trim(),
    plate_no: document.getElementById("car-plate").value.trim(),
    mileage: document.getElementById("car-mileage").value.trim(),
    vin: document.getElementById("car-vin").value.trim() || null,
    color: document.getElementById("car-color").value.trim() || null,
    chasis_no: document.getElementById("car-chasis").value.trim() || null,
    customer_id: parseInt(document.getElementById("car-customer").value),
  };

  if (currentCarId) {
    updateCar(currentCarId, carData);
  } else {
    createCar(carData);
  }
}

function handleCustomerSubmit(e) {
  e.preventDefault();

  const customerData = {
    name: document.getElementById("customer-name").value.trim(),
    phone: document.getElementById("customer-phone").value.trim(),
    address: document.getElementById("customer-address").value.trim(),
  };

  if (currentCustomerId) {
    updateCustomer(currentCustomerId, customerData);
  } else {
    createCustomer(customerData);
  }
}

// Action Functions
function editCar(carId) {
  openCarModal(carId);
}

function editCustomer(customerId) {
  openCustomerModal(customerId);
}

function viewCustomerCars(customerId) {
  loadCustomerCars(customerId);
}

// Utility Functions
function updateCustomerSelect() {
  const select = document.getElementById("car-customer");
  const currentValue = select.value;

  select.innerHTML = '<option value="">Select Customer</option>';
  customers.forEach((customer) => {
    const option = document.createElement("option");
    option.value = customer.id;
    option.textContent = customer.name;
    select.appendChild(option);
  });

  if (currentValue) {
    select.value = currentValue;
  }
}

function showLoading(elementId) {
  document.getElementById(elementId).innerHTML = `
        <tr>
            <td colspan="6" class="loading">Loading...</td>
        </tr>
    `;
}

function showSuccess(message) {
  // Simple success notification
  alert(message);
}

function showError(message) {
  // Simple error notification
  alert("Error: " + message);
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
