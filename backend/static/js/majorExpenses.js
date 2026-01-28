// Major Expenses Management JavaScript

// Category filter for this page
const EXPENSE_CATEGORY_FILTER = "Major Expenses";

// Function to check if expense is older than 1 day
function isExpenseOlderThanOneDay(createdAtStr) {
  const createdDate = new Date(createdAtStr);
  const currentDate = new Date();
  const oneDayInMs = 24 * 60 * 60 * 1000;
  return currentDate - createdDate > oneDayInMs;
}

// Function to check if edit button should be disabled for current user
function shouldDisableEditButton(expense) {
  const userStr = localStorage.getItem("user");
  if (!userStr) return false;

  const user = JSON.parse(userStr);

  if (user.role === "admin") {
    return false;
  }

  if (user.role === "accountant") {
    return isExpenseOlderThanOneDay(expense.created_at);
  }

  return true;
}

function initializeExpenses() {
  const today = new Date().toISOString().split("T")[0];
  document.getElementById("expense-date").value = today;
  
  const searchFromDateInput = document.getElementById("search-from-date");
  const searchToDateInput = document.getElementById("search-to-date");
  if (searchFromDateInput && !searchFromDateInput.value) {
    searchFromDateInput.value = today;
  }
  if (searchToDateInput && !searchToDateInput.value) {
    searchToDateInput.value = today;
  }

  loadExpenses();
  setupEventListeners();
  updateSummary();
}

function setupEventListeners() {
  document
    .getElementById("expense-form")
    .addEventListener("submit", handleAddExpense);

  document.getElementById("clear-form").addEventListener("click", clearForm);

  document
    .getElementById("search-keyword")
    .addEventListener("input", performSearch);
  document
    .getElementById("search-from-date")
    .addEventListener("change", performSearch);
  document
    .getElementById("search-to-date")
    .addEventListener("change", performSearch);
  document
    .getElementById("clear-search")
    .addEventListener("click", clearSearch);

  document.querySelector(".close").addEventListener("click", closeEditModal);
  window.addEventListener("click", function (event) {
    const modal = document.getElementById("edit-modal");
    if (event.target === modal) {
      closeEditModal();
    }
  });

  document
    .getElementById("edit-expense-form")
    .addEventListener("submit", handleEditExpense);
}

async function loadExpenses() {
  try {
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
    // Don't filter by category in API - we'll filter client-side to include all subcategories
    if (keyword) params.append("keyword", keyword);

    const expenses = await APIHelper.request(
      `/api/expenses?${params.toString()}`
    );
    
    if (expenses) {
      // Filter to only show expenses with major expense categories
      const filteredExpenses = expenses.filter(expense => 
        expense.category === "Major Expenses" ||
        expense.category === "Capital Expenditure" ||
        expense.category === "Equipment Purchase" ||
        expense.category === "Infrastructure" ||
        expense.category === "Major Repairs" ||
        expense.category === "Other Major"
      );
      displayExpenses(filteredExpenses);
      updateSummary(filteredExpenses);
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
      <td><strong>PKR ${parseFloat(expense.amount).toFixed(2)}</strong></td>
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
    // Don't filter by category in API - we'll filter client-side
    APIHelper.request(`/api/expenses?${params.toString()}`)
      .then((expenses) => {
        const filtered = expenses.filter(expense => 
          expense.category === "Major Expenses" ||
          expense.category === "Capital Expenditure" ||
          expense.category === "Equipment Purchase" ||
          expense.category === "Infrastructure" ||
          expense.category === "Major Repairs" ||
          expense.category === "Other Major"
        );
        updateSummary(filtered);
      })
      .catch((error) => console.error("Error updating summary:", error));
    return;
  }

  const fromDate =
    (document.getElementById("search-from-date") || {}).value ||
    new Date().toISOString().split("T")[0];
  const toDate =
    (document.getElementById("search-to-date") || {}).value ||
    new Date().toISOString().split("T")[0];

  const filteredExpenses = expenses.filter((expense) => {
    const expenseDate = expense.date;
    return expenseDate >= fromDate && expenseDate <= toDate;
  });

  const totalAmount = filteredExpenses.reduce(
    (sum, expense) => sum + parseFloat(expense.amount),
    0
  );

  const totalElement = document.getElementById("total-amount");
  if (totalElement) totalElement.textContent = `PKR ${totalAmount.toFixed(2)}`;
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
  document.getElementById("expense-category").value = EXPENSE_CATEGORY_FILTER;
}

function performSearch() {
  loadExpenses();
}

function clearSearch() {
  document.getElementById("search-keyword").value = "";
  const today = new Date().toISOString().split("T")[0];
  document.getElementById("search-from-date").value = today;
  document.getElementById("search-to-date").value = today;
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
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;

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

  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = "slideOutRight 0.3s ease-in";
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 300);
  }, 3000);
}

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

document.addEventListener("DOMContentLoaded", function () {
  if (!auth.requirePageAccess("major-expenses")) {
    return;
  }

  const backBtn = document.getElementById("back-btn");
  const urlParams = new URLSearchParams(window.location.search);
  const fromPage =
    urlParams.get("from") ||
    localStorage.getItem("lastPage") ||
    "finance-management";

  if (fromPage === "finance-management") {
    backBtn.href = "finance-management.html";
  } else {
    backBtn.href = "finance-management.html";
  }

  localStorage.setItem("lastPage", "major-expenses");

  initializeExpenses();
});
