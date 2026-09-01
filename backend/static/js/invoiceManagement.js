document.addEventListener("DOMContentLoaded", () => {
  // Set up smart back button logic
  const backBtn = document.getElementById("back-btn");
  const urlParams = new URLSearchParams(window.location.search);
  const fromPage =
    urlParams.get("from") ||
    localStorage.getItem("lastPage") ||
    "invoiceSystem";

  // Set back button destination based on where user came from
  if (backBtn) {
    if (fromPage === "home") {
      backBtn.href = "home.html";
    } else if (fromPage === "invoiceSystem") {
      backBtn.href = "invoiceSystem.html";
    } else {
      backBtn.href = "invoiceSystem.html"; // Default fallback
    }
  }

  // Track current page for back button logic
  localStorage.setItem("lastPage", "invoice-management");

  const resultsDiv = document.getElementById("invoice-management-results");
  const keywordSearchInput = document.getElementById("keyword-search-input");
  const idSearchInput = document.getElementById("id-search-input");
  const searchBtn = document.getElementById("search-btn");
  const clearSearchBtn = document.getElementById("clear-search-btn");
  const btnAll = document.getElementById("show-all");
  const btnPaid = document.getElementById("show-paid");
  const btnPartial = document.getElementById("show-partial");
  const btnUnpaid = document.getElementById("show-unpaid");

  // Date filter elements
  const filterToday = document.getElementById("filter-today");
  const filterThisWeek = document.getElementById("filter-this-week");
  const filterThisMonth = document.getElementById("filter-this-month");
  const filterThisYear = document.getElementById("filter-this-year");
  const filterCustom = document.getElementById("filter-custom");
  const clearDateFilter = document.getElementById("clear-date-filter");
  const customRangeContainer = document.getElementById("custom-range-container");
  const dateFromInput = document.getElementById("date-from");
  const dateToInput = document.getElementById("date-to");
  const applyCustomRange = document.getElementById("apply-custom-range");

  let currentStatus = "all";
  let currentKeywordQuery = "";
  let currentIdQuery = "";
  let currentDateFrom = "";
  let currentDateTo = "";

  // Date range calculation functions
  function formatDate(date) {
    return date.toISOString().split('T')[0];
  }

  function getTodayRange() {
    const today = new Date();
    const dateStr = formatDate(today);
    return { from: dateStr, to: dateStr };
  }

  function getThisWeekRange() {
    const today = new Date();
    const dayOfWeek = today.getDay();
    // Calculate Monday (start of week) - if Sunday (0), go back 6 days
    const monday = new Date(today);
    monday.setDate(today.getDate() - (dayOfWeek === 0 ? 6 : dayOfWeek - 1));
    // Calculate Sunday (end of week)
    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    return { from: formatDate(monday), to: formatDate(sunday) };
  }

  function getThisMonthRange() {
    const today = new Date();
    const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
    const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);
    return { from: formatDate(firstDay), to: formatDate(lastDay) };
  }

  function getThisYearRange() {
    const today = new Date();
    const firstDay = new Date(today.getFullYear(), 0, 1);
    const lastDay = new Date(today.getFullYear(), 11, 31);
    return { from: formatDate(firstDay), to: formatDate(lastDay) };
  }

  function setActiveDateButton(activeBtn) {
    [filterToday, filterThisWeek, filterThisMonth, filterThisYear, filterCustom].forEach((btn) => {
      btn.classList.remove("active");
    });
    if (activeBtn) {
      activeBtn.classList.add("active");
    }
  }

  function updateDateFilterVisibility() {
    if (currentDateFrom || currentDateTo) {
      clearDateFilter.style.display = "inline-block";
    } else {
      clearDateFilter.style.display = "none";
    }
  }

  // Function to check if invoice is older than 1 day
  function isInvoiceOlderThanOneDay(createdAtStr) {
    const createdDate = new Date(createdAtStr);
    const currentDate = new Date();
    const oneDayInMs = 24 * 60 * 60 * 1000; // 24 hours in milliseconds
    return currentDate - createdDate > oneDayInMs;
  }

  // Function to check if edit button should be disabled for current user
  function shouldDisableEditButton(invoice) {
    // Get current user from auth system
    const userStr = localStorage.getItem("user");
    if (!userStr) return false;

    const user = JSON.parse(userStr);

    // Admins and accountants can always edit (including invoices older than 1 day)
    if (user.role === "admin" || user.role === "accountant") {
      return false;
    }

    // Other roles cannot edit
    return true;
  }

  async function loadInvoices(status, keywordQuery = "", idQuery = "", dateFrom = "", dateTo = "") {
    APIHelper.renderLoading(resultsDiv, "Loading invoices...");
    try {
      let url = `/api/search?type=invoice`;

      // Add keyword search if provided
      if (keywordQuery) {
        url += `&q=${encodeURIComponent(keywordQuery)}`;
      }

      // Add ID search if provided
      if (idQuery) {
        url += `&id=${encodeURIComponent(idQuery)}`;
      }

      // Add status filter if provided
      if (status && status !== "all") {
        url += `&status=${encodeURIComponent(status)}`;
      }

      // Add date range filter if provided
      if (dateFrom) {
        url += `&date_from=${encodeURIComponent(dateFrom)}`;
      }
      if (dateTo) {
        url += `&date_to=${encodeURIComponent(dateTo)}`;
      }

      const data = await APIHelper.get(url);
      const invoices = data.invoices || [];

      if (invoices.length === 0) {
        const statusText = status && status !== "all" ? status : "";
        let searchText = "";
        if (keywordQuery && idQuery) {
          searchText = ` for keyword "${keywordQuery}" and ID "${idQuery}"`;
        } else if (keywordQuery) {
          searchText = ` for keyword "${keywordQuery}"`;
        } else if (idQuery) {
          searchText = ` for ID "${idQuery}"`;
        }
        resultsDiv.innerHTML = `<p>No ${statusText} invoices found${searchText}.</p>`;
        return;
      }
      let html = '<div class="results-container">';
      html += '<div class="results-column invoices-column">';
      html += `<h3>🧾 Invoices (${invoices.length})</h3>`;
      html += invoices
        .map((invoice) => {
          const invoiceTotal = invoice.net_total !== undefined ? invoice.net_total : (invoice.total || 0);
          const totalWithTax =
            invoice.include_tax && invoice.tax_amount > 0
              ? invoiceTotal + invoice.tax_amount
              : invoiceTotal;
          const taxDisplay =
            invoice.include_tax && invoice.tax_amount > 0
              ? `<p><strong>GST/PST:</strong> ${invoice.tax_amount.toFixed(
                  2
                )} PKR</p>`
              : "";
          const statusDisplay = `<p><strong>Status:</strong> <span class="invoice-status">${
            invoice.status || "N/A"
          }</span></p>`;
          
          let proofLinksHtml = "";
          if (invoice.payments_history && invoice.payments_history.length > 0) {
            const paymentsWithProof = invoice.payments_history.filter(p => p.proof_path);
            if (paymentsWithProof.length > 0) {
              proofLinksHtml = `
                <div class="proof-links" style="margin-top: 8px; font-size: 0.85rem; border-top: 1px dashed #e2e8f0; padding-top: 8px; margin-bottom: 8px;">
                  <strong>Payment Proofs:</strong>
                  <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px;">
                    ${paymentsWithProof.map((p, idx) => `
                      <a href="/static/${p.proof_path}" target="_blank" class="badge" style="background: #2b6cb0; color: white; padding: 2px 6px; border-radius: 4px; text-decoration: none; font-size: 11px; display: inline-flex; align-items: center; gap: 4px;" title="Paid on ${p.timestamp} by ${p.person}">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 10px; height: 10px;">
                          <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path>
                        </svg>
                        Proof #${idx + 1} (${p.amount} PKR)
                      </a>
                    `).join("")}
                  </div>
                </div>
              `;
            }
          }

          // Check if edit button should be disabled
          const isEditDisabled = shouldDisableEditButton(invoice);
          const editButtonClass = isEditDisabled
            ? "wide-btn-edit edit-btn disabled"
            : "wide-btn-edit edit-btn";
          const editButtonDisabled = isEditDisabled ? "disabled" : "";
          const editButtonText = isEditDisabled ? "Edit (Locked)" : "Edit";

          // Status badge coloring
          let statusBadgeColor = "#e2e8f0";
          let statusTextColor = "#4a5568";
          const statusLower = (invoice.status || "unpaid").toLowerCase();
          if (statusLower === "paid") {
            statusBadgeColor = "#c6f6d5";
            statusTextColor = "#22543d";
          } else if (statusLower === "partially paid" || statusLower === "partial") {
            statusBadgeColor = "#feebc8";
            statusTextColor = "#744210";
          } else if (statusLower === "unpaid") {
            statusBadgeColor = "#fed7d7";
            statusTextColor = "#742a2a";
          }

          const statusBadge = `
            <span class="status-badge" style="background: ${statusBadgeColor}; color: ${statusTextColor}; padding: 4px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; display: inline-block;">
              ${invoice.status || "N/A"}
            </span>
          `;

          return `
          <div class="invoice-card" id="invoice-card-${invoice.id}" style="background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03); margin-bottom: 20px; transition: transform 0.2s, box-shadow 0.2s;">
            <div class="card-header" style="display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 1px solid #edf2f7; padding-bottom: 12px; margin-bottom: 16px;">
              <div>
                <h2 style="margin: 0; font-size: 1.25rem; font-weight: 700; color: #8b1538; text-transform: capitalize;">${invoice.type_of}</h2>
                <span style="font-size: 0.8rem; color: #718096;">ID: #${invoice.id} &bull; Created: ${invoice.created_at}</span>
              </div>
              ${statusBadge}
            </div>
            
            <div class="card-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 16px; font-size: 0.875rem;">
              <div class="info-block">
                <span style="display: block; font-size: 0.75rem; color: #a0aec0; text-transform: uppercase; font-weight: 600;">Customer</span>
                <strong>${invoice.customer_name}</strong>${invoice.customer_code ? ` <span class="customer-code">${invoice.customer_code}</span>` : ""}
                <div style="font-size: 0.8rem; color: #4a5568; margin-top: 2px;">${invoice.customer_phone}</div>
                <div style="font-size: 0.8rem; color: #718096; font-style: italic;">Reg: ${invoice.customer_reg_no}</div>
              </div>
              
              <div class="info-block" style="background: #f7fafc; padding: 8px 12px; border-radius: 8px;">
                <span style="display: block; font-size: 0.75rem; color: #718096; text-transform: uppercase; font-weight: 600;">Summary</span>
                <div>Net Total: <strong>${invoiceTotal.toFixed(2)}</strong></div>
                ${invoice.discount > 0 ? `<div>Discount: <span style="color: #e53e3e;">-${invoice.discount.toFixed(2)}</span></div>` : ""}
                ${invoice.advance > 0 ? `<div>Advance: <span style="color: #4a5568;">-${invoice.advance.toFixed(2)}</span></div>` : ""}
                ${invoice.include_tax && invoice.tax_amount > 0 ? `<div>Tax (GST): <span style="color: #718096;">+${invoice.tax_amount.toFixed(2)}</span></div>` : ""}
              </div>
              
              <div class="info-block" style="background: #fffaf0; padding: 8px 12px; border-radius: 8px; border: 1px solid #feebc8;">
                <span style="display: block; font-size: 0.75rem; color: #b7791f; text-transform: uppercase; font-weight: 600;">Outstanding</span>
                <div style="font-size: 1.1rem; font-weight: 700; color: #dd6b20;">${invoice.balance.toFixed(2)} PKR</div>
                <div style="font-size: 0.75rem; color: #718096; margin-top: 2px;">Paid: ${(invoice.paid_amount || 0).toFixed(2)} PKR</div>
              </div>
            </div>
            
            ${proofLinksHtml}
            
            <div class="invoice-actions" style="display: flex; justify-content: flex-end; gap: 8px; border-top: 1px solid #edf2f7; padding-top: 12px; margin-top: 12px; flex-wrap: wrap;">
              <button class="wide-btn-submit view-btn">View</button>
              <button class="${editButtonClass}" ${editButtonDisabled}>${editButtonText}</button>
              <button class="wide-btn-update update-balance-btn">Update Balance</button>
              <button class="wide-btn-delete delete-btn">Delete</button>
            </div>
          </div>
        `;
        })
        .join("");
      html += "</div></div>";
      resultsDiv.innerHTML = html;
      // Attach event listeners
      invoices.forEach((invoice) => {
        // View/Edit/Delete event listeners
        const viewBtn = document.querySelector(
          `#invoice-card-${invoice.id} .view-btn`
        );
        if (viewBtn) {
          viewBtn.addEventListener("click", async () => {
            try {
              const fullInvoiceData = await APIHelper.get(
                `/api/invoice/${invoice.id}`
              );
              if (fullInvoiceData) {
                sessionStorage.setItem(
                  "invoiceData",
                  JSON.stringify(fullInvoiceData)
                );
                sessionStorage.setItem("invoiceId", invoice.id);
                sessionStorage.setItem("documentType", fullInvoiceData.type_of);
                window.location.href = `invoice-template.html?from=invoice-management&id=${invoice.id}`;
              } else {
                alert("Document not found");
              }
            } catch (err) {
              alert("Failed to load document data");
            }
          });
        }
        const editBtn = document.querySelector(
          `#invoice-card-${invoice.id} .edit-btn`
        );
        if (editBtn) {
          editBtn.addEventListener("click", () => {
            // Check if edit is disabled before proceeding
            if (shouldDisableEditButton(invoice)) {
              alert(
                "You cannot edit invoices older than 1 day. Please contact an administrator."
              );
              return;
            }
            window.location.href = `invoice.html?id=${invoice.id}`;
          });
        }
        const updateBalanceBtn = document.querySelector(
          `#invoice-card-${invoice.id} .update-balance-btn`
        );
        if (updateBalanceBtn) {
          updateBalanceBtn.addEventListener("click", async () => {
            // Calculate total with tax for this specific invoice
            const invoiceTotal = invoice.net_total !== undefined ? invoice.net_total : (invoice.total || 0);
            let totalWithTax = invoiceTotal;
            if (invoice.include_tax && invoice.tax_amount) {
              totalWithTax += invoice.tax_amount;
            }
            if (invoice.discount) {
              totalWithTax -= invoice.discount;
            }
            if (invoice.advance) {
              totalWithTax -= invoice.advance;
            }

            const currentBalance = totalWithTax - (invoice.paid_amount || 0);
            const currentPaidAmount = invoice.paid_amount || 0;
            
            openUpdateBalanceModal(invoice.id, totalWithTax, currentPaidAmount, currentBalance);
          });
        }
        const deleteBtn = document.querySelector(
          `#invoice-card-${invoice.id} .delete-btn`
        );
        if (deleteBtn) {
          deleteBtn.addEventListener("click", async () => {
            if (!confirm("Are you sure you want to delete this document?"))
              return;
            try {
              const result = await APIHelper.request(
                `/api/invoice/${invoice.id}/delete`,
                {
                  method: "DELETE",
                }
              );
              if (result) {
                document.getElementById(`invoice-card-${invoice.id}`).remove();
              } else {
                alert("Failed to delete document.");
              }
            } catch (err) {
              alert("Error occurred while deleting document.");
            }
          });
        }
      });
    } catch (err) {
      console.error("Error fetching invoices:", err);
      APIHelper.renderError(resultsDiv, err, () => loadInvoices(status));
    }
  }

  // Search functionality
  function performSearch() {
    const keywordQuery = keywordSearchInput.value.trim();
    const idQuery = idSearchInput.value.trim();

    currentKeywordQuery = keywordQuery;
    currentIdQuery = idQuery;

    // Show clear button if either field has content
    if (keywordQuery || idQuery) {
      clearSearchBtn.style.display = "block";
    } else {
      clearSearchBtn.style.display = "none";
    }

    loadInvoices(currentStatus, keywordQuery, idQuery, currentDateFrom, currentDateTo);
  }

  function clearSearch() {
    keywordSearchInput.value = "";
    idSearchInput.value = "";
    currentKeywordQuery = "";
    currentIdQuery = "";
    clearSearchBtn.style.display = "none";
    loadInvoices(currentStatus, "", "", currentDateFrom, currentDateTo);
  }

  function setActiveButton(activeBtn) {
    [btnAll, btnPaid, btnPartial, btnUnpaid].forEach((btn) => {
      btn.classList.remove("active");
    });
    activeBtn.classList.add("active");
  }

  // Search event listeners
  searchBtn.addEventListener("click", performSearch);

  keywordSearchInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
      performSearch();
    }
  });

  idSearchInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
      performSearch();
    }
  });

  clearSearchBtn.addEventListener("click", clearSearch);

  // Button event listeners
  btnAll.addEventListener("click", () => {
    currentStatus = "all";
    setActiveButton(btnAll);
    loadInvoices(currentStatus, currentKeywordQuery, currentIdQuery, currentDateFrom, currentDateTo);
  });

  btnPaid.addEventListener("click", () => {
    currentStatus = "paid";
    setActiveButton(btnPaid);
    loadInvoices(currentStatus, currentKeywordQuery, currentIdQuery, currentDateFrom, currentDateTo);
  });

  btnPartial.addEventListener("click", () => {
    currentStatus = "partially paid";
    setActiveButton(btnPartial);
    loadInvoices(currentStatus, currentKeywordQuery, currentIdQuery, currentDateFrom, currentDateTo);
  });

  btnUnpaid.addEventListener("click", () => {
    currentStatus = "unpaid";
    setActiveButton(btnUnpaid);
    loadInvoices(currentStatus, currentKeywordQuery, currentIdQuery, currentDateFrom, currentDateTo);
  });

  // Date filter event listeners
  filterToday.addEventListener("click", () => {
    const range = getTodayRange();
    currentDateFrom = range.from;
    currentDateTo = range.to;
    setActiveDateButton(filterToday);
    updateDateFilterVisibility();
    customRangeContainer.style.display = "none";
    loadInvoices(currentStatus, currentKeywordQuery, currentIdQuery, currentDateFrom, currentDateTo);
  });

  filterThisWeek.addEventListener("click", () => {
    const range = getThisWeekRange();
    currentDateFrom = range.from;
    currentDateTo = range.to;
    setActiveDateButton(filterThisWeek);
    updateDateFilterVisibility();
    customRangeContainer.style.display = "none";
    loadInvoices(currentStatus, currentKeywordQuery, currentIdQuery, currentDateFrom, currentDateTo);
  });

  filterThisMonth.addEventListener("click", () => {
    const range = getThisMonthRange();
    currentDateFrom = range.from;
    currentDateTo = range.to;
    setActiveDateButton(filterThisMonth);
    updateDateFilterVisibility();
    customRangeContainer.style.display = "none";
    loadInvoices(currentStatus, currentKeywordQuery, currentIdQuery, currentDateFrom, currentDateTo);
  });

  filterThisYear.addEventListener("click", () => {
    const range = getThisYearRange();
    currentDateFrom = range.from;
    currentDateTo = range.to;
    setActiveDateButton(filterThisYear);
    updateDateFilterVisibility();
    customRangeContainer.style.display = "none";
    loadInvoices(currentStatus, currentKeywordQuery, currentIdQuery, currentDateFrom, currentDateTo);
  });

  filterCustom.addEventListener("click", () => {
    setActiveDateButton(filterCustom);
    customRangeContainer.style.display = customRangeContainer.style.display === "none" ? "block" : "none";
    // Pre-fill with current date range if set
    if (currentDateFrom) {
      dateFromInput.value = currentDateFrom;
    }
    if (currentDateTo) {
      dateToInput.value = currentDateTo;
    }
  });

  applyCustomRange.addEventListener("click", () => {
    const dateFrom = dateFromInput.value;
    const dateTo = dateToInput.value;
    
    if (!dateFrom && !dateTo) {
      alert("Please select at least one date.");
      return;
    }
    
    currentDateFrom = dateFrom;
    currentDateTo = dateTo;
    updateDateFilterVisibility();
    loadInvoices(currentStatus, currentKeywordQuery, currentIdQuery, currentDateFrom, currentDateTo);
  });

  clearDateFilter.addEventListener("click", () => {
    currentDateFrom = "";
    currentDateTo = "";
    dateFromInput.value = "";
    dateToInput.value = "";
    setActiveDateButton(null);
    updateDateFilterVisibility();
    customRangeContainer.style.display = "none";
    loadInvoices(currentStatus, currentKeywordQuery, currentIdQuery, "", "");
  });

  // Update Balance Modal Event Listeners
  const closeBtn = document.getElementById("close-balance-modal");
  if (closeBtn) closeBtn.addEventListener("click", closeUpdateBalanceModal);
  
  const cancelBtn = document.getElementById("btn-cancel-balance");
  if (cancelBtn) cancelBtn.addEventListener("click", closeUpdateBalanceModal);
  
  const balanceForm = document.getElementById("balance-form");
  if (balanceForm) balanceForm.addEventListener("submit", handleBalanceFormSubmit);
  
  window.addEventListener("click", (e) => {
    const modal = document.getElementById("update-balance-modal");
    if (e.target === modal) {
      closeUpdateBalanceModal();
    }
  });

  // The balance modal's helpers are defined outside this closure, so give them
  // one way back in. Reuses the active tab and filters instead of resetting the
  // view to "all", which a bare loadInvoices() would have done.
  window.refreshInvoiceList = () =>
    loadInvoices(
      currentStatus,
      currentKeywordQuery,
      currentIdQuery,
      currentDateFrom,
      currentDateTo
    );

  // Initial load
  loadInvoices("all");
});

// Update Balance Modal Helper Functions
function openUpdateBalanceModal(invoiceId, total, paid, remaining) {
  document.getElementById("balance-invoice-id").value = invoiceId;
  document.getElementById("balance-info-id").textContent = `#${invoiceId}`;
  document.getElementById("balance-info-total").textContent = `${total.toFixed(2)} PKR`;
  document.getElementById("balance-info-paid").textContent = `${paid.toFixed(2)} PKR`;
  document.getElementById("balance-info-remaining").textContent = `${remaining.toFixed(2)} PKR`;
  const amountInput = document.getElementById("balance-paid-amount");
  amountInput.value = "";
  // The server rejects overpayment; mirror that here so the limit is visible
  // before the user submits rather than after.
  amountInput.max = remaining.toFixed(2);
  amountInput.dataset.remaining = String(remaining);
  document.getElementById("balance-proof-file").value = "";
  document.getElementById("update-balance-modal").style.display = "block";
}

function closeUpdateBalanceModal() {
  document.getElementById("update-balance-modal").style.display = "none";
}

async function handleBalanceFormSubmit(e) {
  e.preventDefault();
  
  const invoiceId = document.getElementById("balance-invoice-id").value;
  const paidAmount = document.getElementById("balance-paid-amount").value;
  const fileInput = document.getElementById("balance-proof-file");
  
  const amount = parseFloat(paidAmount);
  if (!paidAmount || isNaN(amount) || amount <= 0) {
    alert("Enter a payment amount greater than zero.");
    return;
  }

  const remaining = parseFloat(
    document.getElementById("balance-paid-amount").dataset.remaining
  );
  if (!isNaN(remaining) && Math.round(amount * 100) > Math.round(remaining * 100)) {
    alert(
      `Payment of ${amount.toFixed(2)} PKR exceeds the ${remaining.toFixed(
        2
      )} PKR still owed on this invoice.`
    );
    return;
  }
  
  const formData = new FormData();
  formData.append("paid_amount", paidAmount);
  if (fileInput.files.length > 0) {
    formData.append("proof", fileInput.files[0]);
  }
  
  try {
    const result = await APIHelper.request(`/api/invoice/${invoiceId}/update-balance`, {
      method: "PUT",
      body: formData
    });
    
    if (result) {
      alert(result.message || "Balance updated successfully!");
      closeUpdateBalanceModal();
      window.refreshInvoiceList?.();
    } else {
      alert("Failed to update balance.");
    }
  } catch (error) {
    console.error("Error updating balance:", error);
    alert(error.message || "Error occurred while updating balance.");
  }
}
