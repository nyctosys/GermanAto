document.addEventListener("DOMContentLoaded", () => {
  // Set up smart back button logic
  const backBtn = document.getElementById("back-btn");
  const urlParams = new URLSearchParams(window.location.search);
  const fromPage =
    urlParams.get("from") ||
    localStorage.getItem("lastPage") ||
    "invoiceSystem";

  // Set back button destination based on where user came from
  if (fromPage === "home") {
    backBtn.href = "home.html";
  } else if (fromPage === "invoiceSystem") {
    backBtn.href = "invoiceSystem.html";
  } else {
    backBtn.href = "invoiceSystem.html"; // Default fallback
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

    // Admins can always edit
    if (user.role === "admin") {
      return false;
    }

    // Accountants can always edit quotes, but invoices older than 1 day are restricted
    if (user.role === "accountant") {
      // If it's a quote, allow editing
      if (invoice.type_of.toLowerCase() === "quote") {
        return false;
      }
      // If it's an invoice, check if it's older than 1 day
      return isInvoiceOlderThanOneDay(invoice.created_at);
    }

    // Other roles cannot edit
    return true;
  }

  async function loadInvoices(status, keywordQuery = "", idQuery = "", dateFrom = "", dateTo = "") {
    resultsDiv.innerHTML = "<p>Loading...</p>";
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
          const totalWithTax =
            invoice.include_tax && invoice.tax_amount > 0
              ? invoice.total + invoice.tax_amount
              : invoice.total;
          const taxDisplay =
            invoice.include_tax && invoice.tax_amount > 0
              ? `<p><strong>GST/PST:</strong> ${invoice.tax_amount.toFixed(
                  2
                )} PKR</p>`
              : "";
          const statusDisplay = `<p><strong>Status:</strong> <span class="invoice-status">${
            invoice.status || "N/A"
          }</span></p>`;
          const statusDropdown = `
            <select class="invoice-status-dropdown" data-id="${invoice.id}">
              <option value="unpaid" ${
                invoice.status === "unpaid" ? "selected" : ""
              }>Unpaid</option>
              <option value="partially paid" ${
                invoice.status === "partially paid" ? "selected" : ""
              }>Partially Paid</option>
              <option value="paid" ${
                invoice.status === "paid" ? "selected" : ""
              }>Paid</option>
            </select>
          `;

          // Check if edit button should be disabled
          const isEditDisabled = shouldDisableEditButton(invoice);
          const editButtonClass = isEditDisabled
            ? "wide-btn-edit edit-btn disabled"
            : "wide-btn-edit edit-btn";
          const editButtonDisabled = isEditDisabled ? "disabled" : "";
          const editButtonText = isEditDisabled ? "Edit (Locked)" : "Edit";

          return `
          <div class="invoice-card invoice-card" id="invoice-card-${
            invoice.id
          }">
            <h2>${invoice.type_of}</h2>
            <h3>ID: ${invoice.id}</h3>
            <p><strong>Name:</strong> ${invoice.customer_name}</p>
            <p><strong>Phone:</strong> ${invoice.customer_phone}</p>
            <p><strong>Reg No:</strong> ${invoice.customer_reg_no}</p>
            <p><strong>Net Total:</strong> ${invoice.total.toFixed(2)} PKR</p>
            ${taxDisplay}
            <p><strong>Advance:</strong> ${invoice.advance.toFixed(2)} PKR</p>
            <p><strong>Paid Amount:</strong> ${(
              invoice.paid_amount || 0
            ).toFixed(2)} PKR</p>
            <p><strong>Balance:</strong> ${(
              totalWithTax -
              (invoice.paid_amount || 0) -
              (invoice.advance || 0)
            ).toFixed(2)} PKR</p>
            <p><strong>Created:</strong> ${invoice.created_at}</p>
            ${statusDisplay}
            <div class="invoice-actions">
              <button class="wide-btn-submit view-btn">View</button>
              <button class="${editButtonClass}" ${editButtonDisabled}>${editButtonText}</button>
              <button class="wide-btn-update update-balance-btn">Update Balance</button>
              <button class="wide-btn-delete delete-btn">Delete</button>
              ${statusDropdown}
            </div>
          </div>
        `;
        })
        .join("");
      html += "</div></div>";
      resultsDiv.innerHTML = html;
      // Attach event listeners
      invoices.forEach((invoice) => {
        // Status dropdown
        const statusDropdown = document.querySelector(
          `#invoice-card-${invoice.id} .invoice-status-dropdown`
        );
        if (statusDropdown) {
          statusDropdown.addEventListener("change", async (e) => {
            const newStatus = e.target.value;
            try {
              const result = await APIHelper.request(
                `/api/invoice/${invoice.id}/status`,
                {
                  method: "PUT",
                  body: JSON.stringify({ status: newStatus }),
                }
              );
              if (result) {
                const statusSpan = document.querySelector(
                  `#invoice-card-${invoice.id} .invoice-status`
                );
                if (statusSpan) statusSpan.textContent = newStatus;
              } else {
                alert("Failed to update invoice status.");
              }
            } catch (err) {
              alert("Error updating invoice status.");
            }
          });
        }
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
                window.location.href = "invoice-template.html";
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
            let totalWithTax = invoice.total;
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
            const paidAmount = prompt(
              `Enter additional amount to pay for invoice ${
                invoice.id
              }:\nCurrent paid: ${currentPaidAmount.toFixed(
                2
              )} PKR\nCurrent balance: ${currentBalance.toFixed(
                2
              )} PKR\n\nEnter amount to add:`
            );
            if (paidAmount === null) return; // User cancelled

            const paid = parseFloat(paidAmount);
            if (isNaN(paid) || paid < 0) {
              alert("Please enter a valid positive number.");
              return;
            }

            try {
              const result = await APIHelper.request(
                `/api/invoice/${invoice.id}/update-balance`,
                {
                  method: "PUT",
                  body: JSON.stringify({ paid_amount: paid }),
                }
              );

              if (result) {
                alert(result.message || "Balance updated successfully!");
                loadInvoices(); // Reload invoices to show updated data
              } else {
                alert("Failed to update balance.");
              }
            } catch (err) {
              alert("Error occurred while updating balance.");
            }
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
      resultsDiv.innerHTML = `<p>Error fetching invoices.</p>`;
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

  // Initial load
  loadInvoices("all");
});
