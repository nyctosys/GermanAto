// Global variables
let currentEditId = null;
let inventoryItems = [];
let currentPage = 1;
let totalPages = 1;
let isLoading = false;

// Fallback PerformanceUtils if not available
const FallbackUtils = {
  showLoading: (elementId, message = "Loading...") => {
    const element = document.getElementById(elementId);
    if (element) {
      element.innerHTML = `<div style="text-align: center; padding: 2rem;">${message}</div>`;
    }
  },
  hideLoading: (elementId) => {
    const element = document.getElementById(elementId);
    if (element && element.innerHTML.includes("Loading")) {
      element.innerHTML = "";
    }
  },
  showError: (elementId, message, retryCallback = null) => {
    const element = document.getElementById(elementId);
    if (element) {
      element.innerHTML = `
        <div style="text-align: center; padding: 2rem; color: #dc3545;">
          <div style="font-size: 2rem; margin-bottom: 1rem;">⚠️</div>
          <div>${message}</div>
          ${
            retryCallback
              ? `<button onclick="${retryCallback.name}()" style="background: #007bff; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; margin-top: 1rem;">Retry</button>`
              : ""
          }
        </div>
      `;
    }
  },
  fetchWithRetry: async (url, options = {}) => {
    const response = await fetch(url, options);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json();
  },
};

// Initialize the page
document.addEventListener("DOMContentLoaded", function () {
  // Set up smart back button logic
  const backBtn = document.getElementById("back-btn");
  const urlParams = new URLSearchParams(window.location.search);
  const fromPage =
    urlParams.get("from") || localStorage.getItem("lastPage") || "home";

  // Set back button destination based on where user came from
  if (fromPage === "admin") {
    backBtn.href = "admin.html";
  } else if (fromPage === "home") {
    backBtn.href = "home.html";
  } else if (fromPage === "invoiceSystem") {
    backBtn.href = "invoiceSystem.html";
  } else {
    backBtn.href = "home.html"; // Default fallback to home instead of admin
  }

  // Track current page for back button logic
  localStorage.setItem("lastPage", "inventory");

  loadInventory();
  setupEventListeners();
  setupPagination();
});

// Setup event listeners
function setupEventListeners() {
  // Form submission
  document
    .getElementById("item-form")
    .addEventListener("submit", handleFormSubmit);

  // Restock form submission
  document
    .getElementById("restock-form")
    .addEventListener("submit", handleRestockSubmit);

  // Search input with debounced search
  const searchInput = document.getElementById("search-input");
  if (searchInput) {
    let searchTimeout;
    const debouncedSearch = () => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(searchInventory, 500);
    };

    searchInput.addEventListener("keyup", function (e) {
      if (e.key === "Enter") {
        searchInventory();
      } else {
        debouncedSearch();
      }
    });
  }

  // Modal close on outside click
  document.getElementById("item-modal").addEventListener("click", function (e) {
    if (e.target === this) {
      closeModal();
    }
  });

  // Restock modal close on outside click
  document
    .getElementById("restock-modal")
    .addEventListener("click", function (e) {
      if (e.target === this) {
        closeRestockModal();
      }
    });
}

// Load inventory items with pagination and performance optimization
async function loadInventory(page = 1, search = "") {
  if (isLoading) return;

  isLoading = true;

  // Get utils once at the beginning of the function
  const utils = window.PerformanceUtils || FallbackUtils;

  try {
    // Show loading state
    utils.showLoading("inventory-grid", "Loading inventory...");

    // Build URL with pagination and search parameters
    const params = new URLSearchParams({
      page: page,
      per_page: 50,
      search: search,
    });

    // Use PerformanceUtils if available, otherwise use fallback
    const data = await utils.fetchWithRetry(
      `/api/inventory?${params.toString()}`
    );

    if (data.items) {
      // Handle paginated response
      inventoryItems = data.items;
      currentPage = data.pagination.page;
      totalPages = data.pagination.pages;

      renderInventory();
      updatePaginationControls();
    } else {
      // Handle legacy response format
      inventoryItems = data;
      renderInventory();
    }
  } catch (error) {
    console.error("Error loading inventory:", error);
    utils.showError(
      "inventory-grid",
      "Failed to load inventory. Please try again.",
      () => loadInventory(currentPage, search)
    );
  } finally {
    isLoading = false;
    utils.hideLoading("inventory-grid");
  }
}

// Setup pagination controls
function setupPagination() {
  // Add pagination controls to the page
  const inventoryContainer = document.querySelector(".inventory-container");
  if (inventoryContainer && !document.getElementById("pagination-controls")) {
    const paginationHTML = `
      <div id="pagination-controls" class="pagination-controls" style="
        display: flex;
        justify-content: center;
        align-items: center;
        margin: 1rem 0;
        gap: 0.5rem;
      ">
        <button id="prev-page" class="btn btn-sm btn-outline-primary" disabled>
          ← Previous
        </button>
        <span id="page-info" class="page-info">
          Page 1 of 1
        </span>
        <button id="next-page" class="btn btn-sm btn-outline-primary" disabled>
          Next →
        </button>
      </div>
    `;

    inventoryContainer.insertAdjacentHTML("beforeend", paginationHTML);

    // Add event listeners
    document.getElementById("prev-page").addEventListener("click", () => {
      if (currentPage > 1) {
        loadInventory(currentPage - 1, getCurrentSearch());
      }
    });

    document.getElementById("next-page").addEventListener("click", () => {
      if (currentPage < totalPages) {
        loadInventory(currentPage + 1, getCurrentSearch());
      }
    });
  }
}

// Update pagination controls
function updatePaginationControls() {
  const prevBtn = document.getElementById("prev-page");
  const nextBtn = document.getElementById("next-page");
  const pageInfo = document.getElementById("page-info");

  if (prevBtn) {
    prevBtn.disabled = currentPage <= 1;
  }

  if (nextBtn) {
    nextBtn.disabled = currentPage >= totalPages;
  }

  if (pageInfo) {
    pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
  }
}

// Get current search term
function getCurrentSearch() {
  const searchInput = document.getElementById("search-input");
  return searchInput ? searchInput.value.trim() : "";
}

// Load sample data for demonstration
function loadSampleData() {
  inventoryItems = [
    {
      id: 1,
      name: "Engine Oil Filter",
      category: "parts",
      quantity: 25,
      price: 450.0,
      description: "High-quality engine oil filter for various car models",
      location: "Shelf A1",
      reorder_level: 5,
      reorder_quantity: 20,
    },
    {
      id: 2,
      name: "Brake Pads Set",
      category: "parts",
      quantity: 12,
      price: 1200.0,
      description: "Front brake pads set for sedan vehicles",
      location: "Shelf B2",
      reorder_level: 3,
      reorder_quantity: 15,
    },
    {
      id: 3,
      name: "Air Filter",
      category: "parts",
      quantity: 2, // Low stock
      price: 350.0,
      description: "Engine air filter for improved performance",
      location: "Shelf A3",
      reorder_level: 5,
      reorder_quantity: 25,
    },
    {
      id: 4,
      name: "Transmission Fluid",
      category: "fluids",
      quantity: 0, // Out of stock
      price: 800.0,
      description: "High-quality transmission fluid",
      location: "Shelf C1",
      reorder_level: 3,
      reorder_quantity: 10,
    },
    {
      id: 5,
      name: "Spark Plugs",
      category: "parts",
      quantity: 4, // Low stock
      price: 250.0,
      description: "Iridium spark plugs for better ignition",
      location: "Shelf A2",
      reorder_level: 5,
      reorder_quantity: 30,
    },
    {
      id: 6,
      name: "Socket Wrench Set",
      category: "tools",
      quantity: 8,
      price: 2500.0,
      description: "Complete socket wrench set with 32 pieces",
      location: "Tool Cabinet C1",
      reorder_level: 2,
      reorder_quantity: 5,
    },
    {
      id: 7,
      name: "Motor Oil 5W-30",
      category: "fluids",
      quantity: 30,
      price: 800.0,
      description: "Synthetic motor oil 5W-30, 1L bottles",
      location: "Fluid Storage D1",
      reorder_level: 5,
      reorder_quantity: 20,
    },
  ];
  renderInventory();
}

// Render inventory items grouped by category with collapsible sections
function renderInventory() {
  const grid = document.getElementById("inventory-grid");
  grid.innerHTML = "";

  if (inventoryItems.length === 0) {
    grid.innerHTML = `
            <div class="empty-state">
                <h3>No inventory items found</h3>
                <p>Click "Add New Item" to get started</p>
            </div>
        `;
    return;
  }

  // Group items by category
  const groupedItems = groupItemsByCategory(inventoryItems);

  // Define category order for consistent display
  const categoryOrder = ["parts", "tools", "fluids", "accessories", "other"];

  // Render each category section
  categoryOrder.forEach((category) => {
    if (groupedItems[category] && groupedItems[category].length > 0) {
      // Create category wrapper
      const categoryWrapper = document.createElement("div");
      categoryWrapper.className = "category-wrapper";
      categoryWrapper.setAttribute("data-category-wrapper", category);

      // Create category section header
      const categoryHeader = createCategoryHeader(
        category,
        groupedItems[category].length
      );
      categoryWrapper.appendChild(categoryHeader);

      // Create category container
      const categoryContainer = document.createElement("div");
      categoryContainer.className = "category-section";
      categoryContainer.setAttribute("data-category", category);

      // Add items to category container
      groupedItems[category].forEach((item) => {
        const itemElement = createInventoryItemElement(item);
        categoryContainer.appendChild(itemElement);
      });

      categoryWrapper.appendChild(categoryContainer);
      grid.appendChild(categoryWrapper);
    }
  });
}

// Create inventory item element
function createInventoryItemElement(item) {
  const div = document.createElement("div");
  div.className = "inventory-item";
  div.innerHTML = `
        <div class="item-header">
            <div class="item-image-container">
                ${
                  item.image_path
                    ? `<img src="/static/${item.image_path}" alt="${item.name}" class="item-image" onerror="this.style.display='none'">`
                    : `<div class="item-image-placeholder">📦</div>`
                }
            </div>
            <div class="item-info">
                <div class="item-id">${
                  item.part_number || `Product #${item.id}`
                }</div>
                <div class="item-name">${item.name}</div>
                <div class="item-category">${getCategoryDisplayName(
                  item.category
                )}</div>
            </div>
        </div>
        <div class="item-details">
            <div class="item-detail">
                <span>Quantity:</span>
                <span class="${
                  item.quantity <= (item.reorder_level || 5) ? "low-stock" : ""
                }">${item.quantity}</span>
            </div>
            <div class="item-detail">
                <span>Price:</span>
                <span>PKR ${item.price.toFixed(2)}</span>
            </div>
            <div class="item-detail">
                <span>Total Value:</span>
                <span>PKR ${(item.quantity * item.price).toFixed(2)}</span>
            </div>
            <div class="item-detail">
                <span>Reorder Level:</span>
                <span>${item.reorder_level || 5}</span>
            </div>
            <div class="item-detail">
                <span>Reorder Qty:</span>
                <span>${item.reorder_quantity || 10}</span>
            </div>
            ${
              item.location
                ? `
            <div class="item-detail">
                <span>Location:</span>
                <span>${item.location}</span>
            </div>
            `
                : ""
            }
        </div>
        ${
          item.description
            ? `
        <div class="item-description">
            <p>${item.description}</p>
        </div>
        `
            : ""
        } <br>
        <div class="item-actions">
            <button class="action-btn edit-btn" onclick="editItem(${
              item.id
            })">Edit</button>
            <button class="action-btn delete-btn" onclick="deleteItem(${
              item.id
            })">Delete</button>
        </div>
    `;
  return div;
}

// Get category display name
function getCategoryDisplayName(category) {
  const categories = {
    parts: "Auto Parts",
    tools: "Tools",
    fluids: "Fluids & Lubricants",
    accessories: "Accessories",
    other: "Other",
  };
  return categories[category] || category;
}

// Group items by category
function groupItemsByCategory(items) {
  const grouped = {};
  items.forEach((item) => {
    const category = item.category || "other";
    if (!grouped[category]) {
      grouped[category] = [];
    }
    grouped[category].push(item);
  });
  return grouped;
}

// Create category header element with collapsible functionality
function createCategoryHeader(category, itemCount) {
  const header = document.createElement("div");
  header.className = "category-header";
  header.innerHTML = `
    <div class="category-title" onclick="toggleCategory('${category}')">
      <div class="category-info">
        <div class="category-icon">${getCategoryIcon(category)}</div>
        <div class="category-details">
          <h3>${getCategoryDisplayName(category)}</h3>
          <span class="category-count">${itemCount} item${
    itemCount !== 1 ? "s" : ""
  }</span>
        </div>
      </div>
      <div class="category-toggle">
        <span class="toggle-icon">▼</span>
      </div>
    </div>
  `;
  return header;
}

// Get category icon
function getCategoryIcon(category) {
  const icons = {
    parts: "🔧",
    tools: "🛠️",
    fluids: "🛢️",
    accessories: "🎨",
    other: "📦",
  };
  return icons[category] || "📦";
}

// Toggle category section
function toggleCategory(category) {
  const categorySection = document.querySelector(
    `[data-category="${category}"]`
  );
  const toggleIcon = document.querySelector(
    `[onclick="toggleCategory('${category}')"] .toggle-icon`
  );

  if (categorySection.style.display === "none") {
    categorySection.style.display = "grid";
    toggleIcon.textContent = "▼";
    categorySection.parentElement.classList.remove("collapsed");
  } else {
    categorySection.style.display = "none";
    toggleIcon.textContent = "▶";
    categorySection.parentElement.classList.add("collapsed");
  }
}

// Open add modal
function openAddModal() {
  currentEditId = null;
  document.getElementById("modal-title").textContent = "Add New Item";
  document.getElementById("item-form").reset();

  // Reset image display
  const currentImageContainer = document.getElementById(
    "current-image-container"
  );
  const fileInput = document.getElementById("item-image");
  const removeImageFlag = document.getElementById("remove-image-flag");

  currentImageContainer.style.display = "none";
  fileInput.value = "";
  removeImageFlag.value = "false";

  document.getElementById("item-modal").style.display = "block";
}

// Open edit modal
function editItem(id) {
  const item = inventoryItems.find((item) => item.id === id);
  if (!item) return;

  currentEditId = id;
  document.getElementById("modal-title").textContent = "Edit Item";

  // Fill form with item data
  document.getElementById("item-name").value = item.name;
  document.getElementById("item-category").value = item.category;
  document.getElementById("item-quantity").value = item.quantity;
  document.getElementById("item-price").value = item.price;
  document.getElementById("item-description").value = item.description || "";
  document.getElementById("item-location").value = item.location || "";
  document.getElementById("item-reorder-level").value = item.reorder_level || 5;
  document.getElementById("item-reorder-quantity").value =
    item.reorder_quantity || 10;

  // Handle current image display
  const currentImageContainer = document.getElementById(
    "current-image-container"
  );
  const currentImagePreview = document.getElementById("current-image-preview");
  const removeImageFlag = document.getElementById("remove-image-flag");
  const fileInput = document.getElementById("item-image");

  if (item.image_path) {
    // Show current image
    currentImagePreview.src = `/static/${item.image_path}`;
    currentImageContainer.style.display = "block";
    removeImageFlag.value = "false";
  } else {
    // Hide current image section
    currentImageContainer.style.display = "none";
    removeImageFlag.value = "false";
  }

  // Clear file input
  fileInput.value = "";

  document.getElementById("item-modal").style.display = "block";
}

// Close modal
function closeModal() {
  document.getElementById("item-modal").style.display = "none";
  currentEditId = null;

  // Reset image display
  const currentImageContainer = document.getElementById(
    "current-image-container"
  );
  const fileInput = document.getElementById("item-image");
  const removeImageFlag = document.getElementById("remove-image-flag");

  currentImageContainer.style.display = "none";
  fileInput.value = "";
  removeImageFlag.value = "false";
}

// Preview new image when file is selected
function previewNewImage(input) {
  const currentImageContainer = document.getElementById(
    "current-image-container"
  );
  const currentImagePreview = document.getElementById("current-image-preview");
  const removeImageFlag = document.getElementById("remove-image-flag");

  if (input.files && input.files[0]) {
    const reader = new FileReader();
    reader.onload = function (e) {
      currentImagePreview.src = e.target.result;
      currentImageContainer.style.display = "block";
      removeImageFlag.value = "false"; // Reset remove flag when new image is selected
    };
    reader.readAsDataURL(input.files[0]);
  }
}

// Remove current image
function removeCurrentImage() {
  const currentImageContainer = document.getElementById(
    "current-image-container"
  );
  const fileInput = document.getElementById("item-image");
  const removeImageFlag = document.getElementById("remove-image-flag");

  currentImageContainer.style.display = "none";
  fileInput.value = ""; // Clear the file input
  removeImageFlag.value = "true"; // Set flag to remove image
}

// Open restock modal
function openRestockModal() {
  document.getElementById("restock-modal").style.display = "block";
  setupSearchableSelect();
}

// Close restock modal
function closeRestockModal() {
  document.getElementById("restock-modal").style.display = "none";
  document.getElementById("restock-form").reset();
  // Clear the search input and hidden field
  document.getElementById("restock-product-search").value = "";
  document.getElementById("restock-product").value = "";
}

// Setup searchable select functionality
function setupSearchableSelect() {
  const searchInput = document.getElementById("restock-product-search");
  const dropdown = document.getElementById("restock-product-dropdown");
  const hiddenInput = document.getElementById("restock-product");

  // Clear previous event listeners
  searchInput.removeEventListener("input", handleSearchInput);
  searchInput.removeEventListener("focus", handleSearchFocus);
  searchInput.removeEventListener("blur", handleSearchBlur);

  // Add event listeners
  searchInput.addEventListener("input", handleSearchInput);
  searchInput.addEventListener("focus", handleSearchFocus);
  searchInput.addEventListener("blur", handleSearchBlur);

  // Populate dropdown with all items initially
  populateSearchableDropdown(inventoryItems);
}

// Handle search input
function handleSearchInput(e) {
  const searchTerm = e.target.value.toLowerCase();
  const filteredItems = inventoryItems.filter(
    (item) =>
      item.name.toLowerCase().includes(searchTerm) ||
      (item.description &&
        item.description.toLowerCase().includes(searchTerm)) ||
      (item.part_number && item.part_number.toLowerCase().includes(searchTerm))
  );

  populateSearchableDropdown(filteredItems);
  showDropdown();
}

// Handle search focus
function handleSearchFocus() {
  showDropdown();
}

// Handle search blur
function handleSearchBlur() {
  // Delay hiding dropdown to allow for item selection
  setTimeout(() => {
    hideDropdown();
  }, 200);
}

// Show dropdown
function showDropdown() {
  const dropdown = document.getElementById("restock-product-dropdown");
  dropdown.style.display = "block";
}

// Hide dropdown
function hideDropdown() {
  const dropdown = document.getElementById("restock-product-dropdown");
  dropdown.style.display = "none";
}

// Populate searchable dropdown
function populateSearchableDropdown(items) {
  const dropdown = document.getElementById("restock-product-dropdown");
  const hiddenInput = document.getElementById("restock-product");

  dropdown.innerHTML = "";

  if (items.length === 0) {
    dropdown.innerHTML =
      '<div class="searchable-dropdown-item">No products found</div>';
    return;
  }

  items.forEach((item) => {
    const itemDiv = document.createElement("div");
    itemDiv.className = "searchable-dropdown-item";
    itemDiv.innerHTML = `
      <div class="product-name">${item.name}</div>
      <div class="product-details">
        Current Stock: ${item.quantity} | Category: ${item.category || "N/A"}
        ${item.part_number ? ` | Part #: ${item.part_number}` : ""}
      </div>
    `;

    itemDiv.addEventListener("click", () => {
      selectProduct(item, item.name);
    });

    dropdown.appendChild(itemDiv);
  });
}

// Select a product from the dropdown
function selectProduct(item, displayName) {
  const searchInput = document.getElementById("restock-product-search");
  const hiddenInput = document.getElementById("restock-product");
  const dropdown = document.getElementById("restock-product-dropdown");

  // Update the display and hidden input
  searchInput.value = displayName;
  hiddenInput.value = item.id;

  // Hide the dropdown
  hideDropdown();

  // Highlight the selected item in dropdown
  const items = dropdown.querySelectorAll(".searchable-dropdown-item");
  items.forEach((itemEl) => {
    itemEl.classList.remove("selected");
    if (itemEl.querySelector(".product-name").textContent === displayName) {
      itemEl.classList.add("selected");
    }
  });
}

// Populate restock product dropdown
function populateRestockProductDropdown() {
  // This function is no longer needed as we're using the searchable select
  // Keeping it for backward compatibility but it's not used
}

// Handle restock form submission
async function handleRestockSubmit(e) {
  e.preventDefault();

  const formData = new FormData(e.target);
  const productId = formData.get("product_id");
  const quantity = formData.get("quantity");
  const notes = formData.get("notes") || "";

  // Validate form data
  if (!productId || !quantity) {
    alert("Please select a product and enter the quantity to restock.");
    return;
  }

  if (parseInt(quantity) <= 0) {
    alert("Quantity must be greater than 0.");
    return;
  }

  const restockData = {
    product_id: parseInt(productId),
    quantity: parseInt(quantity),
    notes: notes,
  };

  // Get the submit button and show loading state
  const submitBtn = e.target.querySelector(".save-btn");
  const originalText = submitBtn.textContent;
  submitBtn.textContent = "Restocking...";
  submitBtn.disabled = true;

  try {
    // Call the restock API endpoint
    const response = await fetch("/api/inventory/restock", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(restockData),
    });

    if (response.ok) {
      const result = await response.json();

      // Show success message
      alert(
        `Successfully restocked ${result.quantity_added} units of ${result.product_name}.\n\nOld quantity: ${result.old_quantity}\nNew quantity: ${result.new_quantity}`
      );

      // Close modal and refresh inventory
      closeRestockModal();
      await loadInventory(); // Refresh the inventory display
    } else {
      const errorData = await response.json();
      alert(
        `Error restocking item: ${errorData.error || "Unknown error occurred"}`
      );
    }
  } catch (error) {
    console.error("Error restocking item:", error);
    alert("Error restocking item. Please check your connection and try again.");
  } finally {
    // Restore button state
    submitBtn.textContent = originalText;
    submitBtn.disabled = false;
  }
}

// Handle form submission
async function handleFormSubmit(e) {
  e.preventDefault();

  const formData = new FormData(e.target);

  try {
    if (currentEditId) {
      // Update existing item - send FormData for file upload support
      await updateInventoryItem(currentEditId, formData);
    } else {
      // Add new item - send FormData for file upload
      await addInventoryItem(formData);
    }

    // Only close modal and reload after successful API call
    closeModal();
    loadInventory();
  } catch (error) {
    console.error("Error saving item:", error);
    alert("Error saving item. Please try again.");
  }
}

// Add inventory item
async function addInventoryItem(itemData) {
  try {
    const response = await fetch("/api/inventory", {
      method: "POST",
      body: itemData, // FormData object
    });

    if (response.ok) {
      const result = await response.json();
      inventoryItems.push(result.item);
      return result.item;
    } else {
      const errorData = await response.json();
      throw new Error(errorData.error || "Failed to add item");
    }
  } catch (error) {
    console.error("Error adding item:", error);
    throw error;
  }
}

// Update inventory item
async function updateInventoryItem(id, formData) {
  try {
    const response = await fetch(`/api/inventory/${id}`, {
      method: "PUT",
      body: formData, // Send FormData directly for file upload support
    });

    if (response.ok) {
      const result = await response.json();
      const updatedItem = result.item;
      const index = inventoryItems.findIndex((item) => item.id === id);
      if (index !== -1) {
        inventoryItems[index] = updatedItem;
      }
      return updatedItem;
    } else {
      const errorText = await response.text();
      console.error("Update failed:", response.status, errorText);
      throw new Error("Failed to update item");
    }
  } catch (error) {
    console.error("Error updating item:", error);
    throw error;
  }
}

// Delete inventory item
async function deleteItem(id) {
  if (!confirm("Are you sure you want to delete this item?")) {
    return;
  }

  try {
    const response = await fetch(`/api/inventory/${id}`, {
      method: "DELETE",
    });

    if (response.ok) {
      inventoryItems = inventoryItems.filter((item) => item.id !== id);
      renderInventory();
    } else {
      throw new Error("Failed to delete item");
    }
  } catch (error) {
    // For demo purposes, remove from local array
    inventoryItems = inventoryItems.filter((item) => item.id !== id);
    renderInventory();
  }
}

// Search inventory with server-side search
function searchInventory() {
  const searchTerm = getCurrentSearch();

  // Reset to first page when searching
  currentPage = 1;

  // Load inventory with search term
  loadInventory(currentPage, searchTerm);
}

// Toggle low stock view
function toggleLowStockView() {
  const lowStockSection = document.getElementById("low-stock-section");
  const inventoryGrid = document.getElementById("inventory-grid");
  const lowStockBtn = document.querySelector(".low-stock-btn");

  if (lowStockSection.style.display === "none") {
    // Show low stock section
    lowStockSection.style.display = "block";
    inventoryGrid.style.display = "none";
    lowStockBtn.style.background =
      "linear-gradient(135deg, #28a745 0%, #20c997 100%)";
    lowStockBtn.innerHTML = "<span>📦</span> All Items";
    loadLowStockItems();
  } else {
    // Show all inventory
    lowStockSection.style.display = "none";
    inventoryGrid.style.display = "grid";
    lowStockBtn.style.background =
      "linear-gradient(135deg, #ff6b6b 0%, #ee5a52 100%)";
    lowStockBtn.innerHTML = "<span>⚠️</span> Low Stock Items";
  }
}

// Load low stock items
async function loadLowStockItems() {
  try {
    const response = await fetch("/api/inventory/low-stock");
    if (response.ok) {
      const data = await response.json();
      renderLowStockItems(data);
    } else {
      console.error("Failed to load low stock items");
      // Fallback: filter from current inventory
      const urgentItems = inventoryItems.filter((item) => item.quantity < 0);
      const lowStockItems = inventoryItems.filter(
        (item) => item.quantity <= item.reorder_level && item.quantity >= 0
      );
      renderLowStockItems({
        urgent_items: urgentItems,
        low_stock_items: lowStockItems,
      });
    }
  } catch (error) {
    console.error("Error loading low stock items:", error);
    // Fallback: filter from current inventory
    const urgentItems = inventoryItems.filter((item) => item.quantity < 0);
    const lowStockItems = inventoryItems.filter(
      (item) => item.quantity <= item.reorder_level && item.quantity >= 0
    );
    renderLowStockItems({
      urgent_items: urgentItems,
      low_stock_items: lowStockItems,
    });
  }
}

// Render low stock items
function renderLowStockItems(data) {
  const urgentGrid = document.getElementById("urgent-grid");
  const lowStockGrid = document.getElementById("low-stock-grid");

  const urgentItems = data.urgent_items || [];
  const lowStockItems = data.low_stock_items || [];

  // Render urgent items (negative stock)
  if (urgentItems.length === 0) {
    urgentGrid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 2rem; color: #155724;">
        <h3>✅ No Urgent Items!</h3>
        <p>No items with negative stock levels.</p>
      </div>
    `;
  } else {
    urgentGrid.innerHTML = urgentItems
      .map((item) => createLowStockItemElement(item, "urgent"))
      .join("");
  }

  // Render regular low stock items
  if (lowStockItems.length === 0) {
    lowStockGrid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 2rem; color: #856404;">
        <h3>🎉 No Low Stock Items!</h3>
        <p>All inventory items are above their reorder levels.</p>
      </div>
    `;
  } else {
    lowStockGrid.innerHTML = lowStockItems
      .map((item) => createLowStockItemElement(item, "low-stock"))
      .join("");
  }
}

// Create low stock item element
function createLowStockItemElement(item, urgencyLevel = "low-stock") {
  let stockStatus, statusText;

  if (urgencyLevel === "urgent") {
    stockStatus = "urgent";
    statusText = item.stock_status || "URGENT - Negative Stock";
  } else if (item.quantity === 0) {
    stockStatus = "out-of-stock";
    statusText = "Out of Stock";
  } else {
    stockStatus = "low-stock";
    statusText = "Low Stock";
  }

  return `
    <div class="low-stock-item">
      <div class="low-stock-item-header">
        <div>
          <div class="low-stock-item-name">${item.name}</div>
          <div class="low-stock-item-category">${getCategoryDisplayName(
            item.category
          )}</div>
          <div class="low-stock-item-part-number">${
            item.part_number || "No Part Number"
          }</div>
        </div>
        <div class="stock-status ${stockStatus}">${statusText}</div>
      </div>
      
      <div class="low-stock-item-details">
        <div class="low-stock-item-detail">
          <span>Current Stock:</span>
          <span>${item.quantity}</span>
        </div>
        <div class="low-stock-item-detail">
          <span>Reorder Level:</span>
          <span>${item.reorder_level}</span>
        </div>
        <div class="low-stock-item-detail">
          <span>Price:</span>
          <span>PKR ${item.price.toFixed(2)}</span>
        </div>
        ${
          item.location
            ? `
        <div class="low-stock-item-detail">
          <span>Location:</span>
          <span>${item.location}</span>
        </div>
        `
            : ""
        }
      </div>
      
      <div class="reorder-info">
        <h4>📋 Reorder Information</h4>
        <p><strong>Recommended Order:</strong> <span class="needed-quantity">${
          item.reorder_quantity
        }</span> units</p>
        <p><strong>Total Cost:</strong> PKR ${(
          item.reorder_quantity * item.price
        ).toFixed(2)}</p>
        ${
          item.description
            ? `<p><strong>Description:</strong> ${item.description}</p>`
            : ""
        }
      </div>
      
      <div class="item-actions" style="margin-top: 1rem;">
        <button class="action-btn edit-btn" onclick="editItem(${item.id})">
          Edit Item
        </button>
        <button class="action-btn delete-btn" onclick="deleteItem(${item.id})">
          Delete
        </button>
      </div>
    </div>
  `;
}

// Open print sheet for low stock items
async function openPrintSheet() {
  try {
    // Fetch latest low stock items from server
    const response = await fetch("/api/inventory/low-stock");
    if (response.ok) {
      const lowStockItems = await response.json();
      sessionStorage.setItem("lowStockItems", JSON.stringify(lowStockItems));
    } else {
      // Fallback to current inventory data
      const lowStockItems = inventoryItems.filter(
        (item) => item.quantity <= item.reorder_level
      );
      sessionStorage.setItem("lowStockItems", JSON.stringify(lowStockItems));
    }

    // Open print sheet in same window
    window.location.href = "low-stock-print.html";
  } catch (error) {
    console.error("Error fetching low stock items:", error);
    // Fallback to current inventory data
    const lowStockItems = inventoryItems.filter(
      (item) => item.quantity <= item.reorder_level
    );
    sessionStorage.setItem("lowStockItems", JSON.stringify(lowStockItems));
    window.location.href = "low-stock-print.html";
  }
}
