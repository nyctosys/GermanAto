// Global variables
let currentEditId = null;
let inventoryItems = [];
let currentPage = 1;
let totalPages = 1;
let isLoading = false;
let searchTimeout = null;

// Default category order for stable display (known categories first)
const DEFAULT_CATEGORY_ORDER = ["parts", "tools", "fluids", "accessories", "other"];

// Category pagination state
let categoryPagination = {
  parts: { page: 1, totalPages: 1, hasMore: false, items: [], totalItems: 0 },
  tools: { page: 1, totalPages: 1, hasMore: false, items: [], totalItems: 0 },
  fluids: { page: 1, totalPages: 1, hasMore: false, items: [], totalItems: 0 },
  accessories: {
    page: 1,
    totalPages: 1,
    hasMore: false,
    items: [],
    totalItems: 0,
  },
  other: { page: 1, totalPages: 1, hasMore: false, items: [], totalItems: 0 },
};

// Dynamic list of categories to load/render (from API; includes any category that has items)
let inventoryCategoryOrder = [...DEFAULT_CATEGORY_ORDER];

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
          <div style="font-size: 2rem; margin-bottom: 1rem;"></div>
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
    // Use APIHelper for proper JWT authentication
    return await APIHelper.get(url);
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
  loadCategories();
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

// Fetch distinct categories from API and ensure categoryPagination has an entry for each
async function ensureCategoryList() {
  try {
    const data = await APIHelper.get("/api/inventory/categories");
    const apiCategories = (data && data.categories) ? data.categories : [];
    // Merge: default order first, then any API categories not in the list
    const merged = [...DEFAULT_CATEGORY_ORDER];
    apiCategories.forEach((c) => {
      if (c && !merged.includes(c)) merged.push(c);
    });
    inventoryCategoryOrder = merged;
    // Ensure categoryPagination has a slot for every category we might load
    inventoryCategoryOrder.forEach((cat) => {
      if (!categoryPagination[cat]) {
        categoryPagination[cat] = {
          page: 1,
          totalPages: 1,
          hasMore: false,
          items: [],
          totalItems: 0,
        };
      }
    });
  } catch (e) {
    inventoryCategoryOrder = [...DEFAULT_CATEGORY_ORDER];
  }
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

    if (search && search.trim()) {
      // Use grouped search for better performance when searching
      await loadInventoryWithSearch(search);
    } else {
      // Use dynamic category list from API so new categories are loaded
      await ensureCategoryList();
      for (const category of inventoryCategoryOrder) {
        await loadInventoryByCategory(category, 1, search);
      }
    }

    // Render all categories after loading
    renderInventory();
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

// Load inventory with search using grouped search endpoint
async function loadInventoryWithSearch(search) {
  // Get utils once at the beginning of the function
  const utils = window.PerformanceUtils || FallbackUtils;

  try {
    // Call the grouped search endpoint
    const data = await utils.fetchWithRetry(
      `/api/inventory/search-grouped?q=${encodeURIComponent(search)}`
    );

    if (data && data.results) {
      // Clear all category pagination states
      Object.keys(categoryPagination).forEach((category) => {
        categoryPagination[category] = {
          page: 1,
          totalPages: 1,
          hasMore: false,
          items: [],
          totalItems: 0,
        };
      });

      // Populate category pagination with search results (create slot for new categories)
      Object.keys(data.results).forEach((category) => {
        if (!categoryPagination[category]) {
          categoryPagination[category] = {
            page: 1,
            totalPages: 1,
            hasMore: false,
            items: [],
            totalItems: 0,
          };
          if (!inventoryCategoryOrder.includes(category)) {
            inventoryCategoryOrder.push(category);
          }
        }
        categoryPagination[category].items = data.results[category];
        categoryPagination[category].totalItems = data.results[category].length;
      });
    }
  } catch (error) {
    console.error("Error searching inventory:", error);
    throw error;
  }
}

// Load inventory items by category with pagination
async function loadInventoryByCategory(category, page = 1, search = "") {
  // Get utils once at the beginning of the function
  const utils = window.PerformanceUtils || FallbackUtils;

  try {
    // Build URL with pagination and search parameters
    const params = new URLSearchParams({
      page: page,
      per_page: 50,
      search: search,
      category: category,
    });

    // Use PerformanceUtils if available, otherwise use fallback
    const data = await utils.fetchWithRetry(
      `/api/inventory/by-category?${params.toString()}`
    );

    if (data.items) {
      // Update category pagination state
      categoryPagination[category].page = data.pagination.page;
      categoryPagination[category].totalPages = data.pagination.pages;
      categoryPagination[category].hasMore = data.pagination.has_next;
      categoryPagination[category].totalItems = data.pagination.total;

      // If it's the first page, replace items; otherwise append
      if (page === 1) {
        categoryPagination[category].items = data.items;
        // Re-render the entire category section for first page
        renderCategorySection(category);
      } else {
        // For subsequent pages, just append new items
        const newItems = data.items;
        categoryPagination[category].items = [
          ...categoryPagination[category].items,
          ...newItems,
        ];

        // Append new items to existing category section
        appendNewItemsToCategory(category, newItems);
      }
    }
  } catch (error) {
    console.error(`Error loading inventory for category ${category}:`, error);
    utils.showError(
      "inventory-grid",
      `Failed to load ${category} inventory. Please try again.`,
      () => loadInventoryByCategory(category, page, search)
    );
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
      description: "High-quality engine oil filter for various car models",
      location: "Shelf A1",
      reorder_level: 5,
    },
    {
      id: 2,
      name: "Brake Pads Set",
      category: "parts",
      quantity: 12,
      description: "Front brake pads set for sedan vehicles",
      location: "Shelf B2",
      reorder_level: 3,
    },
    {
      id: 3,
      name: "Air Filter",
      category: "parts",
      quantity: 2, // Low stock
      description: "Engine air filter for improved performance",
      location: "Shelf A3",
      reorder_level: 5,
    },
    {
      id: 4,
      name: "Transmission Fluid",
      category: "fluids",
      quantity: 0, // Out of stock
      description: "High-quality transmission fluid",
      location: "Shelf C1",
      reorder_level: 3,
    },
    {
      id: 5,
      name: "Spark Plugs",
      category: "parts",
      quantity: 4, // Low stock
      description: "Iridium spark plugs for better ignition",
      location: "Shelf A2",
      reorder_level: 5,
    },
    {
      id: 6,
      name: "Socket Wrench Set",
      category: "tools",
      quantity: 8,
      description: "Complete socket wrench set with 32 pieces",
      location: "Tool Cabinet C1",
      reorder_level: 2,
    },
    {
      id: 7,
      name: "Motor Oil 5W-30",
      category: "fluids",
      quantity: 30,
      description: "Synthetic motor oil 5W-30, 1L bottles",
      location: "Fluid Storage D1",
      reorder_level: 5,
    },
  ];
  renderInventory();
}

// Render inventory items grouped by category with collapsible sections
function renderInventory() {
  const grid = document.getElementById("inventory-grid");
  grid.innerHTML = "";

  // Check if we have any items in any category
  const hasAnyItems = Object.values(categoryPagination).some(
    (cat) => cat.items.length > 0
  );

  if (!hasAnyItems) {
    grid.innerHTML = `
            <div class="empty-state">
                <h3>No inventory items found</h3>
                <p>Click "Add New Item" to get started</p>
            </div>
        `;
    return;
  }

  // Use dynamic category order so new categories are rendered
  const categoryOrder = inventoryCategoryOrder;

  // Render each category section
  categoryOrder.forEach((category) => {
    const categoryData = categoryPagination[category];
    if (categoryData && categoryData.items && categoryData.items.length > 0) {
      renderCategorySection(category);
    }
  });
}

// Render a specific category section
function renderCategorySection(category) {
  const grid = document.getElementById("inventory-grid");

  // Remove existing category wrapper if it exists
  const existingWrapper = document.querySelector(
    `[data-category-wrapper="${category}"]`
  );
  if (existingWrapper) {
    existingWrapper.remove();
  }

  const categoryData = categoryPagination[category];
  if (!categoryData || !categoryData.items || categoryData.items.length === 0) {
    return;
  }

  // Create category wrapper
  const categoryWrapper = document.createElement("div");
  categoryWrapper.className = "category-wrapper collapsed"; // Collapsed by default
  categoryWrapper.setAttribute("data-category-wrapper", category);

  // Create category section header
  const categoryHeader = createCategoryHeader(
    category,
    categoryData.totalItems,
    categoryData.hasMore
  );
  categoryWrapper.appendChild(categoryHeader);

  // Create category container
  const categoryContainer = document.createElement("div");
  categoryContainer.className = "category-section";
  categoryContainer.setAttribute("data-category", category);

  // Add items to category container
  categoryData.items.forEach((item) => {
    const itemElement = createInventoryItemElement(item);
    categoryContainer.appendChild(itemElement);
  });

  // Add Show More button if there are more items
  if (categoryData.hasMore) {
    const showMoreButton = createShowMoreButton(category);
    categoryContainer.appendChild(showMoreButton);
  }

  categoryWrapper.appendChild(categoryContainer);
  grid.appendChild(categoryWrapper);
}

// Append new items to existing category section with smooth transition
function appendNewItemsToCategory(category, newItems) {
  const categoryContainer = document.querySelector(
    `[data-category="${category}"]`
  );

  if (!categoryContainer) {
    return;
  }

  // Remove existing Show More button if it exists
  const existingShowMore = categoryContainer.querySelector(
    ".show-more-container"
  );
  if (existingShowMore) {
    existingShowMore.remove();
  }

  // Add new items with staggered animation
  newItems.forEach((item, index) => {
    const itemElement = createInventoryItemElement(item);

    // Add staggered delay for smooth appearance
    itemElement.style.animationDelay = `${index * 0.1}s`;

    categoryContainer.appendChild(itemElement);
  });

  // Update Show More button if there are more items
  const categoryData = categoryPagination[category];
  if (categoryData.hasMore) {
    const showMoreButton = createShowMoreButton(category);
    categoryContainer.appendChild(showMoreButton);
  }

  // Update the category header count
  updateCategoryHeaderCount(category);

  // Reset any existing Show More button state
  const existingShowMoreBtn = categoryContainer.querySelector(".show-more-btn");
  if (existingShowMoreBtn) {
    existingShowMoreBtn.disabled = false;
    existingShowMoreBtn.textContent = "Show More";
  }
}

// Update category header count after loading more items
function updateCategoryHeaderCount(category) {
  const categoryData = categoryPagination[category];
  const categoryHeader = document.querySelector(
    `[data-category-wrapper="${category}"] .category-header`
  );

  if (!categoryHeader || !categoryData) {
    return;
  }

  const displayedItems = categoryData.items.length;
  const totalItems = categoryData.totalItems;
  const hasMore = categoryData.hasMore;

  let countText = `${totalItems} item${totalItems !== 1 ? "s" : ""}`;
  if (hasMore && displayedItems < totalItems) {
    countText += ` (showing ${displayedItems})`;
  }

  const countElement = categoryHeader.querySelector(".category-count");
  if (countElement) {
    countElement.textContent = countText;
  }
}

// Create inventory item element
function createInventoryItemElement(item) {
  const div = document.createElement("div");
  div.className = "inventory-item";
  const openingQuantity = Number(item.opening_quantity ?? item.quantity ?? 0);
  const purchasesQuantity = Number(item.purchases_quantity ?? 0);
  const salesQuantity = Number(item.sales_quantity ?? 0);
  const adjustmentsQuantity = Number(item.adjustments_quantity ?? 0);
  const closingQuantity = Number(item.closing_quantity ?? item.quantity ?? 0);
  const movementDate = item.movement_date || new Date().toISOString().slice(0, 10);

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
                <div class="item-category">${
                  item.barcode || item.manufacturer_part_number || ""
                }</div>
                <div class="item-movement-date">Today · ${movementDate}</div>
            </div>
        </div>
        <div class="item-details">
            <div class="item-detail">
                <span>Opening Qty:</span>
                <span>${openingQuantity}</span>
            </div>
            <div class="item-detail">
                <span>Purchases (issue in):</span>
                <span>${purchasesQuantity}</span>
            </div>
            <div class="item-detail">
                <span>Sales (issue out):</span>
                <span>${salesQuantity}</span>
            </div>
            <div class="item-detail">
                <span>Adjustments:</span>
                <span class="${
                  adjustmentsQuantity > 0 ? "adjustment-positive" : adjustmentsQuantity < 0 ? "adjustment-negative" : ""
                }">${adjustmentsQuantity > 0 ? "+" : ""}${adjustmentsQuantity}</span>
            </div>
            <div class="item-detail">
                <span>Closing Qty:</span>
                <span class="${
                  closingQuantity <= (item.reorder_level || 5) ? "low-stock" : ""
                }">${closingQuantity}</span>
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
            <button class="action-btn excel-btn" onclick="exportItemLedgerXlsx(${
              item.id
            })">Excel</button>
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
function createCategoryHeader(category, totalItems, hasMore = false) {
  const header = document.createElement("div");
  header.className = "category-header";

  // Get currently displayed items count
  const categoryData = categoryPagination[category];
  const displayedItems = categoryData ? categoryData.items.length : 0;

  // Create count text
  let countText = `${totalItems} item${totalItems !== 1 ? "s" : ""}`;
  if (hasMore && displayedItems < totalItems) {
    countText += ` (showing ${displayedItems})`;
  }

  header.innerHTML = `
    <div class="category-title" onclick="toggleCategory('${category}')">
      <div class="category-info">
        <div class="category-icon">${getCategoryIcon(category)}</div>
        <div class="category-details">
          <h3>${getCategoryDisplayName(category)}</h3>
          <span class="category-count">${countText}</span>
        </div>
      </div>
      <div class="category-toggle">
        <span class="toggle-icon">▶</span>
      </div>
    </div>
  `;
  return header;
}

// Create Show More button
function createShowMoreButton(category) {
  const buttonContainer = document.createElement("div");
  buttonContainer.className = "show-more-container";

  const button = document.createElement("button");
  button.className = "show-more-btn";
  button.textContent = "Show More";
  button.onclick = () => showMoreItems(category);

  buttonContainer.appendChild(button);
  return buttonContainer;
}

// Show more items for a specific category
async function showMoreItems(category) {
  const categoryData = categoryPagination[category];
  const nextPage = categoryData.page + 1;

  // Get current search term
  const searchInput = document.getElementById("search-input");
  const searchTerm = searchInput ? searchInput.value : "";

  // Show loading state on the button
  const showMoreBtn = document.querySelector(
    `[data-category="${category}"] .show-more-btn`
  );
  if (showMoreBtn) {
    showMoreBtn.disabled = true;
    showMoreBtn.textContent = "Loading...";
  }

  try {
    await loadInventoryByCategory(category, nextPage, searchTerm);
  } catch (error) {
    console.error(`Error loading more items for ${category}:`, error);
    // Reset button state on error
    if (showMoreBtn) {
      showMoreBtn.disabled = false;
      showMoreBtn.textContent = "Show More";
    }
  }
}

// Get category icon
function getCategoryIcon(category) {
  const icons = {
    parts: "",
    tools: "",
    fluids: "",
    accessories: "",
    other: "",
  };
  return icons[category] || "📦";
}

// Toggle category section
function toggleCategory(category) {
  const categoryWrapper = document.querySelector(
    `[data-category-wrapper="${category}"]`
  );
  const toggleIcon = document.querySelector(
    `[onclick="toggleCategory('${category}')"] .toggle-icon`
  );

  if (categoryWrapper.classList.contains("collapsed")) {
    // Expand the category
    categoryWrapper.classList.remove("collapsed");
    toggleIcon.textContent = "▼";
  } else {
    // Collapse the category
    categoryWrapper.classList.add("collapsed");
    toggleIcon.textContent = "▶";
  }
}

// Load categories from database
async function loadCategories() {
  try {
    // Load from settings API WITHOUT sync to prevent recreating old categories
    const data = await APIHelper.get("/api/settings/categories");
    if (!data || !data.categories) return;

    const categories = data.categories;
    const categorySelect = document.getElementById("item-category");
    
    if (categorySelect) {
      // Clear existing options except the first one
      categorySelect.innerHTML = '<option value="">Select Category</option>';

      categories.forEach((cat) => {
        const option = document.createElement("option");
        option.value = cat.name;
        option.textContent = cat.name;
        categorySelect.appendChild(option);
      });
    }
  } catch (error) {
    console.error("Error loading categories:", error);
  }
}

// Open add modal
async function openAddModal() {
  currentEditId = null;
  document.getElementById("modal-title").textContent = "Add New Item";
  document.getElementById("item-form").reset();

  // Ensure categories are loaded
  await loadCategories();

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
async function editItem(id) {
  // Search for the item across all categories
  let item = null;
  for (const category of Object.keys(categoryPagination)) {
    item = categoryPagination[category].items.find((item) => item.id === id);
    if (item) break;
  }

  if (!item) {
    console.error(`Item with ID ${id} not found`);
    return;
  }

  try {
    item = await APIHelper.get(`/api/inventory/${id}`);
  } catch (error) {
    console.error(`Error loading item ${id}:`, error);
    alert("Could not load item details. Please try again.");
    return;
  }

  currentEditId = id;
  document.getElementById("modal-title").textContent = "Edit Item";

  // Ensure categories are loaded before setting the value
  await loadCategories();

  // Fill form with item data
  document.getElementById("item-name").value = item.name;
  
  // Set category value - if it doesn't exist in dropdown, add it as an option
  const categorySelect = document.getElementById("item-category");
  const categoryValue = item.category;
  if (categorySelect) {
    // Check if the value exists in the dropdown
    const optionExists = Array.from(categorySelect.options).some(
      opt => opt.value === categoryValue
    );
    
    if (!optionExists && categoryValue) {
      // Add the category as an option if it doesn't exist (for legacy data)
      const option = document.createElement("option");
      option.value = categoryValue;
      option.textContent = categoryValue + " (Legacy)";
      categorySelect.appendChild(option);
    }
    
    categorySelect.value = categoryValue;
  }
  
  document.getElementById("item-quantity").value = item.quantity;
  document.getElementById("item-barcode").value = item.barcode || "";
  document.getElementById("item-manufacturer-part-number").value =
    item.manufacturer_part_number || "";
  document.getElementById("item-description").value = item.description || "";
  document.getElementById("item-location").value = item.location || "";
  document.getElementById("item-reorder-level").value = item.reorder_level || 5;

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
  document.getElementById("restock-code").value = "";
  document.getElementById("restock-code-status").textContent = "";
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

  const codeInput = document.getElementById("restock-code");
  codeInput.removeEventListener("keydown", handleRestockCodeKeydown);
  codeInput.removeEventListener("change", handleRestockCodeLookup);
  codeInput.addEventListener("keydown", handleRestockCodeKeydown);
  codeInput.addEventListener("change", handleRestockCodeLookup);

  // Clear dropdown initially - items will be loaded via search
  dropdown.innerHTML =
    '<div class="dropdown-item">Type to search for items...</div>';
}

function handleRestockCodeKeydown(e) {
  if (e.key === "Enter") {
    e.preventDefault();
    handleRestockCodeLookup();
  }
}

async function handleRestockCodeLookup() {
  const codeInput = document.getElementById("restock-code");
  const status = document.getElementById("restock-code-status");
  const code = codeInput.value.trim();

  if (!code) {
    status.textContent = "";
    return;
  }

  try {
    status.textContent = "Looking up item...";
    const result = await APIHelper.get(
      `/api/inventory/lookup?code=${encodeURIComponent(code)}`
    );

    if (result && result.item) {
      selectProduct(result.item, result.item.name);
      status.textContent = `Matched: ${result.item.name}`;
    }
  } catch (error) {
    document.getElementById("restock-product").value = "";
    document.getElementById("restock-product-search").value = "";
    status.textContent = "No matching inventory item found";
  }
}

// Handle search input with debouncing
async function handleSearchInput(e) {
  const searchTerm = e.target.value.trim();

  // Clear previous timeout
  if (searchTimeout) {
    clearTimeout(searchTimeout);
  }

  // Clear dropdown if search term is empty
  if (!searchTerm) {
    hideDropdown();
    return;
  }

  // Only search if we have at least 2 characters to avoid too many results
  if (searchTerm.length < 2) {
    return;
  }

  // Debounce the search - wait 300ms after user stops typing
  searchTimeout = setTimeout(async () => {
    try {
      // Show loading state
      const dropdown = document.getElementById("restock-product-dropdown");
      dropdown.innerHTML = '<div class="dropdown-item">Searching...</div>';
      showDropdown();

      // Call the database search endpoint
      const result = await APIHelper.get(
        `/api/inventory/search?q=${encodeURIComponent(searchTerm)}`
      );

      if (result && result.results) {
        populateSearchableDropdown(result.results);
      } else {
        dropdown.innerHTML = '<div class="dropdown-item">No items found</div>';
      }

      showDropdown();
    } catch (error) {
      console.error("Error searching inventory:", error);
      const dropdown = document.getElementById("restock-product-dropdown");
      dropdown.innerHTML =
        '<div class="dropdown-item">Error searching items</div>';
      showDropdown();
    }
  }, 300);
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
        Current Stock: ${item.closing_quantity ?? item.quantity} | Category: ${item.category || "N/A"}
        ${item.part_number ? ` | Part #: ${item.part_number}` : ""}
        ${item.barcode ? ` | Barcode: ${item.barcode}` : ""}
        ${item.manufacturer_part_number ? ` | MPN: ${item.manufacturer_part_number}` : ""}
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
  const code = (formData.get("code") || "").trim();
  const quantity = formData.get("quantity");
  const notes = formData.get("notes") || "";

  // Validate form data
  if ((!productId && !code) || !quantity) {
    alert("Please scan a code or select a product, then enter the quantity received.");
    return;
  }

  if (parseInt(quantity) <= 0) {
    alert("Quantity must be greater than 0.");
    return;
  }

  const restockData = {
    quantity: parseInt(quantity),
    notes: notes,
  };

  if (code) {
    restockData.code = code;
  } else {
    restockData.product_id = parseInt(productId);
  }

  // Get the submit button and show loading state
  const submitBtn = e.target.querySelector(".save-btn");
  const originalText = submitBtn.textContent;
  submitBtn.textContent = "Receiving...";
  submitBtn.disabled = true;

  try {
    const endpoint = code ? "/api/inventory/receive" : "/api/inventory/restock";
    const result = await APIHelper.request(endpoint, {
      method: "POST",
      body: JSON.stringify(restockData),
    });

    if (result) {
      // Show success message
      alert(
        `Successfully received ${result.quantity_added} units of ${result.product_name}.\n\nOld quantity: ${result.old_quantity}\nNew quantity: ${result.new_quantity}`
      );

      // Close modal and update the specific item in UI
      closeRestockModal();

      // Update the specific item in the UI
      const productId = result.product_id;
      for (const category of Object.keys(categoryPagination)) {
        const itemIndex = categoryPagination[category].items.findIndex(
          (item) => item.id === productId
        );
        if (itemIndex !== -1) {
          const existingItem = categoryPagination[category].items[itemIndex];
          categoryPagination[category].items[itemIndex] = result.item || {
            ...existingItem,
            quantity: result.new_quantity,
            closing_quantity: result.new_quantity,
            purchases_quantity:
              Number(existingItem.purchases_quantity || 0) +
              Number(result.quantity_added || 0),
          };
          // Re-render the specific category section
          renderCategorySection(category);
          break;
        }
      }
    } else {
      const errorData = await response.json();
      alert(
        `Error receiving stock: ${errorData.error || "Unknown error occurred"}`
      );
    }
  } catch (error) {
    console.error("Error receiving stock:", error);
    alert("Error receiving stock. Please check your connection and try again.");
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

    // Only close modal after successful API call
    // UI update is handled in addInventoryItem/updateInventoryItem functions
    closeModal();
  } catch (error) {
    console.error("Error saving item:", error);
    alert("Error saving item. Please try again.");
  }
}

// Add inventory item
async function addInventoryItem(itemData) {
  try {
    const result = await APIHelper.request("/api/inventory", {
      method: "POST",
      body: itemData, // FormData object
    });

    if (result) {
      const newItem = result.item;

      // Add to inventoryItems array
      inventoryItems.push(newItem);

      // Add to the appropriate category in categoryPagination
      const category = newItem.category;
      if (!categoryPagination[category]) {
        categoryPagination[category] = {
          page: 1,
          totalPages: 1,
          hasMore: false,
          items: [newItem],
          totalItems: 1,
        };
        if (!inventoryCategoryOrder.includes(category)) {
          inventoryCategoryOrder.push(category);
        }
      } else {
        categoryPagination[category].items.unshift(newItem);
        categoryPagination[category].totalItems += 1;
      }
      renderCategorySection(category);

      return newItem;
    } else {
      throw new Error("Failed to add item");
    }
  } catch (error) {
    console.error("Error adding item:", error);
    throw error;
  }
}

// Update inventory item
async function updateInventoryItem(id, formData) {
  try {
    const result = await APIHelper.request(`/api/inventory/${id}`, {
      method: "PUT",
      body: formData, // Send FormData directly for file upload support
    });

    if (result) {
      const updatedItem = result.item;
      const newCategory = updatedItem.category;

      // Find and remove the item from its current category
      let oldCategory = null;
      for (const category of Object.keys(categoryPagination)) {
        const index = categoryPagination[category].items.findIndex(
          (item) => item.id === id
        );
        if (index !== -1) {
          oldCategory = category;
          categoryPagination[category].items.splice(index, 1);
          break;
        }
      }

      // If category changed, update counts
      if (oldCategory && oldCategory !== newCategory) {
        // Decrease count in old category
        categoryPagination[oldCategory].totalItems -= 1;

        // Add to new category (create slot if server returned a category not in initial set)
        if (categoryPagination[newCategory]) {
          categoryPagination[newCategory].items.unshift(updatedItem);
          categoryPagination[newCategory].totalItems += 1;
        } else {
          categoryPagination[newCategory] = {
            page: 1,
            totalPages: 1,
            hasMore: false,
            items: [updatedItem],
            totalItems: 1,
          };
          if (!inventoryCategoryOrder.includes(newCategory)) {
            inventoryCategoryOrder.push(newCategory);
          }
        }

        // Re-render both categories
        renderCategorySection(oldCategory);
        renderCategorySection(newCategory);
      } else if (oldCategory) {
        // Same category, just update the item
        categoryPagination[oldCategory].items.unshift(updatedItem);
        renderCategorySection(oldCategory);
      }

      return updatedItem;
    } else {
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
    const result = await APIHelper.request(`/api/inventory/${id}`, {
      method: "DELETE",
    });

    if (result) {
      // Remove the item from the correct category and update count
      for (const category of Object.keys(categoryPagination)) {
        const itemIndex = categoryPagination[category].items.findIndex(
          (item) => item.id === id
        );
        if (itemIndex !== -1) {
          categoryPagination[category].items.splice(itemIndex, 1);
          categoryPagination[category].totalItems -= 1;

          // Re-render the specific category section
          renderCategorySection(category);
          break;
        }
      }
    } else {
      throw new Error("Failed to delete item");
    }
  } catch (error) {
    console.error("Error deleting item:", error);
    alert("Failed to delete item. Please try again.");
  }
}

// Search inventory with server-side search
function searchInventory() {
  const searchTerm = getCurrentSearch();

  // Reset to first page when searching
  currentPage = 1;

  // Reset category pagination state
  Object.keys(categoryPagination).forEach((category) => {
    categoryPagination[category] = {
      page: 1,
      totalPages: 1,
      hasMore: false,
      items: [],
      totalItems: 0,
    };
  });

  // Load inventory with search term using new category pagination
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
    lowStockBtn.innerHTML = "<span></span> Low Stock Items";
  }
}

// Load low stock items
async function loadLowStockItems() {
  try {
    const data = await APIHelper.request("/api/inventory/low-stock");
    if (data) {
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
        <h3>No Urgent Items!</h3>
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
  const openingQuantity = Number(item.opening_quantity ?? item.quantity ?? 0);
  const purchasesQuantity = Number(item.purchases_quantity ?? 0);
  const salesQuantity = Number(item.sales_quantity ?? 0);
  const closingQuantity = Number(item.closing_quantity ?? item.quantity ?? 0);
  const movementDate = item.movement_date || new Date().toISOString().slice(0, 10);

  if (urgencyLevel === "urgent") {
    stockStatus = "urgent";
    statusText = item.stock_status || "URGENT - Negative Stock";
  } else if (closingQuantity === 0) {
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
          <div class="item-movement-date">Today · ${movementDate}</div>
        </div>
        <div class="stock-status ${stockStatus}">${statusText}</div>
      </div>
      
      <div class="low-stock-item-details">
        <div class="low-stock-item-detail">
          <span>Opening Qty:</span>
          <span>${openingQuantity}</span>
        </div>
        <div class="low-stock-item-detail">
          <span>Purchases (issue in):</span>
          <span>${purchasesQuantity}</span>
        </div>
        <div class="low-stock-item-detail">
          <span>Sales (issue out):</span>
          <span>${salesQuantity}</span>
        </div>
        <div class="low-stock-item-detail">
          <span>Closing Qty:</span>
          <span>${closingQuantity}</span>
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
      
      <div class="item-actions" style="margin-top: 1rem;">
        <button class="action-btn excel-btn" onclick="exportItemLedgerXlsx(${item.id})">
          Excel
        </button>
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

async function fetchCompleteInventoryReport() {
  const perPage = 200;
  let page = 1;
  let allItems = [];

  while (true) {
    const data = await APIHelper.get(`/api/inventory?page=${page}&per_page=${perPage}`);
    const items = data && data.items ? data.items : [];
    allItems = allItems.concat(items);

    if (!data || !data.pagination || !data.pagination.has_next) {
      return allItems;
    }

    page += 1;
  }
}

function getInventoryStockStatus(item) {
  const closingQuantity = Number(item.closing_quantity ?? item.quantity ?? 0);

  if (closingQuantity < 0) return "Negative Stock";
  if (closingQuantity === 0) return "Out of Stock";
  if (closingQuantity <= (item.reorder_level || 0)) return "Low Stock";
  return "In Stock";
}

function sanitizeExcelFilenamePart(value) {
  return String(value || "item")
    .trim()
    .replace(/[\\/:*?"<>|]+/g, "-")
    .replace(/\s+/g, "-")
    .slice(0, 60);
}

async function exportItemLedgerXlsx(itemId) {
  try {
    if (!window.XLSX) {
      throw new Error("Excel export library is not available");
    }

    const ledger = await APIHelper.get(`/api/inventory/${itemId}/ledger`);
    if (!ledger || !ledger.item) {
      throw new Error("Ledger data was not returned");
    }

    const item = ledger.item;
    const dailyRows = (ledger.daily_rows || []).map((row) => ({
      Date: row.date,
      Opening: Number(row.opening ?? 0),
      "In (Purchases)": Number(row.in_quantity ?? 0),
      "Out (Sales)": Number(row.out_quantity ?? 0),
      Adjustments: Number(row.adjustments_quantity ?? 0),
      Closing: Number(row.closing ?? 0),
    }));

    const transactionRows = (ledger.transactions || []).map((txn) => ({
      Date: txn.date,
      "Date Time": txn.datetime,
      Type: txn.transaction_type,
      In: Number(txn.in_quantity || 0),
      Out: Number(txn.out_quantity || 0),
      "Previous Qty": Number(txn.previous_quantity || 0),
      "New Qty": Number(txn.new_quantity || 0),
      Reference: txn.reference_description || "",
      Notes: txn.notes || "",
      "Repair Order": txn.repair_order_id || "",
    }));

    // Calculate monthly totals
    const monthlySummary = {};
    (ledger.daily_rows || []).forEach(row => {
      const month = row.date.substring(0, 7); // e.g. "2026-08"
      if (!monthlySummary[month]) {
        monthlySummary[month] = {
          in: 0,
          out: 0,
          adjustments: 0
        };
      }
      monthlySummary[month].in += Number(row.in_quantity ?? 0);
      monthlySummary[month].out += Number(row.out_quantity ?? 0);
      monthlySummary[month].adjustments += Number(row.adjustments_quantity ?? 0);
    });

    const summaryData = [
      ["GermanATO Item Stock Ledger"],
      ["Item Name", item.name || ""],
      ["Part Number", item.part_number || ""],
      ["Barcode", item.barcode || ""],
      ["Manufacturer Part Number", item.manufacturer_part_number || ""],
      ["Business Date", ledger.movement_date || item.movement_date || ""],
      ["Today Opening", Number(item.opening_quantity ?? 0)],
      ["Today Purchases (In)", Number(item.purchases_quantity ?? 0)],
      ["Today Sales (Out)", Number(item.sales_quantity ?? 0)],
      ["Today Adjustments", Number(item.adjustments_quantity ?? 0)],
      ["Today Closing", Number(item.closing_quantity ?? item.quantity ?? 0)],
      [],
      [
        "Note",
        "Each day's closing becomes the next day's opening. Card values are for today only.",
      ],
      [],
      ["Monthly Summary Breakdown"],
      ["Month", "Total Received (In)", "Total Issued (Out)", "Total Adjustments"]
    ];

    Object.keys(monthlySummary).sort().forEach(month => {
      summaryData.push([
        month,
        monthlySummary[month].in,
        monthlySummary[month].out,
        monthlySummary[month].adjustments
      ]);
    });

    const summarySheet = XLSX.utils.aoa_to_sheet(summaryData);
    summarySheet["!cols"] = [{ wch: 28 }, { wch: 28 }, { wch: 24 }, { wch: 20 }];

    const dailySheet = XLSX.utils.json_to_sheet(
      dailyRows.length
        ? dailyRows
        : [
            {
              Date: ledger.movement_date || "",
              Opening: Number(item.opening_quantity ?? item.quantity ?? 0),
              "In (Purchases)": 0,
              "Out (Sales)": 0,
              Adjustments: 0,
              Closing: Number(item.closing_quantity ?? item.quantity ?? 0),
            },
          ]
    );
    dailySheet["!cols"] = [
      { wch: 14 },
      { wch: 12 },
      { wch: 16 },
      { wch: 14 },
      { wch: 14 },
      { wch: 12 },
    ];

    const transactionsSheet = XLSX.utils.json_to_sheet(
      transactionRows.length
        ? transactionRows
        : [
            {
              Date: "",
              "Date Time": "",
              Type: "",
              In: 0,
              Out: 0,
              "Previous Qty": "",
              "New Qty": "",
              Reference: "No transactions recorded",
              Notes: "",
              "Repair Order": "",
            },
          ]
    );
    transactionsSheet["!cols"] = [
      { wch: 12 },
      { wch: 20 },
      { wch: 12 },
      { wch: 8 },
      { wch: 8 },
      { wch: 14 },
      { wch: 10 },
      { wch: 40 },
      { wch: 30 },
      { wch: 14 },
    ];

    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, dailySheet, "Daily In-Out");
    XLSX.utils.book_append_sheet(wb, transactionsSheet, "Transactions");
    XLSX.utils.book_append_sheet(wb, summarySheet, "Summary");

    const filenamePart = sanitizeExcelFilenamePart(
      item.part_number || item.name || `item-${item.id}`
    );
    const dateStamp = ledger.movement_date || new Date().toISOString().slice(0, 10);
    XLSX.writeFile(wb, `inventory-ledger-${filenamePart}-${dateStamp}.xlsx`);
  } catch (error) {
    console.error("Error exporting item ledger:", error);
    alert("Could not export this item's Excel ledger. Please try again.");
  }
}

function buildInventoryReportRows(items) {
  return items.map((item) => ({
    "Part Number": item.part_number || "",
    Barcode: item.barcode || "",
    "Manufacturer Part Number": item.manufacturer_part_number || "",
    "Item Name": item.name || "",
    Category: getCategoryDisplayName(item.category || "other"),
    "Business Date": item.movement_date || "",
    "Opening Qty": Number(item.opening_quantity ?? item.quantity ?? 0),
    "Purchases (issue in)": Number(item.purchases_quantity ?? 0),
    "Sales (issue out)": Number(item.sales_quantity ?? 0),
    "Closing Qty": Number(item.closing_quantity ?? item.quantity ?? 0),
    Location: item.location || "",
    "Reorder Level": Number(item.reorder_level || 0),
    "Stock Status": getInventoryStockStatus(item),
    Description: item.description || "",
    "Created At": item.created_at || "",
    "Updated At": item.updated_at || "",
  }));
}

function getInventoryReportColumns() {
  return [
    { wch: 18 },
    { wch: 18 },
    { wch: 26 },
    { wch: 30 },
    { wch: 20 },
    { wch: 14 },
    { wch: 12 },
    { wch: 20 },
    { wch: 18 },
    { wch: 12 },
    { wch: 18 },
    { wch: 14 },
    { wch: 16 },
    { wch: 40 },
    { wch: 20 },
    { wch: 20 },
  ];
}

function exportInventoryReportXlsx(items) {
  const reportRows = buildInventoryReportRows(items);
  const lowStockCount = items.filter(
    (item) =>
      Number(item.closing_quantity ?? item.quantity ?? 0) <=
      Number(item.reorder_level || 0)
  ).length;
  const generatedAt = new Date();
  const dateStamp = generatedAt.toISOString().slice(0, 10);

  const reportSheet = XLSX.utils.json_to_sheet(reportRows);
  reportSheet["!cols"] = getInventoryReportColumns();

  const summarySheet = XLSX.utils.aoa_to_sheet([
    ["GermanATO Complete Inventory Report"],
    ["Generated At", generatedAt.toLocaleString()],
    ["Total Items", items.length],
    ["Low Stock Items", lowStockCount],
  ]);
  summarySheet["!cols"] = [{ wch: 28 }, { wch: 24 }];

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, reportSheet, "Inventory");
  XLSX.utils.book_append_sheet(wb, summarySheet, "Summary");
  XLSX.writeFile(wb, `complete-inventory-report-${dateStamp}.xlsx`);
}

async function fetchLowStockReportItems() {
  const data = await APIHelper.get("/api/inventory/low-stock");
  const urgentItems = data && data.urgent_items ? data.urgent_items : [];
  const lowStockItems = data && data.low_stock_items ? data.low_stock_items : [];

  return urgentItems.concat(lowStockItems);
}

async function exportLowStockReportXlsx() {
  const exportBtn = document.querySelector(".low-stock-export-btn");
  const originalText = exportBtn ? exportBtn.innerHTML : "";

  try {
    if (!window.XLSX) {
      throw new Error("Excel export library is not available");
    }

    if (exportBtn) {
      exportBtn.disabled = true;
      exportBtn.innerHTML = "<span>Exporting...</span>";
    }

    const items = await fetchLowStockReportItems();
    const rows = buildInventoryReportRows(items);
    const generatedAt = new Date();
    const dateStamp = generatedAt.toISOString().slice(0, 10);
    const sheet = XLSX.utils.json_to_sheet(rows);
    sheet["!cols"] = getInventoryReportColumns();

    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, sheet, "Low Stock");
    XLSX.writeFile(wb, `low-stock-inventory-report-${dateStamp}.xlsx`);
  } catch (error) {
    console.error("Error exporting low stock report:", error);
    alert("Could not export the low stock report. Please try again.");
  } finally {
    if (exportBtn) {
      exportBtn.disabled = false;
      exportBtn.innerHTML = originalText;
    }
  }
}

// Export complete inventory sheet
async function openPrintSheet() {
  const printBtn = document.querySelector(".print-btn");
  const originalText = printBtn ? printBtn.innerHTML : "";

  try {
    if (!window.XLSX) {
      throw new Error("Excel export library is not available");
    }

    if (printBtn) {
      printBtn.disabled = true;
      printBtn.innerHTML = "<span>Exporting...</span>";
    }

    const items = await fetchCompleteInventoryReport();
    exportInventoryReportXlsx(items);
  } catch (error) {
    console.error("Error exporting inventory report:", error);
    alert("Could not export the inventory report. Please try again.");
  } finally {
    if (printBtn) {
      printBtn.disabled = false;
      printBtn.innerHTML = originalText;
    }
  }
}
