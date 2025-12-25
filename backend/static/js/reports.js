// ===== GLOBAL VARIABLES =====
let reportsData = null;
let salesChart = null;
let profitChart = null;
let growthChart = null;
let currentFilter = "30days"; // Track current active filter

// ===== INITIALIZATION =====
document.addEventListener("DOMContentLoaded", function () {
  // Check authentication
  if (!auth.requirePageAccess("reports")) {
    return;
  }

  // Wait for Chart.js to load
  if (typeof Chart === "undefined") {
    console.error("Chart.js not loaded");
    showErrorState("Chart library not loaded. Please refresh the page.");
    return;
  }

  // Initialize charts
  initializeCharts();

  // Load initial data
  loadReports();

  // Setup back button
  setupBackButton();
});

// ===== QUICK FILTER FUNCTIONS =====
function setQuickFilter(filter) {
  const today = new Date();
  let startDate = new Date();
  const endDate = today;

  // Update active state of filter pills
  updateActiveFilterPill(filter);

  // Handle custom filter differently
  if (filter === "custom") {
    showCustomDateInputs();
    currentFilter = filter;
    return;
  }

  // Hide custom date range for preset filters
  hideCustomDateInputs();

  // Calculate start date based on filter
  switch (filter) {
    case "today":
      startDate = new Date(today);
      document.getElementById("period-select").value = "day";
      break;
    case "7days":
      startDate = new Date(today);
      startDate.setDate(startDate.getDate() - 7);
      document.getElementById("period-select").value = "week";
      break;
    case "30days":
      startDate = new Date(today);
      startDate.setDate(startDate.getDate() - 30);
      document.getElementById("period-select").value = "month";
      break;
    case "year":
      startDate = new Date(today.getFullYear(), 0, 1);
      document.getElementById("period-select").value = "year";
      break;
    default:
      startDate = new Date(today);
      startDate.setDate(startDate.getDate() - 30);
  }

  // Update date inputs
  document.getElementById("start-date").value = formatDateForInput(startDate);
  document.getElementById("end-date").value = formatDateForInput(endDate);

  // Save current filter
  currentFilter = filter;

  // Load reports with new date range
  loadReports();
}

function updateActiveFilterPill(activeFilter) {
  // Remove active class from all pills
  const pills = document.querySelectorAll(".filter-pill");
  pills.forEach((pill) => {
    pill.classList.remove("active");
  });

  // Add active class to selected pill
  const activePill = document.querySelector(
    `.filter-pill[data-filter="${activeFilter}"]`
  );
  if (activePill) {
    activePill.classList.add("active");
  }
}

function showCustomDateInputs() {
  const customRange = document.getElementById("custom-date-range");
  if (customRange) {
    customRange.style.display = "flex";
  }
}

function hideCustomDateInputs() {
  const customRange = document.getElementById("custom-date-range");
  if (customRange) {
    customRange.style.display = "none";
  }
}

function formatDateForInput(date) {
  return date.toISOString().split("T")[0];
}

// ===== DATA LOADING =====
async function loadReports() {
  try {
    showLoadingState();

    const period = document.getElementById("period-select").value;
    const startDate = document.getElementById("start-date").value;
    const endDate = document.getElementById("end-date").value;

    const params = new URLSearchParams({
      period: period,
      start_date: startDate,
      end_date: endDate,
    });

    const data = await APIHelper.get(`/api/reports?${params}`);

    if (data) {
      reportsData = data;
      updateDashboard();
      hideLoadingState();
    } else {
      throw new Error("No data received");
    }
  } catch (error) {
    console.error("Error loading reports:", error);
    showErrorState("Failed to load reports. Please try again.");
  }
}

// ===== UI STATE MANAGEMENT =====
function showLoadingState() {
  document.getElementById("loading-state").style.display = "flex";
  document.getElementById("error-state").style.display = "none";
  document.getElementById("dashboard-content").style.display = "none";
}

function hideLoadingState() {
  document.getElementById("loading-state").style.display = "none";
  document.getElementById("error-state").style.display = "none";
  document.getElementById("dashboard-content").style.display = "block";
}

function showErrorState(message) {
  document.getElementById("loading-state").style.display = "none";
  document.getElementById("error-state").style.display = "flex";
  document.getElementById("dashboard-content").style.display = "none";
  document.getElementById("error-message").textContent = message;
}

// ===== DASHBOARD UPDATE =====
function updateDashboard() {
  if (!reportsData) return;

  updateKPICards();
  updateCharts();
  updateAlerts();
  updateTables();
}

function updateKPICards() {
  const { sales, expenses, profit, receivables, period } = reportsData;

  // Update sales
  document.getElementById("sales-total").textContent = formatCurrency(
    sales.total || 0
  );
  document.getElementById("sales-period").textContent = getFilterText();

  // Update expenses
  document.getElementById("expenses-total").textContent = formatCurrency(
    expenses.total || 0
  );
  document.getElementById("expenses-period").textContent = getFilterText();

  // Update profit
  document.getElementById("profit-total").textContent = formatCurrency(
    profit.total || 0
  );
  document.getElementById("profit-period").textContent = getFilterText();

  // Update receivables
  document.getElementById("receivables-total").textContent = formatCurrency(
    receivables || 0
  );
}

function updateCharts() {
  const { sales, profit, customer_growth, invoice_growth, car_growth } =
    reportsData;

  // Update sales chart
  updateSalesChart(sales);

  // Update profit chart
  updateProfitChart(profit);

  // Update growth chart
  updateGrowthChart(customer_growth, invoice_growth, car_growth);
}

function updateAlerts() {
  const { low_stock, open_repairs, pending_quotes } = reportsData;

  // Update low stock alerts
  updateLowStockAlerts(low_stock);

  // Update open repairs
  updateOpenRepairs(open_repairs);

  // Update pending quotes
  updatePendingQuotes(pending_quotes);
}

function updateTables() {
  const { vendor_balances, completed_today } = reportsData;

  // Update vendors table
  updateVendorsTable(vendor_balances);

  // Update completed today table
  updateCompletedTodayTable(completed_today);
}

// ===== CHART FUNCTIONS =====
function initializeCharts() {
  // Sales Chart - Maroon Theme
  const salesCtx = document.getElementById("sales-chart").getContext("2d");
  const salesGradient = salesCtx.createLinearGradient(0, 0, 0, 280);
  salesGradient.addColorStop(0, "rgba(139, 21, 56, 0.3)");
  salesGradient.addColorStop(1, "rgba(139, 21, 56, 0.02)");

  salesChart = new Chart(salesCtx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Sales",
          data: [],
          borderColor: "#8b1538",
          backgroundColor: salesGradient,
          borderWidth: 3,
          fill: true,
          tension: 0.4,
          pointBackgroundColor: "#8b1538",
          pointBorderColor: "#ffffff",
          pointBorderWidth: 2,
          pointRadius: 5,
          pointHoverRadius: 7,
        },
      ],
    },
    options: getChartOptions("Sales Trend"),
  });

  // Profit Chart - Maroon Theme (lighter shade)
  const profitCtx = document.getElementById("profit-chart").getContext("2d");
  const profitGradient = profitCtx.createLinearGradient(0, 0, 0, 280);
  profitGradient.addColorStop(0, "rgba(169, 29, 69, 0.3)");
  profitGradient.addColorStop(1, "rgba(169, 29, 69, 0.02)");

  profitChart = new Chart(profitCtx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Profit",
          data: [],
          borderColor: "#a91d45",
          backgroundColor: profitGradient,
          borderWidth: 3,
          fill: true,
          tension: 0.4,
          pointBackgroundColor: "#a91d45",
          pointBorderColor: "#ffffff",
          pointBorderWidth: 2,
          pointRadius: 5,
          pointHoverRadius: 7,
        },
      ],
    },
    options: getChartOptions("Profit Trend"),
  });

  // Growth Chart - Maroon Theme with gradient bars
  const growthCtx = document.getElementById("growth-chart").getContext("2d");

  growthChart = new Chart(growthCtx, {
    type: "bar",
    data: {
      labels: ["Customers", "Invoices", "Cars"],
      datasets: [
        {
          label: "Growth",
          data: [0, 0, 0],
          backgroundColor: [
            "rgba(139, 21, 56, 0.85)",
            "rgba(169, 29, 69, 0.85)",
            "rgba(109, 16, 41, 0.85)",
          ],
          borderColor: ["#8b1538", "#a91d45", "#6d1029"],
          borderWidth: 2,
          borderRadius: 8,
          borderSkipped: false,
        },
      ],
    },
    options: getGrowthChartOptions("Growth Metrics"),
  });
}

function updateSalesChart(salesData) {
  const labels = salesData.daily.map((item) => formatDate(item.date));
  const data = salesData.daily.map((item) => item.total);

  salesChart.data.labels = labels;
  salesChart.data.datasets[0].data = data;
  salesChart.update();
}

function updateProfitChart(profitData) {
  const labels = profitData.daily.map((item) => formatDate(item.date));
  const data = profitData.daily.map((item) => item.total);

  profitChart.data.labels = labels;
  profitChart.data.datasets[0].data = data;
  profitChart.update();
}

function updateGrowthChart(customerGrowth, invoiceGrowth, carGrowth) {
  growthChart.data.datasets[0].data = [
    customerGrowth.total || 0,
    invoiceGrowth.total || 0,
    carGrowth.total || 0,
  ];
  growthChart.update();
}

function getChartOptions(title) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      intersect: false,
      mode: "index",
    },
    plugins: {
      legend: {
        display: false,
      },
      title: {
        display: false,
      },
      tooltip: {
        backgroundColor: "rgba(139, 21, 56, 0.9)",
        titleColor: "#ffffff",
        bodyColor: "#ffffff",
        borderColor: "#8b1538",
        borderWidth: 1,
        cornerRadius: 8,
        padding: 12,
        displayColors: false,
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        border: {
          display: false,
        },
        grid: {
          color: "rgba(139, 21, 56, 0.08)",
          drawBorder: false,
        },
        ticks: {
          color: "#718096",
          font: {
            size: 11,
          },
          callback: function (value) {
            return formatCurrency(value);
          },
        },
      },
      x: {
        border: {
          display: false,
        },
        grid: {
          display: false,
        },
        ticks: {
          color: "#718096",
          font: {
            size: 11,
          },
        },
      },
    },
  };
}

function getGrowthChartOptions(title) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false,
      },
      title: {
        display: false,
      },
      tooltip: {
        backgroundColor: "rgba(139, 21, 56, 0.9)",
        titleColor: "#ffffff",
        bodyColor: "#ffffff",
        borderColor: "#8b1538",
        borderWidth: 1,
        cornerRadius: 8,
        padding: 12,
        displayColors: false,
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        border: {
          display: false,
        },
        grid: {
          color: "rgba(139, 21, 56, 0.08)",
          drawBorder: false,
        },
        ticks: {
          color: "#718096",
          font: {
            size: 11,
          },
          callback: function (value) {
            return value;
          },
        },
      },
      x: {
        border: {
          display: false,
        },
        grid: {
          display: false,
        },
        ticks: {
          color: "#718096",
          font: {
            size: 11,
          },
        },
      },
    },
  };
}

// ===== ALERT FUNCTIONS =====
function updateLowStockAlerts(lowStockData) {
  const container = document.getElementById("low-stock-list");
  const countElement = document.getElementById("low-stock-count");

  countElement.textContent = lowStockData.length;

  if (lowStockData.length === 0) {
    container.innerHTML = '<p class="no-alerts">No low stock items</p>';
    return;
  }

  container.innerHTML = lowStockData
    .map(
      (item) => `
        <div class="alert-item">
            <span class="alert-item-name">${item.item_name}</span>
            <span class="alert-item-value">${item.quantity} / ${item.reorder_level}</span>
        </div>
    `
    )
    .join("");
}

function updateOpenRepairs(openRepairsData) {
  const container = document.getElementById("open-repairs-list");
  const countElement = document.getElementById("open-repairs-count");

  countElement.textContent = openRepairsData.length;

  if (openRepairsData.length === 0) {
    container.innerHTML = '<p class="no-alerts">No open repair orders</p>';
    return;
  }

  container.innerHTML = openRepairsData
    .slice(0, 5)
    .map(
      (repair) => `
        <div class="alert-item">
            <span class="alert-item-name">#${repair.id} - ${repair.customer_name}</span>
            <span class="alert-item-value">${repair.status}</span>
        </div>
    `
    )
    .join("");
}

function updatePendingQuotes(pendingQuotesData) {
  const container = document.getElementById("pending-quotes-list");
  const countElement = document.getElementById("pending-quotes-count");

  countElement.textContent = pendingQuotesData.length;

  if (pendingQuotesData.length === 0) {
    container.innerHTML = '<p class="no-alerts">No pending quotes</p>';
    return;
  }

  container.innerHTML = pendingQuotesData
    .slice(0, 5)
    .map(
      (quote) => `
        <div class="alert-item">
            <span class="alert-item-name">#${quote.id} - ${
        quote.customer_name
      }</span>
            <span class="alert-item-value">${formatCurrency(
              quote.total_amount
            )}</span>
        </div>
    `
    )
    .join("");
}

// ===== TABLE FUNCTIONS =====
function updateVendorsTable(vendorBalancesData) {
  const tbody = document.querySelector("#vendors-table tbody");

  if (vendorBalancesData.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="2" class="no-data">No vendors with outstanding balance</td></tr>';
    return;
  }

  tbody.innerHTML = vendorBalancesData
    .map(
      (vendor) => `
        <tr>
            <td>${vendor.vendor_name}</td>
            <td>${formatCurrency(vendor.closing_balance)}</td>
        </tr>
    `
    )
    .join("");
}

function updateCompletedTodayTable(completedTodayData) {
  const tbody = document.querySelector("#completed-today-table tbody");

  if (completedTodayData.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="4" class="no-data">No repair orders completed today</td></tr>';
    return;
  }

  tbody.innerHTML = completedTodayData
    .map(
      (repair) => `
        <tr>
            <td>#${repair.id}</td>
            <td>${repair.customer_name}</td>
            <td>${repair.customer_phone || "N/A"}</td>
            <td><span class="status-badge completed">${
              repair.status
            }</span></td>
        </tr>
    `
    )
    .join("");
}

// ===== UTILITY FUNCTIONS =====
function formatCurrency(amount) {
  return new Intl.NumberFormat("en-PK", {
    style: "currency",
    currency: "PKR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount || 0);
}

function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString("en-PK", {
    month: "short",
    day: "numeric",
  });
}

function getPeriodText(period) {
  const periodMap = {
    day: "Today",
    week: "This Week",
    month: "This Month",
    year: "This Year",
  };
  return periodMap[period] || "This Month";
}

function getFilterText() {
  const filterMap = {
    today: "Today",
    "7days": "Last 7 Days",
    "30days": "Last 30 Days",
    year: "This Year",
    custom: "Custom Range",
  };
  return filterMap[currentFilter] || "Last 30 Days";
}

// ===== EVENT LISTENERS =====
document
  .getElementById("period-select")
  .addEventListener("change", loadReports);
document.getElementById("start-date").addEventListener("change", function () {
  // If user manually changes date, switch to custom filter
  if (currentFilter !== "custom") {
    setQuickFilter("custom");
  }
  loadReports();
});
document.getElementById("end-date").addEventListener("change", function () {
  // If user manually changes date, switch to custom filter
  if (currentFilter !== "custom") {
    setQuickFilter("custom");
  }
  loadReports();
});

// ===== EXPORT FUNCTIONS =====
function exportToPDF() {
  showInfo("PDF export feature coming soon!");
}

function exportToExcel() {
  showInfo("Excel export feature coming soon!");
}

// ===== REFRESH FUNCTION =====
function refreshData() {
  loadReports();
}

// ===== BACK BUTTON FUNCTIONALITY =====
function setupBackButton() {
  const backBtn = document.getElementById("back-btn");
  if (backBtn) {
    backBtn.addEventListener("click", function (e) {
      e.preventDefault();
      const urlParams = new URLSearchParams(window.location.search);
      const from = urlParams.get("from");

      if (from === "home") {
        window.location.href = "home.html";
      } else {
        window.location.href = "home.html";
      }
    });
  }
}
