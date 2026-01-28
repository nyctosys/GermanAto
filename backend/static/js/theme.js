/**
 * Global Theme Management
 * This file should be included in ALL pages (in <head>) for consistent theming
 * Include this BEFORE other scripts to prevent flash of unstyled content
 */

(function() {
  // Apply theme immediately to prevent flash
  const savedTheme = localStorage.getItem("theme") || "light";
  
  function applyTheme(theme) {
    const body = document.body || document.documentElement;
    
    // Remove existing theme classes
    body.classList.remove("dark-theme", "light-theme");
    
    if (theme === "dark") {
      body.classList.add("dark-theme");
    } else if (theme === "auto") {
      // Check system preference
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      if (prefersDark) {
        body.classList.add("dark-theme");
      } else {
        body.classList.add("light-theme");
      }
    } else {
      body.classList.add("light-theme");
    }
  }
  
  // Apply immediately if body exists
  if (document.body) {
    applyTheme(savedTheme);
  }
  
  // Also apply when DOM is ready (in case body wasn't available)
  document.addEventListener("DOMContentLoaded", function() {
    applyTheme(savedTheme);
  });
  
  // Listen for system theme changes (for "auto" mode)
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function(e) {
    const currentTheme = localStorage.getItem("theme");
    if (currentTheme === "auto") {
      applyTheme("auto");
    }
  });
  
  // Expose function globally for settings page to use
  window.applyGlobalTheme = applyTheme;
})();
