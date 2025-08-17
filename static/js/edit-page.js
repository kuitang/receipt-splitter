/**
 * Edit page functionality - All receipt editing logic in one place
 * Depends on: utils.js (for escapeHtml and authenticatedFetch functions)
 */

// Page state variables
let receiptSlug = null;
let receiptId = null;
let isProcessing = false;
let receiptIsBalanced = true;

/**
 * Initialize edit page with data from DOM
 */
function initializeEditPage() {
    const container = document.getElementById('edit-page-data');
    if (container) {
        receiptSlug = container.dataset.receiptSlug;
        receiptId = container.dataset.receiptId;
        isProcessing = container.dataset.isProcessing === 'true';
    }
}

// ============================================================================
// RECEIPT CALCULATION AND VALIDATION FUNCTIONS
// ============================================================================

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
    const finalizeBtn = document.querySelector('[data-action="finalize"]');
    
    if (errors.length > 0) {
        // Show warning banner
        if (warningDiv) warningDiv.classList.remove('hidden');
        if (errorDetails) {
            errorDetails.innerHTML = '<ul class="list-disc list-inside space-y-1">' + 
                errors.map(e => `<li>${escapeHtml(e)}</li>`).join('') + 
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
        
        // Enable finalize button (but only if not processing)
        if (finalizeBtn && !isProcessing) {
            finalizeBtn.disabled = false;
            finalizeBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        }
        
        receiptIsBalanced = true;
    }
}

// ============================================================================
// ITEM MANAGEMENT FUNCTIONS
// ============================================================================

/**
 * Add a new item row
 */
function addItem() {
    if (isProcessing) return;
    
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
        <button data-action="remove-item" class="text-red-600 hover:text-red-800 p-2 hover:bg-red-50 rounded-lg transition-colors mt-3">
            <div class="w-5 h-5 flex items-center justify-center text-lg font-bold">×</div>
        </button>
    `;
    container.appendChild(newRow);
    attachItemListeners(newRow);
    
    // Attach remove button listener
    newRow.querySelector('[data-action="remove-item"]').addEventListener('click', function() {
        removeItem(this);
    });
}

/**
 * Remove an item and update subtotal
 * @param {HTMLElement} button - The remove button element
 */
function removeItem(button) {
    if (isProcessing) return;
    
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

// ============================================================================
// SERVER COMMUNICATION FUNCTIONS
// ============================================================================

/**
 * Save receipt to server
 */
async function saveReceipt(skipReload = false) {
    if (isProcessing) return;
    
    const data = getReceiptData();
    
    try {
        const response = await authenticatedJsonFetch(`/update/${receiptSlug}/`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            // Check validation status from backend
            if (result.is_balanced) {
                // Only reload if not called from finalize flow
                if (!skipReload) {
                    location.reload();
                }
            } else {
                // Keep this alert as it warns about balance issues
                alert('Receipt saved, but it doesn\'t balance. Please review the errors shown above.');
            }
            
            // Update UI based on backend validation
            checkAndDisplayBalance();
        } else {
            // Keep error alerts as they require user attention
            alert('Error saving receipt: ' + (result.error || 'Unknown error'));
        }
    } catch (error) {
        // Keep error alerts as they require user attention
        alert('Error saving receipt: ' + error.message);
    }
}

/**
 * Finalize receipt
 */
async function finalizeReceipt() {
    if (isProcessing) return;
    
    // Check balance before allowing finalization
    if (!receiptIsBalanced) {
        // Keep this alert as it prevents invalid finalization
        alert('Cannot finalize receipt: The receipt doesn\'t balance. Please fix the errors shown above.');
        return;
    }
    
    if (!confirm('Once finalized, this receipt cannot be edited. Continue?')) {
        return;
    }
    
    // Pass true to skip reload when saving during finalization
    await saveReceipt(true);
    
    try {
        const response = await authenticatedFetch(`/finalize/${receiptSlug}/`, {
            method: 'POST'
        });
        
        if (response.ok) {
            const data = await response.json();
            document.getElementById('share-url').value = data.share_url;
            QRCode.toCanvas(document.getElementById('qr-code'), data.share_url);
            document.getElementById('share-modal').classList.remove('hidden');
        } else {
            const error = await response.json();
            // Format validation errors nicely
            let errorMessage = error.error || 'Unknown error';
            if (error.validation_errors) {
                console.error('Validation errors:', error.validation_errors);
            }
            // Keep error alerts as they require user attention
            alert('Error finalizing receipt: ' + errorMessage);
        }
    } catch (error) {
        // Keep error alerts as they require user attention
        alert('Error finalizing receipt: ' + error.message);
    }
}

/**
 * Close share modal and navigate to share URL
 */
function closeShareModal() {
    window.location.href = document.getElementById('share-url').value;
}

// ============================================================================
// PROCESSING MODAL FUNCTIONS
// ============================================================================

/**
 * Poll for processing status (Safari-compatible)
 */
function startProcessingPoll() {
    let pollCount = 0;
    const maxPolls = 60; // 60 seconds max
    
    function pollStatus() {
        pollCount++;
        
        // Use XMLHttpRequest for better Safari compatibility
        const xhr = new XMLHttpRequest();
        xhr.timeout = 10000; // 10 second timeout
        
        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4) {
                if (xhr.status === 200) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        
                        if (data.status === 'completed') {
                            // Reload the page to show the processed content
                            window.location.reload();
                        } else if (data.status === 'failed') {
                            document.getElementById('processing-status').innerHTML = 
                                '<div class="w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center text-xs font-bold">×</div>' +
                                '<span class="text-sm text-red-600">Processing failed. Please try again.</span>';
                            setTimeout(function() {
                                window.location.href = '/';
                            }, 3000);
                        } else if (pollCount < maxPolls) {
                            // Continue polling
                            setTimeout(pollStatus, 1000);
                        } else {
                            document.getElementById('processing-status').innerHTML = 
                                '<span class="text-sm text-orange-600">Taking longer than expected...</span>';
                        }
                    } catch (e) {
                        console.error('Error parsing status response:', e);
                        if (pollCount < maxPolls) {
                            setTimeout(pollStatus, 2000); // Retry with longer delay
                        }
                    }
                } else {
                    console.error('Status check failed:', xhr.status, xhr.statusText);
                    if (pollCount < maxPolls) {
                        setTimeout(pollStatus, 2000); // Retry with longer delay
                    }
                }
            }
        };
        
        xhr.ontimeout = function() {
            console.error('Status check timed out');
            if (pollCount < maxPolls) {
                setTimeout(pollStatus, 2000); // Retry with longer delay
            }
        };
        
        xhr.onerror = function() {
            console.error('Status check network error');
            if (pollCount < maxPolls) {
                setTimeout(pollStatus, 2000); // Retry with longer delay
            }
        };
        
        xhr.open('GET', '/status/' + receiptSlug + '/', true);
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.send();
    }
    
    // Start polling
    setTimeout(pollStatus, 1000);
}

/**
 * Initialize processing animations
 */
function initializeProcessingAnimations() {
    const messages = [
        "🚀 Our AI is scanning faster than a caffeinated cashier!",
        "🤖 Teaching robots to read receipts since 2024...",
        "🔍 Zooming in on those tiny printed numbers...",
        "⚡ Processing at the speed of light (almost)!",
        "🎯 Extracting prices with laser precision...",
        "🧮 Crunching numbers like a hungry calculator...",
        "📸 Pixels to prices in progress...",
        "🎪 Watch as we turn images into itemized lists!",
        "🌟 Making receipt magic happen..."
    ];
    
    let messageIndex = 0;
    const messageElement = document.getElementById('fun-message');
    
    // Rotate messages every 2 seconds
    if (messageElement) {
        setInterval(() => {
            messageIndex = (messageIndex + 1) % messages.length;
            messageElement.innerHTML = `<p class="text-gray-600 font-medium">${messages[messageIndex]}</p>`;
            messageElement.classList.add('wiggle');
            setTimeout(() => messageElement.classList.remove('wiggle'), 500);
        }, 2000);
    }
    
    // Show "Almost done" message after 5 seconds
    setTimeout(() => {
        const almostDone = document.getElementById('almost-done');
        if (almostDone) {
            almostDone.style.opacity = '1';
        }
    }, 5000);
    
    // Update time estimate countdown
    let timeLeft = 10;
    const timeEstimate = document.getElementById('time-estimate');
    if (timeEstimate) {
        const countdown = setInterval(() => {
            timeLeft--;
            if (timeLeft > 0) {
                timeEstimate.textContent = `Estimated time: ${timeLeft} seconds`;
            } else {
                timeEstimate.textContent = "Just a moment more...";
                clearInterval(countdown);
            }
        }, 1000);
    }
}

// ============================================================================
// PAGE INITIALIZATION
// ============================================================================

/**
 * Initialize edit page on DOM ready
 */
document.addEventListener('DOMContentLoaded', () => {
    initializeEditPage();
    
    if (isProcessing) {
        startProcessingPoll();
        initializeProcessingAnimations();
    } else {
        // Initialize receipt editor functionality
        document.querySelectorAll('.item-row').forEach(attachItemListeners);
        
        // Also update prorations on load
        updateProrations();
        
        // Add event listeners for all fields that affect balance
        const fieldsToWatch = ['subtotal', 'tax', 'tip', 'total'];
        fieldsToWatch.forEach(fieldId => {
            const field = document.getElementById(fieldId);
            if (field) {
                field.addEventListener('input', () => {
                    updateProrations();
                    checkAndDisplayBalance();
                });
            }
        });
        
        // Initial balance check
        checkAndDisplayBalance();
    }
    
    // Attach button event handlers
    const saveBtn = document.querySelector('[data-action="save"]');
    if (saveBtn) {
        saveBtn.addEventListener('click', () => saveReceipt());
    }
    
    const finalizeBtn = document.querySelector('[data-action="finalize"]');
    if (finalizeBtn) {
        finalizeBtn.addEventListener('click', () => finalizeReceipt());
    }
    
    const addItemBtn = document.querySelector('[data-action="add-item"]');
    if (addItemBtn) {
        addItemBtn.addEventListener('click', () => addItem());
    }
    
    const closeModalBtn = document.querySelector('[data-action="close-share-modal"]');
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', () => closeShareModal());
    }
    
    // Attach copy share URL handlers
    document.querySelectorAll('[data-action="copy-share-url"]').forEach(btn => {
        btn.addEventListener('click', function(event) {
            const widgetId = this.dataset.widgetId || 'share-url';
            copyShareUrl(widgetId, event);
        });
    });
    
    // Attach remove item handlers
    document.querySelectorAll('[data-action="remove-item"]').forEach(btn => {
        btn.addEventListener('click', function() {
            removeItem(this);
        });
    });
});