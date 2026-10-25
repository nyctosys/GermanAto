/**
 * Performance Utilities for GermanATO
 * Provides optimized data loading and caching mechanisms
 */

class PerformanceUtils {
  constructor() {
    this.cache = new Map();
    this.loadingPromises = new Map();
    this.retryAttempts = 3;
    this.retryDelay = 1000; // 1 second
  }

  /**
   * Batch multiple API requests into a single call
   * @param {Array} requests - Array of request objects {url, options}
   * @returns {Promise<Array>} - Array of responses
   */
  async batchRequests(requests) {
    const promises = requests.map((req) =>
      this.fetchWithRetry(req.url, req.options)
    );
    return Promise.all(promises);
  }

  /**
   * Fetch data with retry logic and caching
   * @param {string} url - API endpoint
   * @param {Object} options - Fetch options
   * @param {number} cacheTime - Cache duration in milliseconds (default: 5 minutes)
   * @returns {Promise<any>} - Response data
   */
  async fetchWithRetry(url, options = {}, cacheTime = 300000) {
    // Check cache first
    const cacheKey = `${url}_${JSON.stringify(options)}`;
    const cached = this.getFromCache(cacheKey, cacheTime);
    if (cached) {
      return cached;
    }

    // Check if already loading
    if (this.loadingPromises.has(cacheKey)) {
      return this.loadingPromises.get(cacheKey);
    }

    // Create loading promise
    const loadingPromise = this._fetchWithRetryInternal(url, options);
    this.loadingPromises.set(cacheKey, loadingPromise);

    try {
      const result = await loadingPromise;
      this.setCache(cacheKey, result);
      return result;
    } finally {
      this.loadingPromises.delete(cacheKey);
    }
  }

  /**
   * Internal method to handle retry logic
   */
  async _fetchWithRetryInternal(url, options) {
    let lastError;

    for (let attempt = 1; attempt <= this.retryAttempts; attempt++) {
      try {
        // Prepare headers with JWT authentication
        const headers = {
          "Content-Type": "application/json",
          ...options.headers,
        };

        // Add JWT token if available
        if (window.auth && window.auth.getAccessToken()) {
          headers["Authorization"] = `Bearer ${window.auth.getAccessToken()}`;
        }

        const response = await fetch(url, {
          ...options,
          headers,
        });

        // Handle 401 responses (token expired)
        if (response.status === 401) {
          // Try to refresh the token if auth is available
          if (window.auth && window.auth.refreshAccessToken) {
            const refreshSuccess = await window.auth.refreshAccessToken();

            if (refreshSuccess) {
              // Retry the request with new token
              headers[
                "Authorization"
              ] = `Bearer ${window.auth.getAccessToken()}`;
              const retryResponse = await fetch(url, {
                ...options,
                headers,
              });

              if (!retryResponse.ok) {
                throw new Error(
                  `HTTP ${retryResponse.status}: ${retryResponse.statusText}`
                );
              }

              const retryData = await retryResponse.json();
              return retryData;
            } else {
              // Refresh failed, redirect to login
              if (window.auth && window.auth.clearAuth) {
                window.auth.clearAuth();
                window.location.href = "login.html";
              }
              throw new Error("Authentication failed");
            }
          } else {
            throw new Error("Authentication failed");
          }
        }

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        return data;
      } catch (error) {
        lastError = error;
        console.warn(`Attempt ${attempt} failed for ${url}:`, error.message);

        if (attempt < this.retryAttempts) {
          await this.delay(this.retryDelay * attempt);
        }
      }
    }

    throw lastError;
  }

  /**
   * Load initial data for pages (customers, cars, inventory)
   * @returns {Promise<Object>} - Combined data object
   */
  async loadInitialData() {
    const requests = [
      { url: "/api/customers", options: { method: "GET" } },
      { url: "/api/cars", options: { method: "GET" } },
      { url: "/api/inventory", options: { method: "GET" } },
    ];

    try {
      const [customers, cars, inventory] = await this.batchRequests(requests);

      return {
        customers: customers || [],
        cars: cars || [],
        inventory: inventory?.items || inventory || [],
      };
    } catch (error) {
      console.error("Error loading initial data:", error);
      return {
        customers: [],
        cars: [],
        inventory: [],
      };
    }
  }

  /**
   * Show loading state with spinner
   * @param {string} elementId - ID of element to show loading in
   * @param {string} message - Loading message
   */
  showLoading(elementId, message = "Loading...") {
    const element = document.getElementById(elementId);
    if (element) {
      element.innerHTML = `
                <div class="loading-container" style="
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    padding: 2rem;
                    flex-direction: column;
                ">
                    <div class="loading-spinner" style="
                        width: 40px;
                        height: 40px;
                        border: 4px solid #f3f3f3;
                        border-top: 4px solid #007bff;
                        border-radius: 50%;
                        animation: spin 1s linear infinite;
                        margin-bottom: 1rem;
                    "></div>
                    <div class="loading-text">${message}</div>
                </div>
                <style>
                    @keyframes spin {
                        0% { transform: rotate(0deg); }
                        100% { transform: rotate(360deg); }
                    }
                </style>
            `;
    }
  }

  /**
   * Hide loading state
   * @param {string} elementId - ID of element to hide loading in
   */
  hideLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
      const loadingContainer = element.querySelector(".loading-container");
      if (loadingContainer) {
        loadingContainer.remove();
      }
    }
  }

  /**
   * Show error message with retry option
   * @param {string} elementId - ID of element to show error in
   * @param {string} message - Error message
   * @param {Function} retryCallback - Function to call on retry
   */
  showError(elementId, message, retryCallback = null) {
    const element = document.getElementById(elementId);
    if (element) {
      element.innerHTML = `
                <div class="error-container" style="
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    padding: 2rem;
                    flex-direction: column;
                    color: #dc3545;
                ">
                    <div style="font-size: 2rem; margin-bottom: 1rem;"></div>
                    <div class="error-message" style="margin-bottom: 1rem;">${message}</div>
                    ${
                      retryCallback
                        ? `
                        <button onclick="${retryCallback.name}()" style="
                            background: #007bff;
                            color: white;
                            border: none;
                            padding: 0.5rem 1rem;
                            border-radius: 4px;
                            cursor: pointer;
                        ">Retry</button>
                    `
                        : ""
                    }
                </div>
            `;
    }
  }

  /**
   * Cache management methods
   */
  setCache(key, value) {
    this.cache.set(key, {
      data: value,
      timestamp: Date.now(),
    });
  }

  getFromCache(key, maxAge) {
    const cached = this.cache.get(key);
    if (cached && Date.now() - cached.timestamp < maxAge) {
      return cached.data;
    }
    if (cached) {
      this.cache.delete(key);
    }
    return null;
  }

  clearCache() {
    this.cache.clear();
  }

  /**
   * Utility method for delays
   */
  delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Debounce function calls
   * @param {Function} func - Function to debounce
   * @param {number} wait - Wait time in milliseconds
   * @returns {Function} - Debounced function
   */
  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  /**
   * Throttle function calls
   * @param {Function} func - Function to throttle
   * @param {number} limit - Time limit in milliseconds
   * @returns {Function} - Throttled function
   */
  throttle(func, limit) {
    let inThrottle;
    return function executedFunction(...args) {
      if (!inThrottle) {
        func.apply(this, args);
        inThrottle = true;
        setTimeout(() => (inThrottle = false), limit);
      }
    };
  }
}

// Create global instance immediately
window.PerformanceUtils = new PerformanceUtils();

// Also make sure it's available when DOM is ready (if document exists)
if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      if (!window.PerformanceUtils) {
        window.PerformanceUtils = new PerformanceUtils();
      }
    });
  } else {
    // Document is already ready
    if (!window.PerformanceUtils) {
      window.PerformanceUtils = new PerformanceUtils();
    }
  }
}

// Export for module systems
if (typeof module !== "undefined" && module.exports) {
  module.exports = PerformanceUtils;
}
