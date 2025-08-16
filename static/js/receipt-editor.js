/**
 * Receipt Editor JavaScript Module
 * Handles all receipt editing functionality with proper subtotal updates
 */

// Global state
let receiptIsBalanced = true;

/**
 * Calculate the subtotal from all line items
 * @returns {number} The calculated subtotal
 */
function calculateSubtotal() {
    let subtotal = 0;
    document.querySelectorAll('.item-row').forEach(row => {
        const itemTotalElement = row.querySelector('.item-total');
        const itemTotal = parseFloat(itemTotalElement.dataset.fullValue || itemTotalElement.value) || 0;
        subtotal += itemTotal;
    });
    return subtotal;
}

/**
 * Update the subtotal field based on current items
 */
function updateSubtotal() {
    const subtotal = calculateSubtotal();
    const subtotalField = document.getElementById('subtotal');
    if (subtotalField) {
        subtotalField.value = subtotal.toFixed(2);
    }
}

/**
 * Update item total when quantity or price changes
 * @param {HTMLElement} row - The item row element
 */
function updateItemTotal(row) {
    const quantity = parseFloat(row.querySelector('.item-quantity').value) || 0;
    const price = parseFloat(row.querySelector('.item-price').value) || 0;
    const total = quantity * price;
    const totalField = row.querySelector('.item-total');
    totalField.value = total.toFixed(2);  // Display with 2 decimals
    totalField.dataset.fullValue = total;  // Store full precision
    
    // Update subtotal after item changes
    updateSubtotal();
    updateProrations();
}

/**
 * Update prorations for all items
 */
function updateProrations() {
    const subtotal = parseFloat(document.getElementById('subtotal').value) || 0;
    const tax = parseFloat(document.getElementById('tax').value) || 0;
    const tip = parseFloat(document.getElementById('tip').value) || 0;
    
    document.querySelectorAll('.item-row').forEach(row => {
        const itemTotalElement = row.querySelector('.item-total');
        const quantityElement = row.querySelector('.item-quantity');
        const priceElement = row.querySelector('.item-price');
        
        const itemTotal = parseFloat(itemTotalElement.dataset.fullValue || itemTotalElement.value) || 0;
        const quantity = parseInt(quantityElement.value) || 0;
        const price = parseFloat(priceElement.value) || 0;
        
        // Update proration display
        if (subtotal > 0) {
            const proportion = itemTotal / subtotal;
            const itemTax = tax * proportion;
            const itemTip = tip * proportion;
            const perItemShare = (itemTotal + itemTax + itemTip) / (quantity || 1);
            const proration = row.querySelector('.item-proration');
            if (proration) {
                proration.innerHTML = 
                    `+ Tax: $${itemTax.toFixed(2)} + Tip: $${itemTip.toFixed(2)} = <span class="font-semibold">$${perItemShare.toFixed(2)}</span> per item`;
            }
        }
    });
    
    // Check balance after updating prorations
    checkAndDisplayBalance();
}

/**
 * Add a new item row
 */
function addItem() {
    const container = document.getElementById('items-container');
    const newRow = document.createElement('div');
    newRow.className = 'item-row flex gap-2 items-start';
    newRow.innerHTML = `
        <div class="flex-1 border rounded-lg p-4">
            <div class="flex gap-2 items-center">
                <div class="flex-1">
                    <input type="text" placeholder="Item name" class="item-name w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500">
                </div>
                <div class="w-16">
                    <input type="number" value="1" min="1" placeholder="Qty" class="item-quantity w-full px-2 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 text-center tabular-nums">
                </div>
                <span class="text-gray-500 font-medium">×</span>
                <div class="w-24">
                    <input type="number" step="0.01" placeholder="Price" class="item-price w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 text-right tabular-nums">
                </div>
                <span class="text-gray-500 font-medium">=</span>
                <div class="w-28">
                    <input type="number" step="0.01" placeholder="Total" class="item-total w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-semibold focus:ring-2 focus:ring-blue-500 text-right tabular-nums bg-gray-50" readonly>
                </div>
            </div>
            <div class="mt-2">
                <p class="text-gray-500 text-xs item-proration"></p>
            </div>
        </div>
        <button onclick="removeItem(this)" class="text-red-600 hover:text-red-800 p-2 hover:bg-red-50 rounded-lg transition-colors mt-3">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
        </button>
    `;
    container.appendChild(newRow);
    attachItemListeners(newRow);
}

/**
 * Remove an item and update subtotal
 * @param {HTMLElement} button - The remove button element
 */
function removeItem(button) {
    button.closest('.item-row').remove();
    // Update subtotal after removing item
    updateSubtotal();
    updateProrations();
}

/**
 * Attach event listeners to item row
 * @param {HTMLElement} row - The item row element
 */
function attachItemListeners(row) {
    row.querySelector('.item-quantity').addEventListener('input', () => {
        updateItemTotal(row);
        updateProrations();
    });
    row.querySelector('.item-price').addEventListener('input', () => {
        updateItemTotal(row);
        updateProrations();
    });
}

/**
 * Validate receipt balance
 * @returns {Array} Array of error messages
 */
function validateReceipt() {
    const data = getReceiptData();
    const errors = [];
    
    // Calculate items sum
    let itemsSum = 0;
    data.items.forEach((item, index) => {
        if (item.name) {
            const expected = item.quantity * item.unit_price;
            if (Math.abs(expected - item.total_price) > 0.01) {
                errors.push(`Item "${item.name}": Total $${item.total_price.toFixed(2)} doesn't match quantity (${item.quantity}) × price ($${item.unit_price.toFixed(2)}) = $${expected.toFixed(2)}`);
            }
            itemsSum += item.total_price;
        }
    });
    
    // Check if items sum matches subtotal
    if (Math.abs(itemsSum - data.subtotal) > 0.01) {
        errors.push(`Subtotal $${data.subtotal.toFixed(2)} doesn't match sum of items $${itemsSum.toFixed(2)}`);
    }
    
    // Check if subtotal + tax + tip = total
    const calculatedTotal = data.subtotal + data.tax + data.tip;
    if (Math.abs(calculatedTotal - data.total) > 0.01) {
        errors.push(`Total $${data.total.toFixed(2)} doesn't match subtotal ($${data.subtotal.toFixed(2)}) + tax ($${data.tax.toFixed(2)}) + tip ($${data.tip.toFixed(2)}) = $${calculatedTotal.toFixed(2)}`);
    }
    
    // Check for negative values
    if (data.subtotal < 0) errors.push("Subtotal cannot be negative");
    if (data.total < 0) errors.push("Total cannot be negative");
    
    return errors;
}

/**
 * Check and display balance status
 */
function checkAndDisplayBalance() {
    const errors = validateReceipt();
    const warningDiv = document.getElementById('balance-warning');
    const errorDetails = document.getElementById('balance-error-details');
    const finalizeBtn = document.querySelector('button[onclick="finalizeReceipt()"]');
    
    if (errors.length > 0) {
        // Show warning banner
        if (warningDiv) warningDiv.classList.remove('hidden');
        if (errorDetails) {
            errorDetails.innerHTML = '<ul class="list-disc list-inside space-y-1">' + 
                errors.map(e => `<li>${e}</li>`).join('') + 
                '</ul>';
        }
        
        // Disable finalize button
        if (finalizeBtn) {
            finalizeBtn.disabled = true;
            finalizeBtn.classList.add('opacity-50', 'cursor-not-allowed');
        }
        
        receiptIsBalanced = false;
    } else {
        // Hide warning banner
        if (warningDiv) warningDiv.classList.add('hidden');
        
        // Enable finalize button
        if (finalizeBtn) {
            finalizeBtn.disabled = false;
            finalizeBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        }
        
        receiptIsBalanced = true;
    }
}

/**
 * Get receipt data from form
 * @returns {Object} Receipt data object
 */
function getReceiptData() {
    const items = [];
    document.querySelectorAll('.item-row').forEach(row => {
        const name = row.querySelector('.item-name').value;
        if (name) {
            const itemTotalElement = row.querySelector('.item-total');
            items.push({
                name: name,
                quantity: parseInt(row.querySelector('.item-quantity').value) || 1,
                unit_price: parseFloat(row.querySelector('.item-price').value) || 0,
                total_price: parseFloat(itemTotalElement.dataset.fullValue || itemTotalElement.value) || 0
            });
        }
    });
    
    const restaurantEl = document.getElementById('restaurant_name');
    const subtotalEl = document.getElementById('subtotal');
    const taxEl = document.getElementById('tax');
    const tipEl = document.getElementById('tip');
    const totalEl = document.getElementById('total');
    
    return {
        restaurant_name: restaurantEl ? restaurantEl.value : '',
        subtotal: subtotalEl ? (parseFloat(subtotalEl.value) || 0) : 0,
        tax: taxEl ? (parseFloat(taxEl.value) || 0) : 0,
        tip: tipEl ? (parseFloat(tipEl.value) || 0) : 0,
        total: totalEl ? (parseFloat(totalEl.value) || 0) : 0,
        items: items
    };
}

// Make functions globally available in browser
if (typeof window !== 'undefined') {
    window.calculateSubtotal = calculateSubtotal;
    window.updateSubtotal = updateSubtotal;
    window.updateItemTotal = updateItemTotal;
    window.updateProrations = updateProrations;
    window.addItem = addItem;
    window.removeItem = removeItem;
    window.attachItemListeners = attachItemListeners;
    window.validateReceipt = validateReceipt;
    window.checkAndDisplayBalance = checkAndDisplayBalance;
    window.getReceiptData = getReceiptData;
    window.receiptIsBalanced = receiptIsBalanced;
}

// Export functions for testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        calculateSubtotal,
        updateSubtotal,
        updateItemTotal,
        updateProrations,
        addItem,
        removeItem,
        attachItemListeners,
        validateReceipt,
        checkAndDisplayBalance,
        getReceiptData
    };
}