document.addEventListener("DOMContentLoaded", () => {
  // Set up smart back button logic
  const backBtn = document.getElementById("back-btn");
  const urlParams = new URLSearchParams(window.location.search);
  const fromPage =
    urlParams.get("from") ||
    localStorage.getItem("lastPage") ||
    "invoiceSystem";

  // Set back button destination based on where user came from
  if (fromPage === "admin") {
    backBtn.href = "admin.html";
  } else if (fromPage === "home") {
    backBtn.href = "home.html";
  } else if (fromPage === "invoiceSystem") {
    backBtn.href = "invoiceSystem.html";
  } else {
    backBtn.href = "invoiceSystem.html"; // Default fallback
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

  let currentStatus = "all";
  let currentKeywordQuery = "";
  let currentIdQuery = "";

  async function loadQuotes(status, keywordQuery = "", idQuery = "") {
    resultsDiv.innerHTML = "<p>Loading...</p>";
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

      const res = await fetch(url);
      const data = await res.json();
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
      html += `<h3>📋 ${
        status.charAt(0).toUpperCase() + status.slice(1)
      } Quotes (${quotes.length})</h3>`;
      html += quotes
        .map((quote) => {
          const totalWithTax =
            quote.include_tax && quote.tax_amount > 0
              ? quote.total + quote.tax_amount
              : quote.total;
          const taxDisplay =
            quote.include_tax && quote.tax_amount > 0
              ? `<p><strong>GST/PST:</strong> ${quote.tax_amount.toFixed(
                  2
                )} PKR</p>`
              : "";
          const approveBtn =
            status === "pending"
              ? `<button class="wide-btn-approve approve-btn">Approve</button>`
              : "";
          return `
          <div class="invoice-card quote-card" id="invoice-card-${quote.id}">
            <h2>${quote.type_of}</h2>
            <h3>ID: ${quote.id}</h3>
            <p><strong>Name:</strong> ${quote.customer_name}</p>
            <p><strong>Phone:</strong> ${quote.customer_phone}</p>
            <p><strong>Reg No:</strong> ${quote.customer_reg_no}</p>
            <p><strong>Net Total:</strong> ${quote.total.toFixed(2)} PKR</p>
            ${taxDisplay}
            <p><strong>Advance:</strong> ${quote.advance.toFixed(2)} PKR</p>
            <p><strong>Total Quotation:</strong> ${totalWithTax.toFixed(
              2
            )} PKR</p>
            <p><strong>Created:</strong> ${quote.created_at}</p>
            <p><strong>Status:</strong> <span class="quote-status">${
              quote.status || "pending"
            }</span></p>
            <div class="invoice-actions">
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
              const res = await fetch(`/api/invoice/${quote.id}/status`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ status: "approved" }),
              });
              if (res.ok) {
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
              const res = await fetch(`/api/invoice/${quote.id}`);
              if (res.ok) {
                const fullInvoiceData = await res.json();
                sessionStorage.setItem(
                  "invoiceData",
                  JSON.stringify(fullInvoiceData)
                );
                sessionStorage.setItem("invoiceId", quote.id);
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
          `#invoice-card-${quote.id} .edit-btn`
        );
        if (editBtn) {
          editBtn.addEventListener("click", () => {
            window.location.href = `invoice.html?id=${quote.id}`;
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
              const res = await fetch(`/api/invoice/${quote.id}/delete`, {
                method: "DELETE",
              });
              if (res.ok) {
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
      resultsDiv.innerHTML = `<p>Error fetching ${status} quotes.</p>`;
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

    loadQuotes(currentStatus, keywordQuery, idQuery);
  }

  function clearSearch() {
    keywordSearchInput.value = "";
    idSearchInput.value = "";
    currentKeywordQuery = "";
    currentIdQuery = "";
    clearSearchBtn.style.display = "none";
    loadQuotes(currentStatus, "", "");
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
    loadQuotes(currentStatus, currentKeywordQuery, currentIdQuery);
  });

  btnPending.addEventListener("click", () => {
    currentStatus = "pending";
    setActiveButton(btnPending);
    loadQuotes(currentStatus, currentKeywordQuery, currentIdQuery);
  });

  btnApproved.addEventListener("click", () => {
    currentStatus = "approved";
    setActiveButton(btnApproved);
    loadQuotes(currentStatus, currentKeywordQuery, currentIdQuery);
  });

  // Initial load
  loadQuotes("all");
});
