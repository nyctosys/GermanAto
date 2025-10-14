// JWT-based Authentication Manager
class AuthManager {
  constructor() {
    this.user = null;
    this.isAuthenticated = false;
    this.accessToken = null;
    this.refreshToken = null;
    this.init();
  }

  async init() {
    // Load tokens from localStorage
    this.accessToken = localStorage.getItem("accessToken");
    this.refreshToken = localStorage.getItem("refreshToken");
    this.user = JSON.parse(localStorage.getItem("user") || "null");
    this.isAuthenticated = !!this.accessToken;

    // If we have tokens, verify them with the server
    if (this.isAuthenticated) {
      await this.verifyToken();
    }
  }

  async verifyToken() {
    try {
      const response = await fetch("/api/auth/verify", {
        method: "GET",
        headers: {
          Authorization: `Bearer ${this.accessToken}`,
          "Content-Type": "application/json",
        },
      });

      if (response.ok) {
        const data = await response.json();
        this.user = data.user;
        this.isAuthenticated = true;
        localStorage.setItem("user", JSON.stringify(data.user));
        return true;
      } else {
        // Token is invalid, try to refresh
        return await this.refreshAccessToken();
      }
    } catch (error) {
      console.error("Token verification failed:", error);
      this.clearAuth();
      return false;
    }
  }

  async refreshAccessToken() {
    if (!this.refreshToken) {
      this.clearAuth();
      return false;
    }

    try {
      const response = await fetch("/api/auth/refresh", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.refreshToken}`,
          "Content-Type": "application/json",
        },
      });

      if (response.ok) {
        const data = await response.json();
        this.accessToken = data.access_token;
        this.user = data.user;
        this.isAuthenticated = true;

        // Update localStorage
        localStorage.setItem("accessToken", this.accessToken);
        localStorage.setItem("user", JSON.stringify(data.user));

        return true;
      } else {
        this.clearAuth();
        return false;
      }
    } catch (error) {
      console.error("Token refresh failed:", error);
      this.clearAuth();
      return false;
    }
  }

  async login(username, password) {
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, password }),
      });

      const data = await response.json();

      if (response.ok) {
        this.accessToken = data.access_token;
        this.refreshToken = data.refresh_token;
        this.user = data.user;
        this.isAuthenticated = true;

        // Store in localStorage
        localStorage.setItem("accessToken", this.accessToken);
        localStorage.setItem("refreshToken", this.refreshToken);
        localStorage.setItem("user", JSON.stringify(data.user));

        return { success: true, user: data.user };
      } else {
        return { success: false, error: data.error };
      }
    } catch (error) {
      console.error("Login failed:", error);
      return { success: false, error: "Network error. Please try again." };
    }
  }

  async logout() {
    try {
      if (this.accessToken) {
        const response = await fetch("/api/auth/logout", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${this.accessToken}`,
            "Content-Type": "application/json",
          },
        });

        if (!response.ok) {
          console.warn(`Logout request failed with status: ${response.status}`);
        }
      }
    } catch (error) {
      console.error("Logout request failed:", error);
      // Don't prevent logout on network errors - still clear local auth
    } finally {
      // Always clear local authentication data regardless of server response
      this.clearAuth();
    }
  }

  clearAuth() {
    this.user = null;
    this.isAuthenticated = false;
    this.accessToken = null;
    this.refreshToken = null;

    localStorage.removeItem("accessToken");
    localStorage.removeItem("refreshToken");
    localStorage.removeItem("user");
  }

  // Role checking methods
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

  canAccessPage(pageName) {
    const pagePermissions = {
      home: ["admin", "accountant", "inventory_manager"],
      invoice: ["admin", "accountant"],
      search: ["admin", "accountant"],
      inventory: ["admin", "inventory_manager"],
      car: ["admin", "accountant"],
      reports: ["admin"],
      admin: ["admin"],
      "daily-expenses": ["admin", "accountant"],
      vendors: ["admin", "accountant"],
      "vendor-detail": ["admin", "accountant"],
      hr: ["admin", "accountant"],
      "worker-detail": ["admin", "accountant"],
      "repair-order": ["admin", "accountant", "inventory_manager"],
      "repair-orders-management": ["admin", "accountant", "inventory_manager"],
    };

    return (
      pagePermissions[pageName] &&
      pagePermissions[pageName].includes(this.user.role)
    );
  }

  requireAuth() {
    if (!this.isAuthenticated) {
      window.location.href = "login.html";
      return false;
    }
    return true;
  }

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

  getCurrentUser() {
    return this.user;
  }

  isAdmin() {
    return this.hasRole("admin");
  }

  isAccountant() {
    return this.hasRole("accountant");
  }

  isInventoryManager() {
    return this.hasRole("inventory_manager");
  }

  getAccessToken() {
    return this.accessToken;
  }
}

// Create global auth instance
const auth = new AuthManager();

// Export for use in other scripts
window.AuthManager = AuthManager;
window.auth = auth;
