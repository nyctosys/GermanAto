// JWT-based API Helper
class APIHelper {
  static async request(url, options = {}) {
    const defaultOptions = {
      headers: {
        ...options.headers,
      },
    };

    // Only set Content-Type for JSON requests, not for FormData
    if (!(options.body instanceof FormData)) {
      defaultOptions.headers["Content-Type"] = "application/json";
    }

    // Add authorization header if we have a token
    if (auth.getAccessToken()) {
      defaultOptions.headers[
        "Authorization"
      ] = `Bearer ${auth.getAccessToken()}`;
    }

    try {
      const response = await fetch(url, { ...defaultOptions, ...options });

      // Handle 401 responses (token expired)
      if (response.status === 401) {
        // Try to refresh the token
        const refreshSuccess = await auth.refreshAccessToken();

        if (refreshSuccess) {
          // Retry the original request with new token
          defaultOptions.headers[
            "Authorization"
          ] = `Bearer ${auth.getAccessToken()}`;
          const retryResponse = await fetch(url, {
            ...defaultOptions,
            ...options,
          });
          return await retryResponse.json();
        } else {
          // Refresh failed, redirect to login
          auth.clearAuth();
          window.location.href = "login.html";
          return null;
        }
      }

      // Check if response is ok
      if (!response.ok) {
        const errorData = await response
          .json()
          .catch(() => ({ error: "Unknown error" }));
        
        // Include validation details if available
        let errorMessage = errorData.error || `HTTP ${response.status}: ${response.statusText}`;
        if (errorData.details && Array.isArray(errorData.details) && errorData.details.length > 0) {
          errorMessage += '\n\nDetails:\n' + errorData.details.join('\n');
        }
        
        throw new Error(errorMessage);
      }

      // Parse and return JSON response
      return await response.json();
    } catch (error) {
      console.error("API request failed:", error);
      throw error;
    }
  }

  static async get(url) {
    return this.request(url, { method: "GET" });
  }

  static async post(url, data) {
    return this.request(url, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  static async put(url, data) {
    return this.request(url, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  static async delete(url) {
    return this.request(url, { method: "DELETE" });
  }

  static async patch(url, data) {
    return this.request(url, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }
}

// Export for use in other scripts
window.APIHelper = APIHelper;
