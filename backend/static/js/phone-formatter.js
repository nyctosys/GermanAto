// Phone number formatting utility for Pakistani phone numbers
// Formats: 0xxx xxxxxx (10 digits), 0xxx xxxxxxx (11 digits), or +92 xxx xxxxxxx

/**
 * Format phone number as user types
 * @param {string} value - The phone number value
 * @returns {string} - Formatted phone number
 */
function formatPhoneNumber(value) {
  if (!value) return '';
  
  // Remove all non-digit characters except +
  let cleaned = value.replace(/[^\d+]/g, '');
  
  // Handle +92 format (international)
  if (cleaned.startsWith('+92')) {
    const digits = cleaned.substring(3); // Remove +92
    if (digits.length === 0) {
      return '+92';
    } else if (digits.length <= 3) {
      return `+92 ${digits}`;
    } else if (digits.length <= 10) {
      return `+92 ${digits.substring(0, 3)} ${digits.substring(3)}`;
    } else {
      // Limit to 10 digits after +92
      return `+92 ${digits.substring(0, 3)} ${digits.substring(3, 10)}`;
    }
  }
  
  // Handle local format (starting with 0)
  if (cleaned.startsWith('0')) {
    if (cleaned.length <= 4) {
      return cleaned;
    } else if (cleaned.length <= 10) {
      // Format as 0xxx xxxxxx (10 digits)
      return `${cleaned.substring(0, 4)} ${cleaned.substring(4)}`;
    } else if (cleaned.length <= 11) {
      // Format as 0xxx xxxxxxx (11 digits)
      return `${cleaned.substring(0, 4)} ${cleaned.substring(4)}`;
    } else {
      // Limit to 11 digits
      return `${cleaned.substring(0, 4)} ${cleaned.substring(4, 11)}`;
    }
  }
  
  // Handle numbers without leading 0
  if (cleaned.length === 0) {
    return '';
  } else if (cleaned.length <= 3) {
    return cleaned;
  } else if (cleaned.length <= 9) {
    // Auto-add 0 if user is typing a number
    return `0${cleaned.substring(0, 3)} ${cleaned.substring(3)}`;
  } else if (cleaned.length <= 10) {
    // 10 digits - format as 0xxx xxxxxx
    return `0${cleaned.substring(0, 3)} ${cleaned.substring(3)}`;
  } else {
    // 11 digits - format as 0xxx xxxxxxx
    return `0${cleaned.substring(0, 3)} ${cleaned.substring(3, 11)}`;
  }
}

/**
 * Setup phone number formatting for an input field
 * @param {string|HTMLElement} inputIdOrElement - Input ID or element
 */
function setupPhoneFormatter(inputIdOrElement) {
  const input = typeof inputIdOrElement === 'string' 
    ? document.getElementById(inputIdOrElement)
    : inputIdOrElement;
  
  if (!input) return;
  
  // Format on input
  input.addEventListener('input', function(e) {
    const cursorPosition = this.selectionStart;
    const oldValue = this.value;
    const newValue = formatPhoneNumber(this.value);
    
    // Only update if value changed
    if (oldValue !== newValue) {
      this.value = newValue;
      
      // Calculate new cursor position
      // Count digits before cursor in old value
      const digitsBeforeCursor = (oldValue.substring(0, cursorPosition).match(/\d/g) || []).length;
      
      // Find position in new value with same number of digits before it
      let newCursorPosition = 0;
      let digitCount = 0;
      for (let i = 0; i < newValue.length; i++) {
        if (/\d/.test(newValue[i])) {
          digitCount++;
          if (digitCount === digitsBeforeCursor) {
            newCursorPosition = i + 1;
            break;
          }
        }
      }
      
      // If we didn't find exact position, place at end
      if (newCursorPosition === 0) {
        newCursorPosition = newValue.length;
      }
      
      this.setSelectionRange(newCursorPosition, newCursorPosition);
    }
  });
  
  // Format on paste
  input.addEventListener('paste', function(e) {
    setTimeout(() => {
      const oldValue = this.value;
      const newValue = formatPhoneNumber(this.value);
      if (oldValue !== newValue) {
        this.value = newValue;
      }
    }, 0);
  });
  
  // Format on blur (final format)
  input.addEventListener('blur', function(e) {
    const oldValue = this.value;
    const newValue = formatPhoneNumber(this.value);
    if (oldValue !== newValue) {
      this.value = newValue;
    }
  });
}

/**
 * Setup phone formatters for all phone inputs on the page
 */
function setupAllPhoneFormatters() {
  // Common phone input IDs
  const phoneInputIds = [
    'customer_phone',
    'customer-phone',
    'modal-customer-phone',
    'phone',
    'editPhone',
    'editEmergencyContactPhone'
  ];
  
  phoneInputIds.forEach(id => {
    setupPhoneFormatter(id);
  });
  
  // Also setup for any input with type="tel" that doesn't have an ID
  document.querySelectorAll('input[type="tel"]').forEach(input => {
    if (!input.id || !phoneInputIds.includes(input.id)) {
      setupPhoneFormatter(input);
    }
  });
}

// Auto-setup when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', setupAllPhoneFormatters);
} else {
  setupAllPhoneFormatters();
}

// Export for manual use
window.formatPhoneNumber = formatPhoneNumber;
window.setupPhoneFormatter = setupPhoneFormatter;
window.setupAllPhoneFormatters = setupAllPhoneFormatters;
