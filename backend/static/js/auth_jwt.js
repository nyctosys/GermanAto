// JWT-based Authentication Manager

// Sub-pages that are covered by a parent page's permission.
const SUB_PAGE_PERMISSIONS = {
  "vendor-detail": "vendors",
  "worker-detail": "hr",
  search: "invoice",
  "repair-orders-management": "repair-order",
};

class AuthManager {
  constructor() {
    this.user = null;
    this.isAuthenticated = false;
    this.accessToken = null;
    this.refreshToken = null;
    this.ready = this.init();
  }

  async init() {
    // Load tokens from localStorage
    this.accessToken = localStorage.getItem("accessToken");
    this.refreshToken = localStorage.getItem("refreshToken");
    this.user = JSON.parse(localStorage.getItem("user") || "null");
    this.isAuthenticated = !!this.accessToken;

    // If we have tokens, verify them with the server
    if (this.isAuthenticated) {
      if (!(await this.verifyToken())) {
        this.requireAuth();
        return;
      }
      await this.loadPermissions();
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

        await this.loadPermissions();

        return { success: true, user: data.user };
      } else {
        return { success: false, error: data.error };
      }
    } catch (error) {
      console.error("Login failed:", error);
      return { success: false, error: "Network error. Please try again." };
    }
  }

  async loadPermissions() {
    if (!this.isAuthenticated || !this.accessToken) return;
    try {
      const response = await fetch("/api/auth/permissions/my", {
        method: "GET",
        headers: {
          Authorization: `Bearer ${this.accessToken}`,
          "Content-Type": "application/json",
        },
      });
      if (response.ok) {
        const data = await response.json();
        localStorage.setItem("userPermissions", JSON.stringify(data.permissions));
      }
    } catch (error) {
      console.error("Failed to load user permissions:", error);
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
    localStorage.removeItem("userPermissions");
  }

  // Role checking methods
  hasRole(requiredRole) {
    if (!this.isAuthenticated || !this.user) {
      return false;
    }

    // admin covers every role; every other role covers only itself
    return this.user.role === "admin" || this.user.role === requiredRole;
  }

  getCachedPermissions() {
    try {
      const perms = JSON.parse(localStorage.getItem("userPermissions"));
      return Array.isArray(perms) ? perms : null;
    } catch (e) {
      console.error("Error parsing userPermissions:", e);
      return null;
    }
  }

  canAccessPage(pageName) {
    if (!this.isAuthenticated || !this.user) {
      return false;
    }

    if (this.user.role === "admin" || pageName === "home") {
      return true;
    }

    const perms = this.getCachedPermissions();

    // Permissions have not arrived yet. The server is the authority on every
    // API call anyway, so let the page start rather than guess and lock the
    // user out of a page they are allowed to see.
    if (!perms) {
      return true;
    }

    return perms.includes(SUB_PAGE_PERMISSIONS[pageName] || pageName);
  }

  requireAuth() {
    if (!this.isAuthenticated) {
      if (!/(^\/$|login\.html$)/.test(window.location.pathname)) {
        window.location.href = "login.html";
      }
      return false;
    }
    return true;
  }

  requirePageAccess(pageName) {
    if (!this.requireAuth()) {
      return false;
    }

    if (this.getCachedPermissions()) {
      return this.enforcePageAccess(pageName);
    }

    // First load after signing in: permissions are still in flight. Let the
    // page initialise and enforce as soon as they land.
    this.ready.then(() => this.enforcePageAccess(pageName));
    return true;
  }

  enforcePageAccess(pageName) {
    if (this.canAccessPage(pageName)) {
      return true;
    }

    alert("You do not have permission to access this page.");
    this.redirectToHome();
    return false;
  }

  redirectToHome() {
    if (!this.isAuthenticated) {
      window.location.href = "login.html";
      return;
    }

    // Admins land on the full business report; everyone else on the dashboard
    // of their own pending work.
    switch (this.user.role) {
      case "inventory_manager":
        window.location.href = "inventory.html";
        break;
      case "admin":
        window.location.href = "reports.html";
        break;
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
