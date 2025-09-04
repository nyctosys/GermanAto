// Finance Management JavaScript

function navigateToBillManagement() {
  window.location.href = "invoiceSystem.html?from=finance";
}

function navigateToDailyExpenses() {
  window.location.href = "daily-expenses.html?from=finance";
}

// Wait for DOM to be fully loaded
document.addEventListener("DOMContentLoaded", function () {
  // Find the back button
  const backBtn = document.getElementById("back-btn");

  if (backBtn) {
    // Add click event listener
    backBtn.addEventListener("click", function (e) {
      e.preventDefault();

      // Get URL parameters
      const urlParams = new URLSearchParams(window.location.search);
      const from = urlParams.get("from");

      // Determine where to go back to
      let targetPage = "home.html"; // default

      if (from === "home") {
        targetPage = "home.html";
      } else if (from === "admin") {
        targetPage = "admin.html";
      } else {
        targetPage = "home.html"; // default fallback
      }

      window.location.href = targetPage;
    });
  }
});

// Also try to set up the back button immediately if DOM is already loaded
if (document.readyState === "loading") {
  // DOM still loading, waiting for DOMContentLoaded
} else {
  // DOM already loaded, set up back button immediately
  const backBtn = document.getElementById("back-btn");
  if (backBtn) {
    backBtn.addEventListener("click", function (e) {
      e.preventDefault();

      const urlParams = new URLSearchParams(window.location.search);
      const from = urlParams.get("from");

      let targetPage = "home.html";
      if (from === "home") {
        targetPage = "home.html";
      } else if (from === "admin") {
        targetPage = "admin.html";
      }

      window.location.href = targetPage;
    });
  }
}
