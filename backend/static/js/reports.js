// ===== GLOBAL VARIABLES =====
let reportsData = null;
let salesChart = null;
let profitChart = null;
let growthChart = null;

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
  document.getElementById("sales-period").textContent = getPeriodText(period);

  // Update expenses
  document.getElementById("expenses-total").textContent = formatCurrency(
    expenses.total || 0
  );
  document.getElementById("expenses-period").textContent =
    getPeriodText(period);

  // Update profit
  document.getElementById("profit-total").textContent = formatCurrency(
    profit.total || 0
  );
  document.getElementById("profit-period").textContent = getPeriodText(period);

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
  // Sales Chart
  const salesCtx = document.getElementById("sales-chart").getContext("2d");
  salesChart = new Chart(salesCtx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Sales",
          data: [],
          borderColor: "#10b981",
          backgroundColor: "rgba(16, 185, 129, 0.1)",
          borderWidth: 3,
          fill: true,
          tension: 0.4,
        },
      ],
    },
    options: getChartOptions("Sales Trend"),
  });

  // Profit Chart
  const profitCtx = document.getElementById("profit-chart").getContext("2d");
  profitChart = new Chart(profitCtx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Profit",
          data: [],
          borderColor: "#3b82f6",
          backgroundColor: "rgba(59, 130, 246, 0.1)",
          borderWidth: 3,
          fill: true,
          tension: 0.4,
        },
      ],
    },
    options: getChartOptions("Profit Trend"),
  });

  // Growth Chart
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
            "rgba(139, 92, 246, 0.8)",
            "rgba(16, 185, 129, 0.8)",
            "rgba(59, 130, 246, 0.8)",
          ],
          borderColor: ["#8b5cf6", "#10b981", "#3b82f6"],
          borderWidth: 2,
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
    plugins: {
      legend: {
        display: false,
      },
      title: {
        display: false,
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        grid: {
          color: "rgba(0, 0, 0, 0.1)",
        },
        ticks: {
          callback: function (value) {
            return formatCurrency(value);
          },
        },
      },
      x: {
        grid: {
          color: "rgba(0, 0, 0, 0.1)",
        },
      },
    },
    elements: {
      point: {
        radius: 4,
        hoverRadius: 6,
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
    },
    scales: {
      y: {
        beginAtZero: true,
        grid: {
          color: "rgba(0, 0, 0, 0.1)",
        },
        ticks: {
          callback: function (value) {
            return value; // Show numbers without currency formatting
          },
        },
      },
      x: {
        grid: {
          color: "rgba(0, 0, 0, 0.1)",
        },
      },
    },
    elements: {
      point: {
        radius: 4,
        hoverRadius: 6,
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

// ===== EVENT LISTENERS =====
document
  .getElementById("period-select")
  .addEventListener("change", loadReports);
document.getElementById("start-date").addEventListener("change", loadReports);
document.getElementById("end-date").addEventListener("change", loadReports);

// ===== EXPORT FUNCTIONS =====
function exportToPDF() {
  // This would implement PDF export functionality
  showInfo("PDF export feature coming soon!");
}

function exportToExcel() {
  // This would implement Excel export functionality
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
      // Check if we came from home page
      const urlParams = new URLSearchParams(window.location.search);
      const from = urlParams.get("from");

      if (from === "home") {
        window.location.href = "home.html";
      } else {
        // Default to home page
        window.location.href = "home.html";
      }
    });
  }
}
