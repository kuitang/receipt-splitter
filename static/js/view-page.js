/**
 * View page specific functionality for claiming items
 * Depends on: common.js
 */

// Global variables from template (will be set by data attributes)
let receiptSlug = null;
let receiptId = null;
let currentClaims = {};

/**
 * Initialize view page with data from DOM
 */
function initializeViewPage() {
    const container = document.getElementById('view-page-data');
    if (container) {
        receiptSlug = container.dataset.receiptSlug;
        receiptId = container.dataset.receiptId;
    }
}

/**
 * Validate that claims don't exceed available quantities and show banner
 */
function validateClaims() {
    let isValid = true;
    const errors = [];
    
    document.querySelectorAll('.claim-quantity').forEach(input => {
        const quantity = parseInt(input.value) || 0;
        const maxQuantity = parseInt(input.getAttribute('max')) || 0;
        
        if (quantity > maxQuantity) {
            input.classList.add('border-red-500', 'bg-red-50');
            
            // Find item name for error message
            const itemContainer = input.closest('.item-container') || input.parentElement.closest('.item-container');
            let itemName = 'Item';
            if (itemContainer) {
                const nameElement = itemContainer.querySelector('h3');
                if (nameElement) {
                    itemName = nameElement.textContent.trim();
                }
            }
            
            errors.push(`${itemName}: trying to claim ${quantity} but only ${maxQuantity} available`);
            isValid = false;
        } else {
            input.classList.remove('border-red-500', 'bg-red-50');
        }
    });
    
    // Show/hide validation banner
    const warningBanner = document.getElementById('claiming-warning');
    const errorDetails = document.getElementById('claiming-error-details');
    
    if (errors.length > 0 && warningBanner && errorDetails) {
        errorDetails.innerHTML = errors.map(error => `<div>• ${error}</div>`).join('');
        warningBanner.classList.remove('hidden');
    } else if (warningBanner) {
        warningBanner.classList.add('hidden');
    }
    
    return isValid;
}

/**
 * Check if user has any active claims (pending inputs > 0)
 */
function hasActiveClaims() {
    return Array.from(document.querySelectorAll('.claim-quantity')).some(input => {
        return (parseInt(input.value) || 0) > 0;
    });
}

/**
 * Update button state based on claims and existing total
 */
function updateButtonState() {
    const button = document.getElementById('claim-button');
    
    if (!button) return;
    
    // Enable button only if user has active pending claims (current input > 0)
    // Don't enable based on existing total - user needs to make new claims to submit
    const shouldEnable = hasActiveClaims();
    
    button.disabled = !shouldEnable;
}

/**
 * Update the total amount for claimed items
 */
function updateTotal() {
    // Get existing total from backend (cumulative from all previous sessions)
    const myTotalElement = document.getElementById('my-total');
    if (!myTotalElement) return;
    
    const existingTotal = parseFloat(myTotalElement.dataset.existingTotal) || 0;
    
    // Calculate current screen total
    let currentScreenTotal = 0;
    document.querySelectorAll('.claim-quantity').forEach(input => {
        const quantity = parseInt(input.value) || 0;
        if (quantity > 0) {
            const itemId = input.dataset.itemId;
            
            // Try to find share element - check if input is in a container or is standalone
            let shareElement = null;
            
            // First try: input is inside a container with data-item-id
            const itemContainer = document.querySelector(`[data-item-id="${itemId}"]`);
            if (itemContainer && itemContainer !== input) {
                shareElement = itemContainer.querySelector('.item-share-amount');
            }
            
            // Second try: share element is a sibling or nearby
            if (!shareElement) {
                shareElement = input.parentElement.querySelector('.item-share-amount') ||
                              input.closest('.item-container')?.querySelector('.item-share-amount');
            }
            
            if (shareElement) {
                const sharePerItem = parseFloat(shareElement.dataset.amount) || 0;
                currentScreenTotal += sharePerItem * quantity;
            }
        }
    });
    
    // Display total = existing total + current screen total
    const displayTotal = existingTotal + currentScreenTotal;
    myTotalElement.textContent = `$${displayTotal.toFixed(2)}`;
    
    // Validate claims and update button state
    validateClaims();
    updateButtonState();
}

/**
 * Confirm and submit claims
 */
async function confirmClaims() {
    // Validate claims first
    if (!validateClaims()) {
        alert('Please fix the highlighted items - you cannot claim more than available.');
        return;
    }
    
    const claims = [];
    document.querySelectorAll('.claim-quantity').forEach(input => {
        const quantity = parseInt(input.value) || 0;
        if (quantity > 0) {
            claims.push({
                line_item_id: input.dataset.itemId,
                quantity: quantity
            });
        }
    });
    
    if (claims.length === 0) {
        // Keep this alert as it requires user action
        alert('Please select items to claim');
        return;
    }
    
    const total = document.getElementById('my-total').textContent;
    if (!confirm(`You're committing to pay ${total}. Continue?`)) {
        return;
    }
    
    for (const claim of claims) {
        try {
            const response = await authenticatedJsonFetch(`/claim/${receiptSlug}/`, {
                method: 'POST',
                body: JSON.stringify(claim)
            });
            
            if (!response.ok) {
                const error = await response.json();
                // Keep error alerts as they require user attention
                alert('Error claiming item: ' + error.error);
                return;
            }
        } catch (error) {
            // Keep error alerts as they require user attention
            alert('Error claiming items: ' + error.message);
            return;
        }
    }
    
    // Just reload the page to show the updated claims
    location.reload();
}

// Polling interval in milliseconds
const POLLING_INTERVAL = 5000;
let pollingId = null;

/**
 * Briefly highlight an element to show it has been updated
 */
function highlightElement(element) {
    if (!element) return;
    element.classList.add('bg-yellow-200', 'transition-colors', 'duration-1000');
    setTimeout(() => {
        element.classList.remove('bg-yellow-200');
    }, 1000);
}

/**
 * Main function to update the entire view based on new data from the server
 */
function updateClaimsView(data) {
    // 1. Preserve user's current input
    const userInput = {};
    document.querySelectorAll('.claim-quantity').forEach(input => {
        const quantity = parseInt(input.value) || 0;
        if (quantity > 0) {
            userInput[input.dataset.itemId] = quantity;
        }
    });

    // 2. Update participant totals
    const participantsContainer = document.querySelector('.space-y-2');
    if (participantsContainer) {
        // Clear existing list
        while (participantsContainer.firstChild) {
            participantsContainer.removeChild(participantsContainer.firstChild);
        }

        // Repopulate with new data
        for (const [name, amount] of Object.entries(data.participant_totals)) {
            const div = document.createElement('div');
            div.className = 'flex justify-between items-center';
            div.innerHTML = `
                <span class="text-gray-700">${name}</span>
                <span class="font-medium tabular-nums">$${amount.toFixed(2)}</span>
            `;
            participantsContainer.appendChild(div);
        }

        if (data.total_unclaimed > 0) {
             const unclaimedDiv = document.createElement('div');
             unclaimedDiv.className = 'flex justify-between items-center text-orange-600 font-medium';
             unclaimedDiv.innerHTML = `
                <span>Not Claimed</span>
                <span class="tabular-nums">$${data.total_unclaimed.toFixed(2)}</span>
             `;
             participantsContainer.appendChild(unclaimedDiv);
        }
    }

    // 3. Update each item
    data.items_with_claims.forEach(itemData => {
        const itemContainer = document.querySelector(`.item-container[data-item-id="${itemData.item.id}"]`);
        if (!itemContainer) return;

        // Update available quantity text
        const availableQuantityText = itemContainer.querySelector('.flex.items-center.space-x-2 span:last-child');
        if (availableQuantityText && availableQuantityText.textContent !== `of ${itemData.available_quantity}`) {
            availableQuantityText.textContent = `of ${itemData.available_quantity}`;
            highlightElement(availableQuantityText);
        }

        // Update claimed by badges
        const claimsContainer = itemContainer.querySelector('.flex.flex-wrap.gap-2');
        if (claimsContainer) {
            claimsContainer.innerHTML = ''; // Clear old badges
            itemData.claims.forEach(claim => {
                const badge = document.createElement('span');
                badge.className = 'bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded';
                badge.textContent = `${claim.claimer_name} (${claim.quantity_claimed})`;
                claimsContainer.appendChild(badge);
            });
        }

        // Update input max value
        const quantityInput = itemContainer.querySelector('.claim-quantity');
        if (quantityInput) {
            if (parseInt(quantityInput.getAttribute('max')) !== itemData.available_quantity) {
                quantityInput.setAttribute('max', itemData.available_quantity);
                highlightElement(quantityInput);
            }
        }
    });

    // 4. Reconcile user input
    Object.keys(userInput).forEach(itemId => {
        const input = document.querySelector(`.claim-quantity[data-item-id="${itemId}"]`);
        if (!input) return;

        const maxQuantity = parseInt(input.getAttribute('max')) || 0;
        const userQuantity = userInput[itemId];

        if (userQuantity <= maxQuantity) {
            input.value = userQuantity;
        } else {
            input.value = 0; // Discard user input as it's no longer valid
            highlightElement(input);
        }
    });

    // 5. Update my total
    const myTotalElement = document.getElementById('my-total');
    if (myTotalElement) {
        myTotalElement.dataset.existingTotal = data.my_total.toFixed(2);
    }

    // 6. Final validation and UI updates
    updateTotal();
}


/**
 * Fetch claims data from the server
 */
async function fetchClaimsData() {
    if (!receiptSlug) return;
    try {
        const response = await authenticatedJsonFetch(`/api/receipt/${receiptSlug}/claims/`);
        if (response.ok) {
            const data = await response.json();
            updateClaimsView(data);
        }
    } catch (error) {
        console.error('Polling error:', error);
        // Stop polling on error to avoid spamming logs
        if (pollingId) {
            clearInterval(pollingId);
        }
    }
}

/**
 * Start polling for claims data
 */
function startPolling() {
    if (pollingId) {
        clearInterval(pollingId);
    }
    pollingId = setInterval(fetchClaimsData, POLLING_INTERVAL);
}


/**
 * Initialize view page on DOM ready
 */
document.addEventListener('DOMContentLoaded', () => {
    initializeViewPage();
    
    // Attach quantity input handlers
    document.querySelectorAll('.claim-quantity').forEach(input => {
        input.addEventListener('input', updateTotal);
    });
    
    // Initialize button state
    updateButtonState();
    
    // Attach confirm button handler
    const confirmBtn = document.querySelector('[data-action="confirm-claims"]');
    if (confirmBtn) {
        confirmBtn.addEventListener('click', () => confirmClaims());
    }
    
    // Attach copy share URL handlers
    document.querySelectorAll('[data-action="copy-share-url"]').forEach(btn => {
        btn.addEventListener('click', function(event) {
            const widgetId = this.dataset.widgetId || 'share-link-input';
            copyShareUrl(widgetId, event);
        });
    });

    // Start polling only if the claim interface is visible
    if (document.getElementById('view-page-data')) {
        startPolling();
    }
});

// ==========================================================================
// Module Exports for Testing
// ==========================================================================

// Export for use in Node.js/ES modules (for testing)
if (typeof module !== 'undefined' && module.exports) {
    // Import utils functions if in Node environment
    let utils = {};
    if (typeof window === 'undefined') {
        // In Node.js environment, import the utils
        const utilsModule = require('./utils.js');
        utils = utilsModule;
        // Make utils functions available globally for this module
        global.authenticatedJsonFetch = utils.authenticatedJsonFetch;
        global.copyShareUrl = utils.copyShareUrl;
    }
    
    module.exports = {
        // Initialization
        initializeViewPage,
        
        // Validation and State
        validateClaims,
        hasActiveClaims,
        updateButtonState,
        
        // Calculations
        updateTotal,
        
        // Actions
        confirmClaims,
        
        // State variables (for testing)
        _getState: () => ({ receiptSlug, receiptId, currentClaims }),
        _setState: (state) => {
            if (state.receiptSlug !== undefined) receiptSlug = state.receiptSlug;
            if (state.receiptId !== undefined) receiptId = state.receiptId;
            if (state.currentClaims !== undefined) currentClaims = state.currentClaims;
        }
    };
}