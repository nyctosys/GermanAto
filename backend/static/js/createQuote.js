/**
 * Create Quote.
 *
 * A quote and an invoice differ in three ways that matter, which is why this
 * is a separate page rather than a mode:
 *
 *   - a quote reserves no stock, so there is nothing to deduct;
 *   - nothing is owed on it, so there is no advance and no balance;
 *   - its status is always 'pending' - payment has no meaning until it
 *     becomes an invoice.
 *
 * Everything else - customers, cars, items, totals - is genuinely shared and
 * comes from invoiceShared.js.
 */

import {
  loadCustomers,
  loadCars,
  loadInventory,
  setupSearchableDropdowns,
  setupCommonEventListeners,
  collectFormData,
  validateFormData,
  updateCustomerAndCarRecords,
  resetForm,
} from "./invoiceShared.js";

async function initializeCreateQuote() {
  const form = document.getElementById("quote-form");
  if (!form) {
    setTimeout(initializeCreateQuote, 100);
    return;
  }

  loadCustomers();
  loadCars();
  await loadInventory();

  setupSearchableDropdowns();
  setupCommonEventListeners();

  form.addEventListener("submit", handleQuoteSubmit);
}

async function handleQuoteSubmit(event) {
  event.preventDefault();

  const formData = collectFormData();
  if (!validateFormData(formData)) return;

  const quoteData = {
    ...formData,
    type_of: "Quote",
    // A quote is not owed, so it carries no payment. The server agrees:
    // calculate_invoice_status() returns 'pending' for a quote regardless.
    advance: 0,
    balance: formData.net_total,
  };

  const button = event.submitter;
  if (button) button.disabled = true;

  try {
    await updateCustomerAndCarRecords(formData);

    const result = await APIHelper.post("/api/add", quoteData);
    if (!result) return;

    sessionStorage.setItem("invoiceData", JSON.stringify(quoteData));
    sessionStorage.setItem("invoiceId", result.invoice_id);
    sessionStorage.setItem("documentType", "quote");

    window.location.href = `invoice-template.html?from=quote&id=${result.invoice_id}`;
    resetForm();
  } catch (error) {
    console.error("Error creating quote:", error);
    const message = error?.message || "Could not create the quote. Please try again.";
    if (typeof showError === "function") showError(message);
    else alert(message);
  } finally {
    if (button) button.disabled = false;
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeCreateQuote);
} else {
  initializeCreateQuote();
}
