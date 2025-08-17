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