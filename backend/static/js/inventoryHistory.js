/**
 * Inventory Transaction History Module
 * Handles displaying and filtering inventory transaction history
 */

// State management
let currentPage = 1;
let perPage = 50;
let totalPages = 1;
let totalTransactions = 0;
let isLoading = false;

// DOM Elements
const transactionsBody = document.getElementById('transactions-body');
const loadingState = document.getElementById('loading-state');
const emptyState = document.getElementById('empty-state');
const paginationContainer = document.getElementById('pagination-container');

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Set default date range (last 30 days)
    const today = new Date();
    const thirtyDaysAgo = new Date(today);
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
    
    document.getElementById('date-to').value = formatDateForInput(today);
    document.getElementById('date-from').value = formatDateForInput(thirtyDaysAgo);
    
    // Add event listeners for enter key on input fields
    document.getElementById('inventory-search').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') applyFilters();
    });
    document.getElementById('repair-order-search').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') applyFilters();
    });
    
    // Load transactions
    loadTransactions();
});

/**
 * Format date for input field
 */
function formatDateForInput(date) {
    return date.toISOString().split('T')[0];
}

/**
 * Load transactions from API
 */
async function loadTransactions() {
    if (isLoading) return;
    isLoading = true;
    
    showLoading();
    
    try {
        // Build query parameters
        const params = new URLSearchParams();
        params.append('page', currentPage);
        params.append('per_page', perPage);
        
        const dateFrom = document.getElementById('date-from').value;
        const dateTo = document.getElementById('date-to').value;
        const transactionType = document.getElementById('transaction-type').value;
        const repairOrderId = document.getElementById('repair-order-search').value;
        const inventorySearch = document.getElementById('inventory-search').value;
        
        if (dateFrom) params.append('date_from', dateFrom);
        if (dateTo) params.append('date_to', dateTo);
        if (transactionType) params.append('transaction_type', transactionType);
        if (repairOrderId) params.append('repair_order_id', repairOrderId);
        if (inventorySearch) params.append('search', inventorySearch);
        
        const response = await APIHelper.get(`/api/inventory/transactions?${params.toString()}`);
        
        if (response) {
            const { transactions, pagination } = response;
            
            totalTransactions = pagination.total;
            totalPages = pagination.pages;
            currentPage = pagination.page;
            
            renderTransactions(transactions);
            updatePagination(pagination);
            updateSummary(transactions);
            
            if (transactions.length === 0) {
                showEmpty();
            } else {
                hideEmpty();
            }
        } else {
            showError('Failed to load transactions');
        }
    } catch (error) {
        console.error('Error loading transactions:', error);
        showError('Error loading transactions');
    } finally {
        isLoading = false;
        hideLoading();
    }
}

/**
 * Render transactions in the table
 */
function renderTransactions(transactions) {
    transactionsBody.innerHTML = '';
    
    transactions.forEach(transaction => {
        const row = createTransactionRow(transaction);
        transactionsBody.appendChild(row);
    });
}

/**
 * Create a transaction row element
 */
function createTransactionRow(transaction) {
    const row = document.createElement('tr');
    row.className = `transaction-row ${transaction.transaction_type}`;
    
    const formattedDate = formatDateTime(transaction.created_at);
    const previousQuantity = Number(transaction.previous_quantity ?? 0);
    const newQuantity = Number(transaction.new_quantity ?? 0);
    const stockChangeDisplay = formatStockChange(
        transaction.quantity,
        transaction.transaction_type
    );
    const typeBadge = createTypeBadge(transaction.transaction_type);
    const repairOrderLink = createRepairOrderLink(transaction.repair_order_id);
    
    row.innerHTML = `
        <td class="transaction-id">#${transaction.id}</td>
        <td class="transaction-date">${formattedDate}</td>
        <td class="transaction-item">
            <div class="item-info">
                <span class="item-name">${transaction.inventory_name || 'Unknown Item'}</span>
                <span class="item-part-number">${transaction.inventory_part_number || ''}</span>
            </div>
        </td>
        <td class="transaction-type">${typeBadge}</td>
        <td class="transaction-quantity" title="Quantity before this transaction">${previousQuantity}</td>
        <td class="transaction-stock-change">${stockChangeDisplay}</td>
        <td class="transaction-total" title="Quantity after this transaction">${newQuantity}</td>
        <td class="transaction-repair-order">${repairOrderLink}</td>
        <td class="transaction-description">
            <span class="description-text" title="${transaction.reference_description || ''}">${transaction.reference_description || '-'}</span>
            ${transaction.notes ? `<span class="description-notes" title="${transaction.notes}">${truncateText(transaction.notes, 30)}</span>` : ''}
        </td>
    `;
    
    return row;
}

/**
 * Format date and time in local timezone
 */
function formatDateTime(dateString) {
    // Parse the date string - append 'Z' if no timezone to treat as UTC,
    // then JavaScript will convert to local time
    let date;
    if (dateString.includes('T') || dateString.includes('Z') || dateString.includes('+')) {
        // Already has timezone info or ISO format
        date = new Date(dateString);
    } else {
        // Server sends format like "2024-01-15 10:30:00" - treat as UTC
        date = new Date(dateString.replace(' ', 'T') + 'Z');
    }
    
    const dateStr = date.toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    });
    const timeStr = date.toLocaleTimeString('en-GB', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    });
    return `<span class="date">${dateStr}</span><span class="time">${timeStr}</span>`;
}

/**
 * Format stock change with an explicit sign (+5 / -1).
 */
function formatStockChange(quantity, transactionType) {
    const amount = Number(quantity ?? 0);
    let className = 'quantity-neutral';
    let display = String(amount);

    if (transactionType === 'issue_out' || amount < 0) {
        className = 'quantity-negative';
        display = String(amount); // already negative for issue_out
    } else if (transactionType === 'received' || amount > 0) {
        className = 'quantity-positive';
        display = `+${amount}`;
    }

    return `<span class="${className}">${display}</span>`;
}

/**
 * Create transaction type badge
 */
function createTypeBadge(transactionType) {
    const typeConfig = {
        'issue_out': {
            label: 'Issue Out',
            icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12l7 7 7-7"></path></svg>'
        },
        'received': {
            label: 'Received',
            icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 19V5M5 12l7-7 7 7"></path></svg>'
        },
        'adjustment': {
            label: 'Adjustment',
            icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>'
        }
    };
    
    const config = typeConfig[transactionType] || { label: transactionType, icon: '' };
    
    return `<span class="type-badge type-${transactionType}">
                ${config.icon}
                ${config.label}
            </span>`;
}

/**
 * Create repair order link
 */
function createRepairOrderLink(repairOrderId) {
    if (!repairOrderId) {
        return '<span class="no-reference">-</span>';
    }
    return `<a href="repair-orders-management.html?id=${repairOrderId}" class="repair-order-link" title="View Repair Order #${repairOrderId}">
                RO #${repairOrderId}
            </a>`;
}

/**
 * Truncate text
 */
function truncateText(text, maxLength) {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

/**
 * Update pagination controls
 */
function updatePagination(pagination) {
    const { page, per_page, total, pages, has_next, has_prev } = pagination;
    
    const start = total === 0 ? 0 : (page - 1) * per_page + 1;
    const end = Math.min(page * per_page, total);
    
    document.getElementById('showing-start').textContent = start;
    document.getElementById('showing-end').textContent = end;
    document.getElementById('total-count').textContent = total;
    document.getElementById('current-page').textContent = page;
    document.getElementById('total-pages').textContent = pages || 1;
    
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    
    prevBtn.disabled = !has_prev;
    nextBtn.disabled = !has_next;
}

/**
 * Update summary cards
 */
function updateSummary(transactions) {
    let issueOutCount = 0;
    let receivedCount = 0;
    let adjustmentCount = 0;
    
    transactions.forEach(t => {
        if (t.transaction_type === 'issue_out') issueOutCount++;
        else if (t.transaction_type === 'received') receivedCount++;
        else if (t.transaction_type === 'adjustment') adjustmentCount++;
    });
    
    document.getElementById('summary-issue-out').textContent = issueOutCount;
    document.getElementById('summary-received').textContent = receivedCount;
    document.getElementById('summary-adjustment').textContent = adjustmentCount;
    document.getElementById('summary-total').textContent = totalTransactions;
}

/**
 * Apply filters
 */
function applyFilters() {
    currentPage = 1;
    loadTransactions();
}

/**
 * Clear filters
 */
function clearFilters() {
    document.getElementById('date-from').value = '';
    document.getElementById('date-to').value = '';
    document.getElementById('transaction-type').value = '';
    document.getElementById('inventory-search').value = '';
    document.getElementById('repair-order-search').value = '';
    
    currentPage = 1;
    loadTransactions();
}

/**
 * Go to previous page
 */
function previousPage() {
    if (currentPage > 1) {
        currentPage--;
        loadTransactions();
    }
}

/**
 * Go to next page
 */
function nextPage() {
    if (currentPage < totalPages) {
        currentPage++;
        loadTransactions();
    }
}

/**
 * Show loading state
 */
function showLoading() {
    loadingState.style.display = 'flex';
    transactionsBody.style.opacity = '0.5';
}

/**
 * Hide loading state
 */
function hideLoading() {
    loadingState.style.display = 'none';
    transactionsBody.style.opacity = '1';
}

/**
 * Show empty state
 */
function showEmpty() {
    emptyState.style.display = 'flex';
    paginationContainer.style.display = 'none';
}

/**
 * Hide empty state
 */
function hideEmpty() {
    emptyState.style.display = 'none';
    paginationContainer.style.display = 'flex';
}

/**
 * Show error message
 */
function showError(message) {
    transactionsBody.innerHTML = `
        <tr>
            <td colspan="8" class="error-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <path d="M12 8v4M12 16h.01"></path>
                </svg>
                ${message}
            </td>
        </tr>
    `;
}
