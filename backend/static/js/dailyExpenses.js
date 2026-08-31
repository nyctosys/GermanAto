// Daily Expenses Management JavaScript

// Function to check if expense is older than 1 day
function isExpenseOlderThanOneDay(createdAtStr) {
  const createdDate = new Date(createdAtStr);
  const currentDate = new Date();
  const oneDayInMs = 24 * 60 * 60 * 1000; // 24 hours in milliseconds
  return currentDate - createdDate > oneDayInMs;
}

// Function to check if edit button should be disabled for current user
function shouldDisableEditButton(expense) {
  // Get current user from auth system
  const userStr = localStorage.getItem("user");
  if (!userStr) return false;

  const user = JSON.parse(userStr);

  // Admins can always edit
  if (user.role === "admin") {
    return false;
  }

  // Accountants cannot edit expenses older than 1 day
  if (user.role === "accountant") {
    return isExpenseOlderThanOneDay(expense.created_at);
  }

  // Other roles cannot edit
  return true;
}

function initializeDailyExpenses() {
  // Set default date to today
  const today = new Date().toISOString().split("T")[0];
  document.getElementById("expense-date").value = today;
  // Set default date range to today if empty
  const searchFromDateInput = document.getElementById("search-from-date");
  const searchToDateInput = document.getElementById("search-to-date");
  if (searchFromDateInput && !searchFromDateInput.value) {
    searchFromDateInput.value = today;
  }
  if (searchToDateInput && !searchToDateInput.value) {
    searchToDateInput.value = today;
  }

  // Load expenses
  loadExpenses();

  // Add event listeners
  setupEventListeners();

  // Update summary
  updateSummary();
}

/**
 * The monthly ledger has its own page. Set it up independently so it does not
 * depend on the Daily Expenses bootstrap, whose elements are absent there.
 */
function initializeMonthlyLedger() {
  const monthSelect = document.getElementById("ledger-month-select");
  if (!monthSelect) return;

  if (!monthSelect.value) {
    monthSelect.value = new Date().toISOString().split("T")[0].substring(0, 7);
  }
  monthSelect.addEventListener("change", () => loadMonthlyLedger());
  loadMonthlyLedger();
}

function setupEventListeners() {
  // Form submission
  document
    .getElementById("expense-form")
    .addEventListener("submit", handleAddExpense);

  // Clear form button
  document.getElementById("clear-form").addEventListener("click", clearForm);

  // Search and filter
  document
    .getElementById("search-keyword")
    .addEventListener("input", performSearch);
  document
    .getElementById("search-category")
    .addEventListener("change", performSearch);
  document
    .getElementById("search-from-date")
    .addEventListener("change", performSearch);
  document
    .getElementById("search-to-date")
    .addEventListener("change", performSearch);
  document
    .getElementById("clear-search")
    .addEventListener("click", clearSearch);

  // Modal close
  document.querySelector(".close").addEventListener("click", closeEditModal);
  window.addEventListener("click", function (event) {
    const modal = document.getElementById("edit-modal");
    if (event.target === modal) {
      closeEditModal();
    }
  });

  // Edit form submission
  document
    .getElementById("edit-expense-form")
    .addEventListener("submit", handleEditExpense);
}

async function loadExpenses() {
  try {
    const category =
      (document.getElementById("search-category") || {}).value || "";
    const keywordRaw =
      (document.getElementById("search-keyword") || {}).value || "";
    const keyword = keywordRaw.trim();
    const fromDate =
      (document.getElementById("search-from-date") || {}).value ||
      new Date().toISOString().split("T")[0];
    const toDate =
      (document.getElementById("search-to-date") || {}).value ||
      new Date().toISOString().split("T")[0];

    const params = new URLSearchParams();
    if (fromDate) params.append("start_date", fromDate);
    if (toDate) params.append("end_date", toDate);
    if (category) params.append("category", category);
    if (keyword) params.append("keyword", keyword);

    const expenses = await APIHelper.request(
      `/api/expenses?${params.toString()}`
    );
    if (expenses) {
      displayExpenses(expenses);
      updateSummary(expenses);
      if (typeof loadMonthlyLedger === "function") {
        loadMonthlyLedger();
      }
    } else {
      showToast("Error loading expenses", "error");
    }
  } catch (error) {
    console.error("Error loading expenses:", error);
    showToast("Error loading expenses", "error");
  }
}

function displayExpenses(expenses) {
  const tbody = document.getElementById("expenses-tbody");
  tbody.innerHTML = "";

  if (expenses.length === 0) {
    tbody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; padding: 2rem; color: #6c757d;">
                    No expenses found
                </td>
            </tr>
        `;
    return;
  }

  expenses.forEach((expense) => {
    const row = document.createElement("tr");

    // Check if edit button should be disabled
    const isEditDisabled = shouldDisableEditButton(expense);
    const editButtonClass = isEditDisabled
      ? "btn btn-edit disabled"
      : "btn btn-edit";
    const editButtonDisabled = isEditDisabled ? "disabled" : "";
    const editButtonText = isEditDisabled ? "Edit (Locked)" : "Edit";

    row.innerHTML = `
            <td>${formatDate(expense.date)}</td>
            <td><span class="category-badge">${expense.category}</span></td>
            <td>${expense.description}</td>
            <td><strong>PKR ${parseFloat(expense.amount).toFixed(
              2
            )}</strong></td>
            <td>${expense.notes || "-"}</td>
            <td>
                <button class="${editButtonClass}" ${editButtonDisabled} onclick="editExpense(${
      expense.id
    })">${editButtonText}</button>
                <button class="btn btn-delete" onclick="deleteExpense(${
                  expense.id
                })">Delete</button>
            </td>
        `;
    tbody.appendChild(row);
  });
}

// Keep module-level variables to compute balance across updates
let __todayExpensesTotal = 0;
let __todayCashTotal = 0;

function updateBalanceCard() {
  const balanceEl = document.getElementById("today-balance-amount");
  if (!balanceEl) return;
  const balance = __todayCashTotal - __todayExpensesTotal;
  balanceEl.textContent = `PKR ${balance.toFixed(2)}`;
}

function updateSummary(expenses = null) {
  if (!expenses) {
    const fromDate =
      (document.getElementById("search-from-date") || {}).value ||
      new Date().toISOString().split("T")[0];
    const toDate =
      (document.getElementById("search-to-date") || {}).value ||
      new Date().toISOString().split("T")[0];
    const params = new URLSearchParams();
    if (fromDate) params.append("start_date", fromDate);
    if (toDate) params.append("end_date", toDate);
    APIHelper.request(`/api/expenses?${params.toString()}`)
      .then((expenses) => updateSummary(expenses))
      .catch((error) => console.error("Error updating summary:", error));
    return;
  }

  const fromDate =
    (document.getElementById("search-from-date") || {}).value ||
    new Date().toISOString().split("T")[0];
  const toDate =
    (document.getElementById("search-to-date") || {}).value ||
    new Date().toISOString().split("T")[0];

  // Filter expenses within the date range
  const filteredExpenses = expenses.filter((expense) => {
    const expenseDate = expense.date;
    return expenseDate >= fromDate && expenseDate <= toDate;
  });

  const todayAmount = filteredExpenses.reduce(
    (sum, expense) => sum + parseFloat(expense.amount),
    0
  );

  __todayExpensesTotal = todayAmount;
  const todayElement = document.getElementById("today-amount");
  if (todayElement) todayElement.textContent = `PKR ${todayAmount.toFixed(2)}`;

  // Update balance after expenses update
  updateBalanceCard();
}

async function handleAddExpense(event) {
  event.preventDefault();

  const formData = new FormData(event.target);
  const expenseData = {
    date: formData.get("date"),
    category: formData.get("category"),
    description: formData.get("description"),
    amount: parseFloat(formData.get("amount")),
    notes: formData.get("notes") || "",
  };

  try {
    const result = await APIHelper.request("/api/expenses", {
      method: "POST",
      body: JSON.stringify(expenseData),
    });

    if (result) {
      showToast("Expense added successfully", "success");
      clearForm();
      loadExpenses();
    } else {
      showToast("Error adding expense", "error");
    }
  } catch (error) {
    console.error("Error adding expense:", error);
    showToast("Error adding expense", "error");
  }
}

async function handleEditExpense(event) {
  event.preventDefault();

  const formData = new FormData(event.target);
  const expenseId = formData.get("id");
  const expenseData = {
    date: formData.get("date"),
    category: formData.get("category"),
    description: formData.get("description"),
    amount: parseFloat(formData.get("amount")),
    notes: formData.get("notes") || "",
  };

  try {
    const data = await APIHelper.put(`/api/expenses/${expenseId}`, expenseData);

    if (data) {
      showToast("Expense updated successfully", "success");
      closeEditModal();
      loadExpenses();
    } else {
      showToast("Error updating expense", "error");
    }
  } catch (error) {
    console.error("Error updating expense:", error);
    showToast("Error updating expense", "error");
  }
}

async function editExpense(expenseId) {
  try {
    const expense = await APIHelper.get(`/api/expenses/${expenseId}`);
    if (expense) {
      // Check if user can edit this expense
      if (shouldDisableEditButton(expense)) {
        alert(
          "You cannot edit expenses older than 1 day. Please contact an administrator."
        );
        return;
      }

      populateEditForm(expense);
      openEditModal();
    } else {
      showToast("Error loading expense details", "error");
    }
  } catch (error) {
    console.error("Error loading expense:", error);
    showToast("Error loading expense details", "error");
  }
}

function populateEditForm(expense) {
  document.getElementById("edit-expense-id").value = expense.id;
  document.getElementById("edit-expense-date").value = expense.date;
  document.getElementById("edit-expense-category").value = expense.category;
  document.getElementById("edit-expense-description").value =
    expense.description;
  document.getElementById("edit-expense-amount").value = expense.amount;
  document.getElementById("edit-expense-notes").value = expense.notes || "";
}

function openEditModal() {
  document.getElementById("edit-modal").style.display = "block";
}

function closeEditModal() {
  document.getElementById("edit-modal").style.display = "none";
  document.getElementById("edit-expense-form").reset();
}

async function deleteExpense(expenseId) {
  if (!confirm("Are you sure you want to delete this expense?")) {
    return;
  }

  try {
    const data = await APIHelper.delete(`/api/expenses/${expenseId}`);

    if (data) {
      showToast("Expense deleted successfully", "success");
      loadExpenses();
    } else {
      showToast("Error deleting expense", "error");
    }
  } catch (error) {
    console.error("Error deleting expense:", error);
    showToast("Error deleting expense", "error");
  }
}

function clearForm() {
  document.getElementById("expense-form").reset();
  document.getElementById("expense-date").value = new Date()
    .toISOString()
    .split("T")[0];
}

function performSearch() {
  // Server-side filtering via query params; reload both lists to respect selected date
  loadExpenses();
  if (typeof loadCashReceived === "function") {
    loadCashReceived();
  }
}

function clearSearch() {
  document.getElementById("search-keyword").value = "";
  document.getElementById("search-category").value = "";
  document.getElementById("search-from-date").value = "";
  document.getElementById("search-to-date").value = "";
  loadExpenses();
}

function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function showToast(message, type = "info") {
  // Create toast element
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;

  // Style the toast
  toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        color: white;
        font-weight: 500;
        z-index: 3000;
        animation: slideInRight 0.3s ease-out;
        max-width: 300px;
        word-wrap: break-word;
    `;

  // Set background color based on type
  switch (type) {
    case "success":
      toast.style.background = "linear-gradient(135deg, #28a745, #20c997)";
      break;
    case "error":
      toast.style.background = "linear-gradient(135deg, #dc3545, #fd7e14)";
      break;
    case "warning":
      toast.style.background = "linear-gradient(135deg, #ffc107, #fd7e14)";
      break;
    default:
      toast.style.background = "linear-gradient(135deg, #17a2b8, #20c997)";
  }

  // Add to page
  document.body.appendChild(toast);

  // Remove after 3 seconds
  setTimeout(() => {
    toast.style.animation = "slideOutRight 0.3s ease-in";
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 300);
  }, 3000);
}

// Add CSS animations for toast
const style = document.createElement("style");
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// ===== CASH RECEIVED FUNCTIONALITY =====

// Function to check if cash received record is older than 1 day
function isCashReceivedOlderThanOneDay(createdAtStr) {
  const createdDate = new Date(createdAtStr);
  const currentDate = new Date();
  const oneDayInMs = 24 * 60 * 60 * 1000; // 24 hours in milliseconds
  return currentDate - createdDate > oneDayInMs;
}

// Function to check if edit button should be disabled for current user
function shouldDisableCashEditButton(cashRecord) {
  // Get current user from auth system
  const userStr = localStorage.getItem("user");
  if (!userStr) return false;

  const user = JSON.parse(userStr);

  // Admins can always edit
  if (user.role === "admin") {
    return false;
  }

  // Accountants cannot edit cash received records older than 1 day
  if (user.role === "accountant") {
    return isCashReceivedOlderThanOneDay(cashRecord.created_at);
  }

  // Other roles cannot edit
  return true;
}

// Load cash received records
/**
 * Fill the "settles invoice" picker with invoices that still owe money.
 * Recording the receipt against the invoice is what stops the payment having to
 * be keyed a second time through Update Balance.
 */
async function loadUnpaidInvoicesForCashForm() {
  const select = document.getElementById("cash-invoice");
  const hint = document.getElementById("cash-invoice-hint");
  if (!select) return;

  try {
    const data = await APIHelper.get("/api/search?type=invoice");
    const owing = (data.invoices || []).filter((i) => (i.balance || 0) > 0.005);

    select.innerHTML =
      '<option value="">Not against an invoice</option>' +
      owing
        .map(
          (i) =>
            `<option value="${i.id}" data-owed="${i.balance}">#${i.id} — ${APIHelper.escapeHtml(
              i.customer_name || ""
            )} — ${Number(i.balance).toLocaleString("en-PK")} PKR owing</option>`
        )
        .join("");

    if (hint) {
      hint.textContent = owing.length
        ? `${owing.length} invoice${owing.length === 1 ? "" : "s"} still owing.`
        : "No invoices are currently owing.";
    }
  } catch (error) {
    console.error("Could not load invoices for the cash form:", error);
    if (hint) hint.textContent = "Could not load invoices — you can still record the cash without linking it.";
  }
}

/** Warn before submitting if the amount does not match what is owed. */
function setupCashInvoiceHint() {
  const select = document.getElementById("cash-invoice");
  const amount = document.getElementById("cash-amount");
  const hint = document.getElementById("cash-invoice-hint");
  if (!select || !amount || !hint) return;

  const check = () => {
    const opt = select.selectedOptions[0];
    const owed = opt && opt.dataset.owed ? parseFloat(opt.dataset.owed) : null;
    const paid = parseFloat(amount.value);
    if (owed === null || isNaN(paid) || paid <= 0) return;
    if (paid > owed + 0.005) {
      hint.textContent = `That is more than the ${owed.toLocaleString("en-PK")} PKR owing on this invoice.`;
    } else if (paid < owed - 0.005) {
      hint.textContent = `Part payment — ${(owed - paid).toLocaleString("en-PK")} PKR will remain owing.`;
    } else {
      hint.textContent = "Settles this invoice in full.";
    }
  };

  select.addEventListener("change", check);
  amount.addEventListener("input", check);
}

async function loadCashReceived() {
  try {
    const fromDate =
      (document.getElementById("search-from-date") || {}).value ||
      new Date().toISOString().split("T")[0];
    const toDate =
      (document.getElementById("search-to-date") || {}).value ||
      new Date().toISOString().split("T")[0];
    const params = new URLSearchParams();
    if (fromDate) params.append("start_date", fromDate);
    if (toDate) params.append("end_date", toDate);

    const cashRecords = await APIHelper.get(
      `/api/cash-received?${params.toString()}`
    );
    if (cashRecords) {
      displayCashReceived(cashRecords);
      updateCashSummary(cashRecords);
      if (typeof loadMonthlyLedger === "function") {
        loadMonthlyLedger();
      }
    } else {
      showToast("Error loading cash received records", "error");
    }
  } catch (error) {
    console.error("Error loading cash received records:", error);
    showToast("Error loading cash received records", "error");
  }
}

// Display cash received records in table
function displayCashReceived(cashRecords) {
  const tbody = document.getElementById("cash-received-tbody");
  tbody.innerHTML = "";

  if (cashRecords.length === 0) {
    tbody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; padding: 2rem; color: #6c757d;">
                    No cash received records found
                </td>
            </tr>
        `;
    return;
  }

  cashRecords.forEach((cashRecord) => {
    const row = document.createElement("tr");

    // Check if edit button should be disabled
    const isEditDisabled = shouldDisableCashEditButton(cashRecord);
    const editButtonClass = isEditDisabled
      ? "btn btn-edit disabled"
      : "btn btn-edit";
    const editButtonDisabled = isEditDisabled ? "disabled" : "";
    const editButtonText = isEditDisabled ? "Edit (Locked)" : "Edit";

    row.innerHTML = `
            <td>${formatDate(cashRecord.date)}</td>
            <td>${cashRecord.description}</td>
            <td><strong>PKR ${parseFloat(cashRecord.amount).toFixed(
              2
            )}</strong></td>
            <td><span class="payment-method-badge">${
              cashRecord.payment_method
            }</span></td>
            <td>${cashRecord.notes || "-"}</td>
            <td>
                <button class="${editButtonClass}" ${editButtonDisabled} onclick="editCashReceived(${
      cashRecord.id
    })">${editButtonText}</button>
                <button class="btn btn-delete" onclick="deleteCashReceived(${
                  cashRecord.id
                })">Delete</button>
            </td>
        `;
    tbody.appendChild(row);
  });
}

// Update cash received summary
function updateCashSummary(cashRecords = null) {
  if (!cashRecords) {
    const fromDate =
      (document.getElementById("search-from-date") || {}).value ||
      new Date().toISOString().split("T")[0];
    const toDate =
      (document.getElementById("search-to-date") || {}).value ||
      new Date().toISOString().split("T")[0];
    const params = new URLSearchParams();
    if (fromDate) params.append("start_date", fromDate);
    if (toDate) params.append("end_date", toDate);
    APIHelper.get(`/api/cash-received?${params.toString()}`)
      .then((cashRecords) => updateCashSummary(cashRecords))
      .catch((error) => console.error("Error updating cash summary:", error));
    return;
  }

  const fromDate =
    (document.getElementById("search-from-date") || {}).value ||
    new Date().toISOString().split("T")[0];
  const toDate =
    (document.getElementById("search-to-date") || {}).value ||
    new Date().toISOString().split("T")[0];

  // Filter cash records within the date range
  const filteredCashRecords = cashRecords.filter((record) => {
    const recordDate = record.date;
    return recordDate >= fromDate && recordDate <= toDate;
  });

  const todayAmount = filteredCashRecords.reduce(
    (sum, record) => sum + parseFloat(record.amount),
    0
  );

  __todayCashTotal = todayAmount;
  const todayElement = document.getElementById("today-cash-amount");
  if (todayElement) todayElement.textContent = `PKR ${todayAmount.toFixed(2)}`;

  // Update balance after cash update
  updateBalanceCard();
}

// Handle add cash received form submission
async function handleAddCashReceived(event) {
  event.preventDefault();

  const formData = new FormData(event.target);
  const cashData = {
    date: formData.get("date"),
    description: formData.get("description"),
    amount: parseFloat(formData.get("amount")),
    payment_method: formData.get("payment_method"),
    notes: formData.get("notes") || "",
    invoice_id: formData.get("invoice_id") || null,
  };

  try {
    const data = await APIHelper.post("/api/cash-received", cashData);

    if (data) {
      showToast("Cash received added successfully", "success");
      clearCashForm();
      loadCashReceived();
      loadUnpaidInvoicesForCashForm();
    } else {
      showToast("Error adding cash received", "error");
    }
  } catch (error) {
    console.error("Error adding cash received:", error);
    showToast("Error adding cash received", "error");
  }
}

// Handle edit cash received form submission
async function handleEditCashReceived(event) {
  event.preventDefault();

  const formData = new FormData(event.target);
  const cashId = formData.get("id");
  const cashData = {
    date: formData.get("date"),
    description: formData.get("description"),
    amount: parseFloat(formData.get("amount")),
    payment_method: formData.get("payment_method"),
    notes: formData.get("notes") || "",
  };

  try {
    const data = await APIHelper.put(`/api/cash-received/${cashId}`, cashData);

    if (data) {
      showToast("Cash received updated successfully", "success");
      closeEditCashModal();
      loadCashReceived();
    } else {
      showToast("Error updating cash received", "error");
    }
  } catch (error) {
    console.error("Error updating cash received:", error);
    showToast("Error updating cash received", "error");
  }
}

// Edit cash received record
async function editCashReceived(cashId) {
  try {
    const cashRecord = await APIHelper.get(`/api/cash-received/${cashId}`);
    if (cashRecord) {
      // Check if user can edit this record
      if (shouldDisableCashEditButton(cashRecord)) {
        alert(
          "You cannot edit cash received records older than 1 day. Please contact an administrator."
        );
        return;
      }

      populateEditCashForm(cashRecord);
      openEditCashModal();
    } else {
      showToast("Error loading cash received details", "error");
    }
  } catch (error) {
    console.error("Error loading cash received:", error);
    showToast("Error loading cash received details", "error");
  }
}

// Populate edit cash form
function populateEditCashForm(cashRecord) {
  document.getElementById("edit-cash-id").value = cashRecord.id;
  document.getElementById("edit-cash-date").value = cashRecord.date;
  document.getElementById("edit-cash-description").value =
    cashRecord.description;
  document.getElementById("edit-cash-amount").value = cashRecord.amount;
  document.getElementById("edit-cash-payment-method").value =
    cashRecord.payment_method;
  document.getElementById("edit-cash-notes").value = cashRecord.notes || "";
}

// Open edit cash modal
function openEditCashModal() {
  document.getElementById("edit-cash-modal").style.display = "block";
}

// Close edit cash modal
function closeEditCashModal() {
  document.getElementById("edit-cash-modal").style.display = "none";
  document.getElementById("edit-cash-received-form").reset();
}

// Delete cash received record
async function deleteCashReceived(cashId) {
  if (!confirm("Are you sure you want to delete this cash received record?")) {
    return;
  }

  try {
    const data = await APIHelper.delete(`/api/cash-received/${cashId}`);

    if (data) {
      showToast("Cash received record deleted successfully", "success");
      loadCashReceived();
    } else {
      showToast("Error deleting cash received record", "error");
    }
  } catch (error) {
    console.error("Error deleting cash received:", error);
    showToast("Error deleting cash received record", "error");
  }
}

// Clear cash form
function clearCashForm() {
  document.getElementById("cash-received-form").reset();
  document.getElementById("cash-date").value = new Date()
    .toISOString()
    .split("T")[0];
}

// Initialize cash received functionality
function initializeCashReceived() {
  // Set default date to today
  const today = new Date().toISOString().split("T")[0];
  document.getElementById("cash-date").value = today;

  // Load cash received records
  loadCashReceived();

  // Add event listeners
  setupCashEventListeners();
}

// Setup cash received event listeners
function setupCashEventListeners() {
  // Form submission
  document
    .getElementById("cash-received-form")
    .addEventListener("submit", handleAddCashReceived);

  // Clear form button
  document
    .getElementById("clear-cash-form")
    .addEventListener("click", clearCashForm);

  // Edit form submission
  document
    .getElementById("edit-cash-received-form")
    .addEventListener("submit", handleEditCashReceived);

  // Modal close
  document
    .querySelector("#edit-cash-modal .close")
    .addEventListener("click", closeEditCashModal);
  window.addEventListener("click", function (event) {
    const modal = document.getElementById("edit-cash-modal");
    if (event.target === modal) {
      closeEditCashModal();
    }
  });
}

// Initialize both expenses and cash received when page loads
document.addEventListener("DOMContentLoaded", function () {
  // Check authentication and page access - allow both admin and accountant
  if (!auth.requirePageAccess("daily-expenses")) {
    return;
  }

  // Set up smart back button logic
  const backBtn = document.getElementById("back-btn");
  const urlParams = new URLSearchParams(window.location.search);
  const fromPage =
    urlParams.get("from") ||
    localStorage.getItem("lastPage") ||
    "finance-management";

  // Set back button destination based on where user came from
  if (backBtn) {
    if (fromPage === "home") {
      backBtn.href = "home.html";
    } else if (fromPage === "admin") {
      backBtn.href = "admin.html";
    } else if (fromPage === "finance-management") {
      backBtn.href = "finance-management.html";
    } else {
      backBtn.href = "finance-management.html"; // Default fallback
    }
  }

  // Track current page for back button logic
  localStorage.setItem("lastPage", "daily-expenses");

  // Store the original from parameter for navigation chain preservation
  if (urlParams.get("from")) {
    localStorage.setItem("originalFrom", urlParams.get("from"));
  }

  // Initialize both expenses and cash received
  if (document.getElementById("expense-form")) {
    initializeDailyExpenses();
    initializeCashReceived();
    loadUnpaidInvoicesForCashForm();
    setupCashInvoiceHint();
  }
  initializeMonthlyLedger();
});

// Monthly Ledger Functionality
let currentLedgerData = null;

async function loadMonthlyLedger() {
  const monthInput = document.getElementById("ledger-month-select");
  // The ledger lives on its own page now; on Daily Expenses there is nothing to fill.
  if (!monthInput) return;
  if (!monthInput) return;
  const month = monthInput.value;
  if (!month) return;

  try {
    const data = await APIHelper.get(`/api/expenses/monthly-ledger?month=${month}`);
    currentLedgerData = data;

    // Update Overview Cards
    document.getElementById("ledger-opening-balance").textContent = `PKR ${formatCurrency(data.initial_balance)}`;
    
    const totalIn = data.daily_ledger.reduce((acc, curr) => acc + curr.inflow, 0);
    const totalOut = data.daily_ledger.reduce((acc, curr) => acc + curr.outflow, 0);
    const closingBalance = data.daily_ledger.length > 0 ? data.daily_ledger[data.daily_ledger.length - 1].closing_balance : data.initial_balance;

    document.getElementById("ledger-total-in").textContent = `PKR ${formatCurrency(totalIn)}`;
    document.getElementById("ledger-total-out").textContent = `PKR ${formatCurrency(totalOut)}`;
    document.getElementById("ledger-closing-balance").textContent = `PKR ${formatCurrency(closingBalance)}`;

    // Render Daily Rolling Balance Ledger Table
    const tbody = document.getElementById("daily-ledger-tbody");
    tbody.innerHTML = "";

    if (!data.daily_ledger || data.daily_ledger.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No daily records found.</td></tr>`;
      return;
    }

    data.daily_ledger.forEach(row => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${row.date}</strong></td>
        <td>PKR ${formatCurrency(row.opening_balance)}</td>
        <td style="color: #2c7a7b; font-weight: 500;">+ PKR ${formatCurrency(row.inflow)}</td>
        <td style="color: #c53030; font-weight: 500;">- PKR ${formatCurrency(row.outflow)}</td>
        <td style="font-weight: bold; color: #44337a;">PKR ${formatCurrency(row.closing_balance)}</td>
      `;
      tbody.appendChild(tr);
    });

  } catch (error) {
    console.error("Error loading monthly ledger:", error);
    showToast("Error loading monthly ledger", "error");
  }
}

function formatCurrency(amount) {
  return parseFloat(amount).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function exportMonthlyLedger() {
  if (!currentLedgerData) {
    showToast("No ledger data available to export.", "error");
    return;
  }

  try {
    const wb = XLSX.utils.book_new();

    // 1. Prepare Daily Statement Sheet
    const dailyRows = currentLedgerData.daily_ledger.map(row => ({
      "Date": row.date,
      "Opening Balance (PKR)": row.opening_balance,
      "Cash Inflow (PKR)": row.inflow,
      "Expenses Outflow (PKR)": row.outflow,
      "Closing Balance (PKR)": row.closing_balance
    }));
    const wsDaily = XLSX.utils.json_to_sheet(dailyRows);
    XLSX.utils.book_append_sheet(wb, wsDaily, "Daily Balances Statement");

    // 2. Prepare Detailed Ledger Sheet
    const detailedRows = currentLedgerData.details.map(t => ({
      "Date": t.date,
      "Type": t.type === 'in' ? "Cash Inflow" : "Expense Outflow",
      "Description": t.description,
      "Category/Payment Method": t.type === 'in' ? t.payment_method : t.category,
      "Amount (PKR)": t.amount,
      "Notes": t.notes
    }));
    const wsDetailed = XLSX.utils.json_to_sheet(detailedRows);
    XLSX.utils.book_append_sheet(wb, wsDetailed, "Detailed Transactions");

    // Write file
    const monthName = currentLedgerData.month;
    XLSX.writeFile(wb, `GermanATO_Ledger_${monthName}.xlsx`);
    showToast("Ledger exported successfully!", "success");
    
  } catch (error) {
    console.error("Error exporting ledger:", error);
    showToast("Failed to export ledger to Excel.", "error");
  }
}
