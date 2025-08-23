/**
 * Edit page functionality - All receipt editing logic in one place
 * Depends on: utils.js (for escapeHtml and authenticatedFetch functions)
 */

// Page state variables
let receiptSlug = null;
let receiptId = null;
let receiptTip = 0;
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
        receiptTip = parseFloat(container.dataset.receiptTip) || 0;
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
        if (itemTotalElement) {
            const itemTotal = parseFloat(itemTotalElement.dataset.fullValue || itemTotalElement.value) || 0;
            subtotal += itemTotal;
        }
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
    const subtotalEl = document.getElementById('subtotal');
    const taxEl = document.getElementById('tax');
    const tipEl = document.getElementById('tip');
    
    const subtotal = subtotalEl ? (parseFloat(subtotalEl.value) || 0) : 0;
    const tax = taxEl ? (parseFloat(taxEl.value) || 0) : 0;
    const tip = tipEl ? (parseFloat(tipEl.value) || 0) : 0;
    
    document.querySelectorAll('.item-row').forEach(row => {
        const itemTotalElement = row.querySelector('.item-total');
        const quantityElement = row.querySelector('.item-quantity');
        const priceElement = row.querySelector('.item-price');
        
        const itemTotal = itemTotalElement ? (parseFloat(itemTotalElement.dataset.fullValue || itemTotalElement.value) || 0) : 0;
        const quantity = quantityElement ? (parseInt(quantityElement.value) || 0) : 0;
        const price = priceElement ? (parseFloat(priceElement.value) || 0) : 0;
        
        // Update proration display
        if (subtotal > 0) {
            const proportion = itemTotal / subtotal;
            const itemTax = tax * proportion;
            const itemTip = tip * proportion;
            const perItemShare = (itemTotal + itemTax + itemTip) / (quantity || 1);
            const proration = row.querySelector('.item-proration');
            if (proration) {
                // Use textContent for simple text, create span separately for safety
                const span = document.createElement('span');
                span.className = 'font-semibold';
                span.textContent = `$${perItemShare.toFixed(2)}`;
                
                proration.textContent = `+ Tax: $${itemTax.toFixed(2)} + Tip: $${itemTip.toFixed(2)} = `;
                proration.appendChild(span);
                proration.appendChild(document.createTextNode(' per item'));
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
    
    // Check for negative values (allow negative tax/tip as discounts)
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
            // Create error list safely using DOM methods
            const ul = document.createElement('ul');
            ul.className = 'list-disc list-inside space-y-1';
            errors.forEach(error => {
                const li = document.createElement('li');
                li.textContent = error;
                ul.appendChild(li);
            });
            errorDetails.innerHTML = '';
            errorDetails.appendChild(ul);
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
    if (!container) return;
    
    // Use TemplateUtils to create item row
    const clone = window.TemplateUtils.createItemRow();
    if (!clone) {
        console.error('Failed to create item row from template');
        return;
    }
    
    container.appendChild(clone);
    
    // Get the newly added row (last child)
    const newRow = container.lastElementChild;
    attachItemListeners(newRow);
    
    // Attach remove button listener
    const removeBtn = newRow.querySelector('[data-action="remove-item"]');
    if (removeBtn) {
        removeBtn.addEventListener('click', function() {
            removeItem(this);
        });
    }
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
    const quantityInput = row.querySelector('.item-quantity');
    quantityInput.addEventListener('input', (e) => {
        // Enforce max 2 digits (99)
        if (e.target.value.length > 2) {
            e.target.value = e.target.value.slice(0, 2);
        }
        // Ensure value is between 1 and 99
        if (parseInt(e.target.value) > 99) {
            e.target.value = 99;
        }
        if (parseInt(e.target.value) < 1 && e.target.value !== '') {
            e.target.value = 1;
        }
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
        const nameEl = row.querySelector('.item-name');
        const name = nameEl ? nameEl.value : '';
        if (name) {
            const quantityEl = row.querySelector('.item-quantity');
            const priceEl = row.querySelector('.item-price');
            const itemTotalElement = row.querySelector('.item-total');
            items.push({
                name: name,
                quantity: quantityEl ? (parseInt(quantityEl.value) || 1) : 1,
                unit_price: priceEl ? (parseFloat(priceEl.value) || 0) : 0,
                total_price: itemTotalElement ? (parseFloat(itemTotalElement.dataset.fullValue || itemTotalElement.value) || 0) : 0
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
    isProcessing = true;
    
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
    } finally {
        isProcessing = false;
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
            const qrCanvas = document.getElementById('qr-code-share-url');
            if (qrCanvas) {
                QRCode.toCanvas(qrCanvas, data.share_url);
            }
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
    try {
        window.location.href = document.getElementById('share-url').value;
    } catch (e) {
        // Navigation not supported in test environments (JSDOM) - this is expected
        console.log('Navigation attempted but not supported in test environment');
    }
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
                                try {
                                    window.location.href = '/';
                                } catch (e) {
                                    // Navigation not supported in test environments (JSDOM) - this is expected
                                    console.log('Navigation attempted but not supported in test environment');
                                }
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
// TIP MODAL FUNCTIONS
// ============================================================================

function initializeTipModal() {
    const template = document.getElementById('add-tip-modal-template');
    if (!template) return;

    const modal = template.content.cloneNode(true).firstElementChild;
    document.body.appendChild(modal);

    const tipValueInput = modal.querySelector('[data-input="tip-value"]');
    const tipTypeButtons = modal.querySelectorAll('[data-action="set-tip-type"]');
    const tipBasisOptions = modal.querySelector('[data-show-for="percentage"]');
    const tipBasisRadios = modal.querySelectorAll('input[name="tip-basis"]');

    let tipType = 'percentage'; // 'percentage' or 'dollar'
    let presetTipApplied = false;

    function updateTipTypeUI() {
        tipTypeButtons.forEach(btn => {
            if (btn.dataset.type === tipType) {
                btn.classList.add('bg-gray-200');
            } else {
                btn.classList.remove('bg-gray-200');
            }
        });
        tipBasisOptions.classList.toggle('hidden', tipType !== 'percentage');
    }

    function calculateTip() {
        const subtotal = parseFloat(document.getElementById('subtotal').value) || 0;
        const tax = parseFloat(document.getElementById('tax').value) || 0;
        let inputValue = parseFloat(tipValueInput.value) || 0;

        if (presetTipApplied) {
            const tipBasis = modal.querySelector('input[name="tip-basis"]:checked').value;
            const base = tipBasis === 'pre-tax' ? subtotal : subtotal + tax;
            return base * (inputValue / 100);
        }

        if (tipType === 'percentage') {
            const tipBasis = modal.querySelector('input[name="tip-basis"]:checked').value;
            const base = tipBasis === 'pre-tax' ? subtotal : subtotal + tax;
            return base * (inputValue / 100);
        } else {
            return inputValue;
        }
    }

    modal.querySelectorAll('[data-action="set-tip-percentage"]').forEach(button => {
        button.addEventListener('click', () => {
            tipType = 'percentage';
            tipValueInput.value = button.dataset.value;
            presetTipApplied = true;
            updateTipTypeUI();
        });
    });

    tipTypeButtons.forEach(button => {
        button.addEventListener('click', () => {
            const previousTipType = tipType;
            tipType = button.dataset.type;
            presetTipApplied = false;
            updateTipTypeUI();

            const subtotal = parseFloat(document.getElementById('subtotal').value) || 0;
            const tax = parseFloat(document.getElementById('tax').value) || 0;
            const inputValue = parseFloat(tipValueInput.value) || 0;

            if (tipType === 'percentage' && previousTipType === 'dollar') {
                const base = subtotal > 0 ? subtotal : 1;
                tipValueInput.value = ((inputValue / base) * 100).toFixed(2);
            } else if (tipType === 'dollar' && previousTipType === 'percentage') {
                const tipBasis = modal.querySelector('input[name="tip-basis"]:checked').value;
                const base = tipBasis === 'pre-tax' ? subtotal : subtotal + tax;
                tipValueInput.value = (base * (inputValue / 100)).toFixed(2);
            }
        });
    });

    tipValueInput.addEventListener('input', () => {
        presetTipApplied = false;
    });

    tipBasisRadios.forEach(radio => {
        radio.addEventListener('input', () => {
            presetTipApplied = false;
        });
    });

    modal.querySelector('[data-action="apply-tip"]').addEventListener('click', () => {
        const finalTip = calculateTip();
        const tipField = document.getElementById('tip');
        const totalField = document.getElementById('total');
        const subtotal = parseFloat(document.getElementById('subtotal').value) || 0;
        const tax = parseFloat(document.getElementById('tax').value) || 0;

        tipField.value = finalTip.toFixed(2);
        totalField.value = (subtotal + tax + finalTip).toFixed(2);

        // Trigger updates
        tipField.dispatchEvent(new Event('input'));

        modal.remove();
    });

    modal.querySelector('[data-action="close-tip-modal"]').addEventListener('click', () => {
        modal.remove();
    });

    updateTipTypeUI();
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

        // Show tip modal if tip is zero
        if (receiptTip === 0) {
            initializeTipModal();
        }
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
    
    // Share buttons are initialized automatically by utils.js
    
    // Attach remove item handlers
    document.querySelectorAll('[data-action="remove-item"]').forEach(btn => {
        btn.addEventListener('click', function() {
            removeItem(this);
        });
    });
});

// ==========================================================================
// Module Exports for Testing
// ==========================================================================

// Export for use in Node.js/ES modules (for testing)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        // Initialization
        initializeEditPage,
        
        // Calculation and Validation
        calculateSubtotal,
        updateSubtotal,
        updateItemTotal,
        updateProrations,
        validateReceipt,
        checkAndDisplayBalance,
        
        // Item Management
        addItem,
        removeItem,
        attachItemListeners,
        getReceiptData,
        
        // Server Communication
        saveReceipt,
        finalizeReceipt,
        closeShareModal,
        
        // Processing
        startProcessingPoll,
        initializeProcessingAnimations,

        // Tip Modal
        initializeTipModal,
        
        // State variables (for testing)
        _getState: () => ({ receiptSlug, receiptId, isProcessing, receiptIsBalanced }),
        _setState: (state) => {
            if (state.receiptSlug !== undefined) receiptSlug = state.receiptSlug;
            if (state.receiptId !== undefined) receiptId = state.receiptId;
            if (state.isProcessing !== undefined) isProcessing = state.isProcessing;
            if (state.receiptIsBalanced !== undefined) receiptIsBalanced = state.receiptIsBalanced;
        }
    };
}