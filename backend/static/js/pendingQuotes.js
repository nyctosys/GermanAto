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
    if (fromPage === "admin") {
      backBtn.href = "admin.html";
    } else if (fromPage === "home") {
      backBtn.href = "home.html";
    } else if (fromPage === "invoiceSystem") {
      backBtn.href = "invoiceSystem.html";
    } else {
      backBtn.href = "invoiceSystem.html"; // Default fallback
    }
  }

  // Track current page for back button logic
  localStorage.setItem("lastPage", "pending-quotes");

  const resultsDiv = document.getElementById("pending-quotes-results");
  const keywordSearchInput = document.getElementById("keyword-search-input");
  const idSearchInput = document.getElementById("id-search-input");
  const searchBtn = document.getElementById("search-btn");
  const clearSearchBtn = document.getElementById("clear-search-btn");
  const btnAll = document.getElementById("show-all");
  const btnPending = document.getElementById("show-pending");
  const btnApproved = document.getElementById("show-approved");

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

  async function loadQuotes(status, keywordQuery = "", idQuery = "", dateFrom = "", dateTo = "") {
    APIHelper.renderLoading(resultsDiv, "Loading quotes...");
    try {
      let url = `/api/search?type=quote`;

      // Add status filter if not "all"
      if (status && status !== "all") {
        url += `&status=${encodeURIComponent(status)}`;
      }

      // Add keyword search if provided
      if (keywordQuery) {
        url += `&q=${encodeURIComponent(keywordQuery)}`;
      }

      // Add ID search if provided
      if (idQuery) {
        url += `&id=${encodeURIComponent(idQuery)}`;
      }

      // Add date range filter if provided
      if (dateFrom) {
        url += `&date_from=${encodeURIComponent(dateFrom)}`;
      }
      if (dateTo) {
        url += `&date_to=${encodeURIComponent(dateTo)}`;
      }

      const data = await APIHelper.get(url);
      const quotes = data.quotes || [];

      if (quotes.length === 0) {
        const statusText = status && status !== "all" ? status : "";
        let searchText = "";
        if (keywordQuery && idQuery) {
          searchText = ` for keyword "${keywordQuery}" and ID "${idQuery}"`;
        } else if (keywordQuery) {
          searchText = ` for keyword "${keywordQuery}"`;
        } else if (idQuery) {
          searchText = ` for ID "${idQuery}"`;
        }
        resultsDiv.innerHTML = `<p>No ${statusText} quotes found${searchText}.</p>`;
        return;
      }
      let html = '<div class="results-container">';
      html += '<div class="results-column quotes-column">';
      html += `<h3>${
        status.charAt(0).toUpperCase() + status.slice(1)
      } Quotes (${quotes.length})</h3>`;
      html += quotes
        .map((quote) => {
          const quoteTotal = quote.net_total !== undefined ? quote.net_total : (quote.total || 0);
          const totalWithTax =
            quote.include_tax && quote.tax_amount > 0
              ? quoteTotal + quote.tax_amount
              : quoteTotal;
          const taxDisplay =
            quote.include_tax && quote.tax_amount > 0
              ? `<p><strong>GST/PST:</strong> ${quote.tax_amount.toFixed(
                  2
                )} PKR</p>`
              : "";
          // Status badge coloring
          let statusBadgeColor = "#feebc8";
          let statusTextColor = "#744210";
          const quoteStatus = quote.status || "pending";
          if (quoteStatus === "approved") {
            statusBadgeColor = "#c6f6d5";
            statusTextColor = "#22543d";
          } else if (quoteStatus === "rejected") {
            statusBadgeColor = "#fed7d7";
            statusTextColor = "#742a2a";
          }

          const statusBadge = `
            <span class="status-badge" style="background: ${statusBadgeColor}; color: ${statusTextColor}; padding: 4px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; display: inline-block;">
              ${quoteStatus}
            </span>
          `;

          const approveBtn =
            status === "pending"
              ? `<button class="wide-btn-approve approve-btn">Approve</button>`
              : "";

          return `
          <div class="invoice-card" id="invoice-card-${quote.id}" style="background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03); margin-bottom: 20px; transition: transform 0.2s, box-shadow 0.2s;">
            <div class="card-header" style="display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 1px solid #edf2f7; padding-bottom: 12px; margin-bottom: 16px;">
              <div>
                <h2 style="margin: 0; font-size: 1.25rem; font-weight: 700; color: #8b1538; text-transform: capitalize;">${quote.type_of}</h2>
                <span style="font-size: 0.8rem; color: #718096;">ID: #${quote.id} &bull; Created: ${quote.created_at}</span>
              </div>
              ${statusBadge}
            </div>
            
            <div class="card-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 16px; font-size: 0.875rem;">
              <div class="info-block">
                <span style="display: block; font-size: 0.75rem; color: #a0aec0; text-transform: uppercase; font-weight: 600;">Customer</span>
                <strong>${quote.customer_name}</strong>${quote.customer_code ? ` <span class="customer-code">${quote.customer_code}</span>` : ""}
                <div style="font-size: 0.8rem; color: #4a5568; margin-top: 2px;">${quote.customer_phone}</div>
                <div style="font-size: 0.8rem; color: #718096; font-style: italic;">Reg: ${quote.customer_reg_no}</div>
              </div>
              
              <div class="info-block" style="background: #f7fafc; padding: 8px 12px; border-radius: 8px;">
                <span style="display: block; font-size: 0.75rem; color: #718096; text-transform: uppercase; font-weight: 600;">Summary</span>
                <div>Net Total: <strong>${quoteTotal.toFixed(2)}</strong></div>
                ${quote.discount > 0 ? `<div>Discount: <span style="color: #e53e3e;">-${quote.discount.toFixed(2)}</span></div>` : ""}
                ${quote.advance > 0 ? `<div>Advance: <span style="color: #4a5568;">-${quote.advance.toFixed(2)}</span></div>` : ""}
                ${quote.include_tax && quote.tax_amount > 0 ? `<div>Tax (GST): <span style="color: #718096;">+${quote.tax_amount.toFixed(2)}</span></div>` : ""}
              </div>
              
              <div class="info-block" style="background: #fffaf0; padding: 8px 12px; border-radius: 8px; border: 1px solid #feebc8;">
                <span style="display: block; font-size: 0.75rem; color: #b7791f; text-transform: uppercase; font-weight: 600;">Total Quotation</span>
                <div style="font-size: 1.1rem; font-weight: 700; color: #dd6b20;">${(totalWithTax - quote.discount).toFixed(2)} PKR</div>
              </div>
            </div>
            
            <div class="invoice-actions" style="display: flex; justify-content: flex-end; gap: 8px; border-top: 1px solid #edf2f7; padding-top: 12px; margin-top: 12px; flex-wrap: wrap;">
              <button class="wide-btn-submit view-btn">View</button>
              <button class="wide-btn-edit edit-btn">Edit</button>
              <button class="wide-btn-delete delete-btn">Delete</button>
              ${approveBtn}
            </div>
          </div>
        `;
        })
        .join("");
      html += "</div></div>";
      resultsDiv.innerHTML = html;
      // Attach event listeners
      quotes.forEach((quote) => {
        const approveBtn = document.querySelector(
          `#invoice-card-${quote.id} .approve-btn`
        );
        if (approveBtn) {
          approveBtn.addEventListener("click", async () => {
            if (!confirm("Approve this quote and create repair order?")) return;
            try {
              const result = await APIHelper.request(
                `/api/invoice/${quote.id}/status`,
                {
                  method: "PUT",
                  body: JSON.stringify({ status: "approved" }),
                }
              );
              if (result) {
                // Redirect to repair order form with quote data
                window.location.href = `repair-order.html?quoteId=${quote.id}&from=pending-quotes`;
              } else {
                alert("Failed to approve quote.");
              }
            } catch (err) {
              alert("Error approving quote.");
            }
          });
        }
        // View/Edit/Delete event listeners can be added as needed
        const viewBtn = document.querySelector(
          `#invoice-card-${quote.id} .view-btn`
        );
        if (viewBtn) {
          viewBtn.addEventListener("click", async () => {
            try {
              const fullInvoiceData = await APIHelper.get(
                `/api/invoice/${quote.id}`
              );
              if (fullInvoiceData) {
                sessionStorage.setItem(
                  "invoiceData",
                  JSON.stringify(fullInvoiceData)
                );
                sessionStorage.setItem("invoiceId", quote.id);
                sessionStorage.setItem("documentType", fullInvoiceData.type_of);
                window.location.href = `invoice-template.html?from=pending-quotes&id=${quote.id}`;
              } else {
                alert("Document not found");
              }
            } catch (err) {
              alert("Failed to load document data");
            }
          });
        }
        const editBtn = document.querySelector(
          `#invoice-card-${quote.id} .edit-btn`
        );
        if (editBtn) {
          editBtn.addEventListener("click", () => {
            // Quotes are edited on the quote form, which has no payment fields.
            window.location.href = `quote.html?id=${quote.id}`;
          });
        }
        const deleteBtn = document.querySelector(
          `#invoice-card-${quote.id} .delete-btn`
        );
        if (deleteBtn) {
          deleteBtn.addEventListener("click", async () => {
            if (!confirm("Are you sure you want to delete this document?"))
              return;
            try {
              const result = await APIHelper.request(
                `/api/invoice/${quote.id}/delete`,
                {
                  method: "DELETE",
                }
              );
              if (result) {
                document.getElementById(`invoice-card-${quote.id}`).remove();
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
      console.error("Error fetching quotes:", err);
      APIHelper.renderError(resultsDiv, err, () => loadQuotes(status));
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

    loadQuotes(currentStatus, keywordQuery, idQuery, currentDateFrom, currentDateTo);
  }

  function clearSearch() {
    keywordSearchInput.value = "";
    idSearchInput.value = "";
    currentKeywordQuery = "";
    currentIdQuery = "";
    clearSearchBtn.style.display = "none";
    loadQuotes(currentStatus, "", "", currentDateFrom, currentDateTo);
  }

  function setActiveButton(activeBtn) {
    [btnAll, btnPending, btnApproved].forEach((btn) => {
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
    loadQuotes(currentStatus, currentKeywordQuery, currentIdQuery, currentDateFrom, currentDateTo);
  });

  btnPending.addEventListener("click", () => {
    currentStatus = "pending";
    setActiveButton(btnPending);
    loadQuotes(currentStatus, currentKeywordQuery, currentIdQuery, currentDateFrom, currentDateTo);
  });

  btnApproved.addEventListener("click", () => {
    currentStatus = "approved";
    setActiveButton(btnApproved);
    loadQuotes(currentStatus, currentKeywordQuery, currentIdQuery, currentDateFrom, currentDateTo);
  });

  // Date filter event listeners
  filterToday.addEventListener("click", () => {
    const range = getTodayRange();
    currentDateFrom = range.from;
    currentDateTo = range.to;
    setActiveDateButton(filterToday);
    updateDateFilterVisibility();
    customRangeContainer.style.display = "none";
    loadQuotes(currentStatus, currentKeywordQuery, currentIdQuery, currentDateFrom, currentDateTo);
  });

  filterThisWeek.addEventListener("click", () => {
    const range = getThisWeekRange();
    currentDateFrom = range.from;
    currentDateTo = range.to;
    setActiveDateButton(filterThisWeek);
    updateDateFilterVisibility();
    customRangeContainer.style.display = "none";
    loadQuotes(currentStatus, currentKeywordQuery, currentIdQuery, currentDateFrom, currentDateTo);
  });

  filterThisMonth.addEventListener("click", () => {
    const range = getThisMonthRange();
    currentDateFrom = range.from;
    currentDateTo = range.to;
    setActiveDateButton(filterThisMonth);
    updateDateFilterVisibility();
    customRangeContainer.style.display = "none";
    loadQuotes(currentStatus, currentKeywordQuery, currentIdQuery, currentDateFrom, currentDateTo);
  });

  filterThisYear.addEventListener("click", () => {
    const range = getThisYearRange();
    currentDateFrom = range.from;
    currentDateTo = range.to;
    setActiveDateButton(filterThisYear);
    updateDateFilterVisibility();
    customRangeContainer.style.display = "none";
    loadQuotes(currentStatus, currentKeywordQuery, currentIdQuery, currentDateFrom, currentDateTo);
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
    loadQuotes(currentStatus, currentKeywordQuery, currentIdQuery, currentDateFrom, currentDateTo);
  });

  clearDateFilter.addEventListener("click", () => {
    currentDateFrom = "";
    currentDateTo = "";
    dateFromInput.value = "";
    dateToInput.value = "";
    setActiveDateButton(null);
    updateDateFilterVisibility();
    customRangeContainer.style.display = "none";
    loadQuotes(currentStatus, currentKeywordQuery, currentIdQuery, "", "");
  });

  // Initial load
  loadQuotes("all");
});
