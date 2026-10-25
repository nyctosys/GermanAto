/**
 * DEPRECATED: This file is no longer used.
 * 
 * Invoice functionality has been split into separate modules for better isolation:
 * - invoiceShared.js - Common utilities shared between create and edit
 * - createInvoice.js - Logic for creating new invoices/quotes
 * - editInvoice.js - Logic for editing existing invoices/quotes
 * 
 * The HTML now conditionally loads the appropriate module based on URL parameters.
 * This file is kept for reference only and will be removed in a future cleanup.
 */

console.warn(
  "DEPRECATED: script.js is no longer used. " +
  "Invoice functionality has been split into createInvoice.js and editInvoice.js"
);
