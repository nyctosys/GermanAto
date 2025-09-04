function openInvoiceTemplate(
  invoiceWindow,
  documentId,
  invoiceData,
  documentType = "invoice"
) {
  if (!invoiceWindow) {
    alert("Popup blocked! Allow popups and try again.");
    return;
  }

  fetch("invoice-template.html")
    .then((response) => response.text())
    .then((html) => {
      invoiceWindow.document.open();
      invoiceWindow.document.write(html);
      invoiceWindow.document.close();

      invoiceWindow.onload = function () {
        // Determine document type from invoiceData.type_of if available, otherwise use documentType parameter
        let actualDocumentType = documentType;
        if (invoiceData.type_of) {
          actualDocumentType = invoiceData.type_of.toLowerCase();
        }

        // Update the document ID prefix based on type
        const idPrefix = actualDocumentType === "invoice" ? "INVOICE" : "QUOTE";

        // Update header text - capitalize first letter
        const headerText =
          actualDocumentType.charAt(0).toUpperCase() +
          actualDocumentType.slice(1);
        invoiceWindow.document.querySelector(".invoice-title").textContent =
          headerText;

        // Update header ID
        invoiceWindow.document.getElementById(
          "invoice-id"
        ).textContent = `${idPrefix} #${documentId}`;
        invoiceWindow.document.getElementById("invoice-date").textContent =
          new Date().toLocaleDateString();

        // Update billing information
        invoiceWindow.document.getElementById("customer-name").textContent =
          invoiceData.customer_name;
        invoiceWindow.document.getElementById("customer-address").textContent =
          invoiceData.customer_address;
        invoiceWindow.document.getElementById("customer-phone").textContent =
          invoiceData.customer_phone;
        invoiceWindow.document.getElementById("reg-number").textContent =
          invoiceData.customer_reg_no;
        invoiceWindow.document.getElementById("made").textContent =
          invoiceData.customer_made;
        invoiceWindow.document.getElementById("mileage").textContent =
          invoiceData.customer_mileage;
        invoiceWindow.document.getElementById("customer-vin").textContent =
          invoiceData.customer_vin || "N/A";
        if (invoiceWindow.document.getElementById("color")) {
          invoiceWindow.document.getElementById("color").textContent =
            invoiceData.customer_color || "N/A";
        }
        if (invoiceWindow.document.getElementById("chasis")) {
          invoiceWindow.document.getElementById("chasis").textContent =
            invoiceData.customer_chasis || "N/A";
        }

        // Update totals heading based on document type
        if (actualDocumentType === "quote") {
          const balanceElement = invoiceWindow.document.querySelector(
            ".total-row:last-of-type"
          );
          if (balanceElement) {
            balanceElement.innerHTML = balanceElement.innerHTML.replace(
              "Balance",
              "Total Quotation"
            );
          }
        }

        // Populate totals
        invoiceWindow.document.getElementById(
          "advance"
        ).textContent = `${invoiceData.advance.toFixed(2)} PKR`;

        let netTotal = 0;
        const partsTableBody =
          invoiceWindow.document.getElementById("parts-table-body");
        const labourTableBody =
          invoiceWindow.document.getElementById("labour-table-body");

        // Clear existing rows (if any)
        while (partsTableBody.firstChild) {
          partsTableBody.removeChild(partsTableBody.firstChild);
        }

        while (labourTableBody.firstChild) {
          labourTableBody.removeChild(labourTableBody.firstChild);
        }

        // Insert Parts & Lubricants
        invoiceData.items.forEach((item) => {
          if (item.quantity) {
            const subtotal = item.quantity * item.price;
            netTotal += subtotal;

            const newRow = document.createElement("tr");
            newRow.innerHTML = `
                                  <td>${item.product_name}</td>
                                  <td>${item.price.toFixed(2)}</td>
                                  <td>${item.quantity}</td>
                                  <td>${subtotal.toFixed(2)}</td>
                              `;
            partsTableBody.appendChild(newRow);
          }
        });

        // Insert Labour Entries
        invoiceData.labours.forEach((item) => {
          const subtotal = item.price;
          netTotal += subtotal;

          const newRow = document.createElement("tr");
          newRow.innerHTML = `
                                <td>${item.description}</td>
                                <td>${item.price.toFixed(2)}</td>
                                <td>${subtotal.toFixed(2)}</td>
                            `;
          labourTableBody.appendChild(newRow);
        });

        // Update totals
        invoiceWindow.document.getElementById(
          "net-total"
        ).textContent = `${netTotal.toFixed(2)} PKR`;
        const balance = netTotal - invoiceData.advance;
        invoiceWindow.document.getElementById(
          "balance"
        ).textContent = `${balance.toFixed(2)} PKR`;

        // Update notes section
        const notesElement =
          invoiceWindow.document.querySelector(".notes-content");
        if (notesElement) {
          notesElement.innerHTML = `
            <strong>Thank you for choosing GermanATO!</strong><br>
            We appreciate your business and trust in our services. 
            For any queries or concerns, please don't hesitate to contact us.
          `;
        }

        // Handle terms and conditions visibility based on document type
        const termsContainer =
          invoiceWindow.document.querySelector(".terms-container");
        if (termsContainer) {
          if (actualDocumentType === "invoice") {
            // Hide terms and conditions for invoices
            termsContainer.style.display = "none";
          } else {
            // Show terms and conditions for quotes
            termsContainer.style.display = "block";
          }
        }
      };
    })
    .catch((error) => {
      console.error("Error loading invoice template:", error);
    });
}

export { openInvoiceTemplate };
