document.addEventListener("DOMContentLoaded", function () {
  const loginForm = document.getElementById("login-form");
  const errorMessage = document.getElementById("error-message");
  const loginBtn = document.querySelector(".login-btn");

  // Check if user is already logged in
  checkAuthStatus();

  loginForm.addEventListener("submit", async function (e) {
    e.preventDefault();

    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;

    if (!username || !password) {
      showError("Please enter both username and password");
      return;
    }

    // Disable button and show loading state
    loginBtn.disabled = true;
    loginBtn.textContent = "Logging in...";

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: username,
          password: password,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        // Store user info in localStorage
        localStorage.setItem("user", JSON.stringify(data.user));
        localStorage.setItem("isAuthenticated", "true");

        // Redirect based on role
        redirectBasedOnRole(data.user.role);
      } else {
        showError(data.error || "Login failed. Please try again.");
      }
    } catch (error) {
      console.error("Login error:", error);
      showError("Network error. Please check your connection and try again.");
    } finally {
      // Re-enable button
      loginBtn.disabled = false;
      loginBtn.textContent = "Login";
    }
  });

  function showError(message) {
    errorMessage.textContent = message;
    errorMessage.style.display = "block";

    // Hide error after 5 seconds
    setTimeout(() => {
      errorMessage.style.display = "none";
    }, 5000);
  }

  function redirectBasedOnRole(role) {
    switch (role) {
      case "admin":
        // Admin can access all pages, redirect to home
        window.location.href = "home.html";
        break;
      case "accountant":
        // Accountant can access billing and customer management
        window.location.href = "home.html";
        break;
      case "inventory_manager":
        // Inventory manager redirects to home page
        window.location.href = "home.html";
        break;
      default:
        window.location.href = "home.html";
    }
  }

  async function checkAuthStatus() {
    try {
      const response = await fetch("/api/auth/check-auth");
      const data = await response.json();

      if (data.authenticated) {
        // User is already logged in, redirect based on role
        redirectBasedOnRole(data.user.role);
      }
    } catch (error) {
      console.error("Auth check error:", error);
    }
  }
});
