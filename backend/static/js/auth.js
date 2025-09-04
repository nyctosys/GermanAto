// Authentication utility functions
class AuthManager {
  constructor() {
    this.user = null;
    this.isAuthenticated = false;
    this.init();
  }

  init() {
    // Check if user is authenticated
    const userStr = localStorage.getItem("user");
    const isAuth = localStorage.getItem("isAuthenticated");

    if (userStr && isAuth === "true") {
      this.user = JSON.parse(userStr);
      this.isAuthenticated = true;
    }
  }

  // Check if user has required role
  hasRole(requiredRole) {
    if (!this.isAuthenticated || !this.user) {
      return false;
    }

    const roleHierarchy = {
      admin: ["admin", "accountant", "inventory_manager"],
      accountant: ["accountant"],
      inventory_manager: ["inventory_manager"],
    };

    return (
      roleHierarchy[requiredRole] &&
      roleHierarchy[requiredRole].includes(this.user.role)
    );
  }

  // Check if user can access a specific page
  canAccessPage(pageName) {
    const pagePermissions = {
      home: ["admin", "accountant", "inventory_manager"],
      invoice: ["admin", "accountant"],
      search: ["admin", "accountant"],
      inventory: ["admin", "inventory_manager"],
      car: ["admin", "accountant"],
      reports: ["admin"], // Removed accountant access
      admin: ["admin"],
      "daily-expenses": ["admin", "accountant"],
    };

    return (
      pagePermissions[pageName] &&
      pagePermissions[pageName].includes(this.user.role)
    );
  }

  // Redirect to login if not authenticated
  requireAuth() {
    if (!this.isAuthenticated) {
      window.location.href = "login.html";
      return false;
    }
    return true;
  }

  // Check page access and redirect if not authorized
  requirePageAccess(pageName) {
    if (!this.requireAuth()) {
      return false;
    }

    if (!this.canAccessPage(pageName)) {
      alert("You do not have permission to access this page.");
      this.redirectToHome();
      return false;
    }

    return true;
  }

  // Redirect to appropriate home page based on role
  redirectToHome() {
    if (!this.isAuthenticated) {
      window.location.href = "login.html";
      return;
    }

    switch (this.user.role) {
      case "inventory_manager":
        window.location.href = "inventory.html";
        break;
      case "admin":
      case "accountant":
      default:
        window.location.href = "home.html";
        break;
    }
  }

  // Logout user
  logout() {
    fetch("/api/auth/logout", {
      method: "POST",
      credentials: "include",
    }).finally(() => {
      localStorage.removeItem("user");
      localStorage.removeItem("isAuthenticated");
      this.user = null;
      this.isAuthenticated = false;
      window.location.href = "login.html";
    });
  }

  // Get current user info
  getCurrentUser() {
    return this.user;
  }

  // Check if user is admin
  isAdmin() {
    return this.hasRole("admin");
  }

  // Check if user is accountant
  isAccountant() {
    return this.hasRole("accountant");
  }

  // Check if user is inventory manager
  isInventoryManager() {
    return this.hasRole("inventory_manager");
  }
}

// Create global auth instance
const auth = new AuthManager();

// Add logout functionality to all pages
document.addEventListener("DOMContentLoaded", function () {
  // Add logout button only on home page if user is authenticated
  if (auth.isAuthenticated && window.location.pathname.includes("home.html")) {
    addLogoutButton();
  }
});

function addLogoutButton() {
  // Create logout button
  const logoutBtn = document.createElement("button");
  logoutBtn.textContent = "Logout";
  logoutBtn.className = "logout-btn";
  logoutBtn.onclick = () => auth.logout();

  // Add to page (you can customize where to place it)
  const header = document.querySelector(".header") || document.body;
  header.appendChild(logoutBtn);
}

// Export for use in other scripts
window.AuthManager = AuthManager;
window.auth = auth;
