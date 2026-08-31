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
      const result = await auth.login(username, password);

      if (result.success) {
        // Redirect based on role
        redirectBasedOnRole(result.user.role);
      } else {
        showError(result.error || "Login failed. Please try again.");
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
    // auth.redirectToHome() owns this decision so login and every in-app
    // "go home" agree: admins land on reports, everyone else on the dashboard.
    auth.redirectToHome();
  }

  async function checkAuthStatus() {
    if (auth.isAuthenticated) {
      // User is already logged in, redirect based on role
      redirectBasedOnRole(auth.user.role);
    }
  }
});
