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
  localStorage.setItem("lastPage", "reports");

  // Load summary data
  loadSummaryData();

  // Update summary cards
  async function loadSummaryData() {
    try {
      const response = await fetch("/api/reports/summary");
      if (response.ok) {
        const data = await response.json();

        // Update summary cards
        document.getElementById("total-invoices").textContent =
          data.total_invoices || 0;
        document.getElementById("total-cars").textContent =
          data.total_cars || 0;
        document.getElementById("total-customers").textContent =
          data.total_customers || 0;
        document.getElementById("total-inventory-value").textContent =
          data.total_inventory_value
            ? `${data.total_inventory_value.toLocaleString()} PKR`
            : "0 PKR";

        // Handle revenue display with NaN checks
        const totalRevenue = data.total_revenue;
        if (isNaN(totalRevenue) || totalRevenue < 0) {
          document.getElementById("total-revenue").textContent = "0 PKR";
        } else {
          document.getElementById(
            "total-revenue"
          ).textContent = `${totalRevenue.toLocaleString()} PKR`;
        }

        // Handle expenses display with NaN checks
        const totalExpenses = data.total_expenses;
        if (isNaN(totalExpenses) || totalExpenses < 0) {
          document.getElementById("total-expenses").textContent = "0 PKR";
        } else {
          document.getElementById(
            "total-expenses"
          ).textContent = `${totalExpenses.toLocaleString()} PKR`;
        }
      } else {
        console.error("Failed to load summary data");
      }
    } catch (error) {
      console.error("Error loading summary data:", error);
    }
  }

  // Invoices per Month Chart (real data)
  fetch("/api/reports/invoices_per_month")
    .then((res) => res.json())
    .then((chartData) => {
      const ctx = document
        .getElementById("invoices-per-month-chart")
        .getContext("2d");
      new Chart(ctx, {
        type: "bar",
        data: {
          labels: chartData.labels,
          datasets: [
            {
              label: "Invoices",
              data: chartData.data,
              backgroundColor: "#3b82f6",
              borderRadius: 6,
              maxBarThickness: 32,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            title: { display: false },
          },
          scales: {
            y: { beginAtZero: true, ticks: { stepSize: 1 } },
          },
        },
      });
    });

  // Revenue per Month Chart (real data)
  fetch("/api/reports/revenue_per_month")
    .then((res) => res.json())
    .then((chartData) => {
      const ctx = document
        .getElementById("revenue-per-month-chart")
        .getContext("2d");
      new Chart(ctx, {
        type: "line",
        data: {
          labels: chartData.labels,
          datasets: [
            {
              label: "Net Revenue (PKR)",
              data: chartData.data,
              fill: false,
              borderColor: "#10b981",
              backgroundColor: "#10b981",
              tension: 0.3,
              pointRadius: 4,
              pointBackgroundColor: "#10b981",
              pointBorderColor: "#fff",
              pointHoverRadius: 6,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            title: { display: false },
            tooltip: {
              callbacks: {
                label: function (context) {
                  let label = context.label || "";
                  let value = context.parsed.y || 0;
                  return `${label}: ${Number(
                    value
                  ).toLocaleString()} PKR (Net)`;
                },
              },
            },
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: {
                callback: function (value) {
                  return Number(value).toLocaleString() + " PKR";
                },
              },
            },
          },
        },
      });
    });

  // Inventory Value by Category Chart (real data)
  fetch("/api/reports/inventory_by_category")
    .then((res) => res.json())
    .then((chartData) => {
      const ctx = document
        .getElementById("inventory-by-category-chart")
        .getContext("2d");
      new Chart(ctx, {
        type: "doughnut",
        data: {
          labels: chartData.labels,
          datasets: [
            {
              label: "Inventory Value (PKR)",
              data: chartData.data,
              backgroundColor: [
                "#3b82f6",
                "#10b981",
                "#f59e42",
                "#a78bfa",
                "#f43f5e",
                "#6366f1",
                "#fbbf24",
                "#14b8a6",
              ],
              borderWidth: 1,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: "bottom" },
            title: { display: false },
            tooltip: {
              callbacks: {
                label: function (context) {
                  let label = context.label || "";
                  let value = context.parsed || 0;
                  return `${label}: ${Number(value).toLocaleString()} PKR`;
                },
              },
            },
          },
        },
      });
    });

  // Top-Selling Products Chart
  fetch("/api/reports/top_products")
    .then((res) => res.json())
    .then((chartData) => {
      const ctx = document
        .getElementById("top-products-chart")
        .getContext("2d");
      new Chart(ctx, {
        type: "bar",
        data: {
          labels: chartData.labels,
          datasets: [
            {
              label: "Quantity Sold",
              data: chartData.data,
              backgroundColor: "#f59e42",
              borderRadius: 6,
              maxBarThickness: 32,
            },
          ],
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            title: { display: false },
          },
          scales: {
            x: { beginAtZero: true, ticks: { stepSize: 1 } },
          },
        },
      });
    });

  // Customer Growth Chart
  fetch("/api/reports/customer_growth")
    .then((res) => res.json())
    .then((chartData) => {
      const ctx = document
        .getElementById("customer-growth-chart")
        .getContext("2d");
      new Chart(ctx, {
        type: "line",
        data: {
          labels: chartData.labels,
          datasets: [
            {
              label: "New Customers",
              data: chartData.data,
              fill: false,
              borderColor: "#10b981",
              backgroundColor: "#10b981",
              tension: 0.3,
              pointRadius: 4,
              pointBackgroundColor: "#10b981",
              pointBorderColor: "#fff",
              pointHoverRadius: 6,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            title: { display: false },
          },
          scales: {
            y: { beginAtZero: true, ticks: { stepSize: 1 } },
          },
        },
      });
    });
});
