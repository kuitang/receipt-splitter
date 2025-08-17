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
 * Update the total amount for claimed items
 */
function updateTotal() {
    let total = 0;
    document.querySelectorAll('.claim-quantity').forEach(input => {
        const quantity = parseInt(input.value) || 0;
        if (quantity > 0) {
            const itemId = input.dataset.itemId;
            const itemContainer = document.querySelector(`[data-item-id="${itemId}"]`);
            const shareElement = itemContainer.querySelector('.item-share-amount');
            if (shareElement) {
                const sharePerItem = parseFloat(shareElement.dataset.amount) || 0;
                total += sharePerItem * quantity;
            }
        }
    });
    document.getElementById('my-total').textContent = `$${total.toFixed(2)}`;
}

/**
 * Confirm and submit claims
 */
async function confirmClaims() {
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