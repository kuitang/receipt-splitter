/**
 * View page specific functionality for claiming items
 * Depends on: common.js
 */

// Global variables from template (will be set by data attributes)
let receiptSlug = null;
let receiptId = null;
let currentClaims = {};
let viewerName = null; // Current user's name

// Polling state
let pollingInterval = null;
let pollingEnabled = false;
let pollingErrorCount = 0;
const POLLING_INTERVAL_MS = 5000; // 5 seconds
const MAX_POLLING_ERRORS = 3;

// CSS class constants for claim inputs
const CLAIM_INPUT_CLASSES = {
    base: 'claim-quantity w-20 px-2 py-1 border rounded',
    enabled: 'border-gray-300',
    disabled: 'border-gray-200 bg-gray-50 text-gray-600'
};

/**
 * Helper to get input classes based on disabled state
 */
function getClaimInputClasses(disabled) {
    return `${CLAIM_INPUT_CLASSES.base} ${disabled ? CLAIM_INPUT_CLASSES.disabled : CLAIM_INPUT_CLASSES.enabled}`;
}

/**
 * Initialize view page with data from DOM
 */
function initializeViewPage() {
    const container = document.getElementById('view-page-data');
    if (container) {
        receiptSlug = container.dataset.receiptSlug;
        receiptId = container.dataset.receiptId;
    }
    
    // Extract viewer name from the "Your Total" section
    const stickySection = document.querySelector('.sticky.bottom-4');
    if (stickySection) {
        const match = stickySection.textContent.match(/Your Total \(([^)]+)\)/);
        if (match) {
            viewerName = match[1];
        }
    }
}

/**
 * Start polling for claim updates
 */
function startPolling() {
    if (pollingInterval || !receiptSlug) return;
    
    pollingEnabled = true;
    pollingErrorCount = 0;
    
    // Hide any existing error banners when starting fresh
    hidePollingError();
    
    // Poll immediately and then set interval
    pollClaimStatus();
    pollingInterval = setInterval(pollClaimStatus, POLLING_INTERVAL_MS);
    
    // Pause polling when page is not visible
    document.addEventListener('visibilitychange', handleVisibilityChange);
}

/**
 * Stop polling for claim updates
 */
function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
    pollingEnabled = false;
    document.removeEventListener('visibilitychange', handleVisibilityChange);
}

/**
 * Handle page visibility changes to pause/resume polling
 */
function handleVisibilityChange() {
    if (document.hidden) {
        // Page is hidden, stop polling
        if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
        }
    } else {
        // Page is visible, resume polling if enabled
        if (pollingEnabled && !pollingInterval) {
            pollingInterval = setInterval(pollClaimStatus, POLLING_INTERVAL_MS);
            // Poll immediately when page becomes visible
            pollClaimStatus();
        }
    }
}

/**
 * Poll for claim status updates
 */
async function pollClaimStatus() {
    if (!receiptSlug) return;
    
    try {
        const response = await authenticatedJsonFetch(`/claim/${receiptSlug}/status/`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        // Debug: Log what we received from server
        console.log('[pollClaimStatus] Received data:', data);
        console.log('[pollClaimStatus] my_total from server:', data.my_total);
        
        if (data.success) {
            // Reset error count on successful poll
            pollingErrorCount = 0;
            hidePollingError();
            
            // Update UI with new data
            updateUIFromPollData(data);
        } else {
            throw new Error(data.error || 'Failed to get claim status');
        }
        
    } catch (error) {
        pollingErrorCount++;
        
        if (pollingErrorCount >= MAX_POLLING_ERRORS) {
            // Stop polling and show error after max retries
            stopPolling();
            showPollingError('Lost connection to server. Please refresh to see latest updates.');
        }
        
        console.warn('Polling error:', error.message);
    }
}

/**
 * Update UI components based on polling data
 */
function updateUIFromPollData(data) {
    // Update participant totals
    updateParticipantTotals(data.participant_totals);
    
    // Update total claimed/unclaimed amounts
    updateTotalAmounts(data.total_claimed, data.total_unclaimed);
    
    // Update user's total
    console.log('[updateUIFromPollData] About to update my_total with:', data.my_total);
    updateMyTotal(data.my_total);
    
    // Update finalization status
    updateFinalizationStatus(data.is_finalized);
    
    // Stop polling if user is finalized (no more changes possible)
    if (data.is_finalized) {
        stopPolling();
    }
    
    // Update item-level claim information 
    updateItemClaims(data.items_with_claims, data.viewer_name, data.is_finalized);
}

/**
 * Update participant totals section
 */
function updateParticipantTotals(participantTotals) {
    // Find the participants section in the DOM
    const participantsDiv = document.querySelector('.space-y-2');
    if (!participantsDiv) return;
    
    // Clear existing participant entries (except "Not Claimed" row)
    const existingEntries = participantsDiv.querySelectorAll('.flex.justify-between.items-center');
    existingEntries.forEach(entry => {
        const span = entry.querySelector('span.text-gray-700');
        if (span && !span.textContent.includes('Not Claimed')) {
            entry.remove();
        }
    });
    
    // Add updated participant entries
    participantTotals.forEach(participant => {
        const entry = document.createElement('div');
        entry.className = 'flex justify-between items-center';
        entry.innerHTML = `
            <span class="text-gray-700">${escapeHtml(participant.name)}</span>
            <span class="font-medium tabular-nums">$${participant.amount.toFixed(2)}</span>
        `;
        
        // Insert before the "Not Claimed" entry if it exists
        const notClaimedEntry = participantsDiv.querySelector('.text-orange-600');
        if (notClaimedEntry && notClaimedEntry.closest('.flex')) {
            participantsDiv.insertBefore(entry, notClaimedEntry.closest('.flex'));
        } else {
            // Insert before "No items claimed yet" message if it exists
            const noItemsMsg = participantsDiv.querySelector('.text-gray-400');
            if (noItemsMsg) {
                participantsDiv.insertBefore(entry, noItemsMsg);
            } else {
                participantsDiv.appendChild(entry);
            }
        }
    });
    
    // Handle "No items claimed yet" message
    const noItemsMsg = participantsDiv.querySelector('.text-gray-400');
    if (noItemsMsg) {
        if (participantTotals.length > 0) {
            noItemsMsg.style.display = 'none';
        } else {
            noItemsMsg.style.display = 'block';
        }
    }
}

/**
 * Update total claimed/unclaimed amounts
 */
function updateTotalAmounts(totalClaimed, totalUnclaimed) {
    // Update "Not Claimed" amount
    const notClaimedEntry = document.querySelector('.text-orange-600');
    if (notClaimedEntry) {
        const amountSpan = notClaimedEntry.querySelector('.tabular-nums');
        if (amountSpan) {
            amountSpan.textContent = `$${totalUnclaimed.toFixed(2)}`;
        }
        
        // Show/hide the "Not Claimed" row based on amount
        const parentDiv = notClaimedEntry.closest('.flex');
        if (parentDiv) {
            if (totalUnclaimed > 0) {
                parentDiv.style.display = 'flex';
            } else {
                parentDiv.style.display = 'none';
            }
        }
    }
}

/**
 * Update user's total amount (new total claims protocol)
 */
function updateMyTotal(serverTotal) {
    const myTotalElement = document.getElementById('my-total');
    if (!myTotalElement) return;
    
    // Debug logging to understand the issue
    console.log('[updateMyTotal] Server total:', serverTotal);
    console.log('[updateMyTotal] Current display:', myTotalElement.textContent);
    
    // IMPORTANT: Only update the total from server if user has finalized claims
    // Otherwise, the local calculation from inputs should be preserved
    // This prevents the regression where selecting items shows a total, but polling resets it to 0
    
    // Check if user has finalized (button would be hidden/disabled)
    const claimButton = document.getElementById('claim-button');
    const isFinalized = !claimButton || claimButton.style.display === 'none' || 
                        claimButton.parentElement.querySelector('.text-blue-600.font-medium');
    
    if (isFinalized || serverTotal > 0) {
        // User has finalized claims or server has a non-zero total - use server value
        myTotalElement.textContent = `$${serverTotal.toFixed(2)}`;
    } else {
        // User hasn't finalized yet - preserve the local calculation
        // The updateTotal() function will handle updating based on input values
        console.log('[updateMyTotal] Preserving local calculation, not overwriting with server 0');
    }
}

/**
 * Update finalization status UI
 */
function updateFinalizationStatus(isFinalized) {
    if (!isFinalized) return; // Only act on finalization, not un-finalization
    
    // Update the sticky bottom section
    const stickySection = document.querySelector('.sticky.bottom-4');
    if (stickySection) {
        // Change border color to blue
        stickySection.classList.remove('border-green-500');
        stickySection.classList.add('border-blue-500');
        
        // Update total title
        const totalTitle = stickySection.querySelector('.text-sm.text-gray-600');
        if (totalTitle && !totalTitle.textContent.includes('Finalized')) {
            totalTitle.textContent = totalTitle.textContent + ' - Finalized';
        }
        
        // Update total color to blue
        const totalAmount = stickySection.querySelector('#my-total');
        if (totalAmount) {
            totalAmount.classList.remove('text-green-600');
            totalAmount.classList.add('text-blue-600');
        }
        
        // Replace button with finalized message
        const claimButton = stickySection.querySelector('#claim-button');
        if (claimButton) {
            claimButton.outerHTML = `
                <div class="text-center">
                    <div class="text-blue-600 text-2xl mb-1">✓</div>
                    <p class="text-sm text-blue-600 font-medium">Claims Finalized</p>
                </div>
            `;
        }
        
        // Note: Finalization message is static in template, not added here
    }
    
    // Disable all claim inputs
    document.querySelectorAll('.claim-quantity').forEach(input => {
        input.readOnly = true;
        input.disabled = true;
        input.className = getClaimInputClasses(true);
    });
    
    // Update all labels from "Claim:" to "Claimed:"
    document.querySelectorAll('label.text-sm.text-gray-600').forEach(label => {
        if (label.textContent.trim() === 'Claim:') {
            label.textContent = 'Claimed:';
        }
    });
}

/**
 * Update item-level claim information
 */
function updateItemClaims(itemsWithClaims, viewerName = null, isFinalized = false) {
    itemsWithClaims.forEach(itemData => {
        const itemContainer = document.querySelector(`[data-item-id="${itemData.item_id}"]`);
        if (!itemContainer) return;
        
        // Calculate user's existing claims for this item
        let myExistingClaim = 0;
        if (viewerName) {
            const myClaim = itemData.claims.find(claim => claim.claimer_name === viewerName);
            if (myClaim) {
                myExistingClaim = myClaim.quantity_claimed;
            }
        }
        
        // Calculate total possible quantity (existing + available)
        const totalPossible = myExistingClaim + itemData.available_quantity;
        
        // Update available quantity in the claim input
        const quantityInput = itemContainer.querySelector('.claim-quantity');
        if (quantityInput) {
            const currentValue = parseInt(quantityInput.value) || 0;
            
            // Update max to include user's existing claims
            quantityInput.setAttribute('max', totalPossible);
            
            // Remove the "of X" text element if it exists (no longer needed)
            const quantityText = quantityInput.nextElementSibling;
            if (quantityText && quantityText.textContent.includes('of ')) {
                quantityText.remove();
            }
            
            // If user has no pending changes, show their existing claim
            // Only update the value if it's currently 0 (no pending user input)
            if (currentValue === 0 && myExistingClaim > 0) {
                quantityInput.value = myExistingClaim;
            }
            
            // If current value exceeds new max, reset it and show validation
            if (currentValue > totalPossible) {
                quantityInput.value = Math.min(currentValue, totalPossible);
                validateClaims();
            }
        }
        
        // Update claim section based on current state
        const claimSection = itemContainer.querySelector('.ml-4');
        if (claimSection) {
            const hasInput = claimSection.querySelector('.claim-quantity') !== null;
            const isFullyClaimed = (itemData.available_quantity === 0 && myExistingClaim === 0);
            const shouldDisable = isFinalized || isFullyClaimed;
            
            // Always show input field, just change its state
            if (!hasInput) {
                const labelText = isFinalized ? 'Claimed:' : 'Claim:';
                const disabledAttr = shouldDisable ? 'readonly disabled' : '';
                
                claimSection.innerHTML = `
                    <div class="flex items-center space-x-2">
                        <label class="text-sm text-gray-600">${labelText}</label>
                        <input type="number" 
                               class="${getClaimInputClasses(shouldDisable)}"
                               min="0"
                               max="${totalPossible}"
                               value="${myExistingClaim}"
                               data-item-id="${itemData.item_id}"
                               ${disabledAttr}>
                    </div>
                `;
                
                // Re-attach event listener for the new input (only if not disabled)
                if (!shouldDisable) {
                    const newInput = claimSection.querySelector('.claim-quantity');
                    if (newInput) {
                        newInput.addEventListener('input', updateTotal);
                    }
                }
            } else {
                // Update existing input's disabled state
                const existingInput = claimSection.querySelector('.claim-quantity');
                if (existingInput) {
                    existingInput.readOnly = shouldDisable;
                    existingInput.disabled = shouldDisable;
                    existingInput.className = getClaimInputClasses(shouldDisable);
                }
            }
        }
        
        // Update item container opacity
        const isFullyClaimed = (itemData.available_quantity === 0 && myExistingClaim === 0);
        itemContainer.classList.toggle('opacity-50', isFullyClaimed);
        
        // Update claims display
        updateItemClaimsDisplay(itemContainer, itemData.claims);
    });
    
    // Validate and update totals after all updates
    validateClaims();
    updateButtonState();
}

/**
 * Update the claims display for a specific item
 */
function updateItemClaimsDisplay(itemContainer, claims) {
    // Find existing claims section
    let claimsSection = itemContainer.querySelector('.border-t');
    
    if (claims.length === 0) {
        // Remove claims section if no claims
        if (claimsSection) {
            claimsSection.remove();
        }
        return;
    }
    
    // Create claims section if it doesn't exist
    if (!claimsSection) {
        claimsSection = document.createElement('div');
        claimsSection.className = 'mt-3 pt-3 border-t';
        itemContainer.appendChild(claimsSection);
    }
    
    // Update claims content
    claimsSection.innerHTML = `
        <p class="text-sm text-gray-600 mb-1">Claimed by:</p>
        <div class="flex flex-wrap gap-2">
            ${claims.map(claim => `
                <span class="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">
                    ${escapeHtml(claim.claimer_name)} (${claim.quantity_claimed})
                </span>
            `).join('')}
        </div>
    `;
}

/**
 * Show polling error message
 */
function showPollingError(message) {
    // Use existing error banner pattern
    const existingBanner = document.getElementById('polling-error-banner');
    if (existingBanner) {
        existingBanner.remove();
    }
    
    const banner = document.createElement('div');
    banner.id = 'polling-error-banner';
    banner.className = 'fixed top-0 left-0 right-0 z-40 bg-yellow-50 border-b-4 border-yellow-500 p-4';
    banner.innerHTML = `
        <div class="max-w-6xl mx-auto">
            <div class="flex">
                <div class="flex-shrink-0">
                    <div class="w-5 h-5 bg-yellow-400 text-white rounded-full flex items-center justify-center text-xs font-bold">!</div>
                </div>
                <div class="ml-3">
                    <h3 class="text-sm font-medium text-yellow-800">Connection Issue</h3>
                    <div class="mt-2 text-sm text-yellow-700">
                        ${escapeHtml(message)}
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertBefore(banner, document.body.firstChild);
}

/**
 * Hide polling error message
 */
function hidePollingError() {
    const banner = document.getElementById('polling-error-banner');
    if (banner) {
        banner.remove();
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
 * Update button state for total claims protocol
 */
function updateButtonState() {
    const button = document.getElementById('claim-button');
    
    if (!button) return;
    
    // With total claims protocol: enable button if user has any claims to finalize
    // Input values represent complete desired totals (not pending additions)
    const shouldEnable = hasActiveClaims();
    
    button.disabled = !shouldEnable;
}

/**
 * Update the total amount for claimed items (new total claims protocol)
 */
function updateTotal() {
    const myTotalElement = document.getElementById('my-total');
    if (!myTotalElement) return;
    
    // Calculate total from input values (inputs represent complete desired totals)
    let totalAmount = 0;
    document.querySelectorAll('.claim-quantity').forEach(input => {
        const quantity = parseInt(input.value) || 0;
        if (quantity > 0) {
            const itemId = input.dataset.itemId;
            
            // Find share element for price calculation
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
                totalAmount += sharePerItem * quantity;
            }
        }
    });
    
    // Display the calculated total (no existingTotal confusion)
    myTotalElement.textContent = `$${totalAmount.toFixed(2)}`;
    
    // Validate claims and update button state
    validateClaims();
    updateButtonState();
}

/**
 * Confirm and finalize all claims (new total claims protocol)
 */
async function confirmClaims() {
    // Validate claims first
    if (!validateClaims()) {
        alert('Please fix the highlighted items - you cannot claim more than available.');
        return;
    }
    
    // Collect ALL claims (including zero quantities for items user doesn't want)
    const claims = [];
    document.querySelectorAll('.claim-quantity').forEach(input => {
        const quantity = parseInt(input.value) || 0;
        claims.push({
            line_item_id: input.dataset.itemId,
            quantity: quantity  // Total desired quantity (may be 0)
        });
    });
    
    // Filter to only positive claims for user feedback
    const positiveClaimsCount = claims.filter(c => c.quantity > 0).length;
    if (positiveClaimsCount === 0) {
        alert('Please select items to claim');
        return;
    }
    
    const total = document.getElementById('my-total').textContent;
    if (!confirm(`You're finalizing claims for ${total}. This cannot be changed later. Continue?`)) {
        return;
    }
    
    try {
        // Submit all claims at once using new protocol
        const response = await authenticatedJsonFetch(`/claim/${receiptSlug}/`, {
            method: 'POST',
            body: JSON.stringify({ claims: claims })
        });
        
        if (!response.ok) {
            const error = await response.json();
            alert('Error finalizing claims: ' + error.error);
            return;
        }
        
        const result = await response.json();
        
        // Success - no need for additional alert, page reload will show finalized state
        
    } catch (error) {
        alert('Error finalizing claims: ' + error.message);
        return;
    }
    
    // Redirect to the view page to show finalized state
    // Using explicit redirect instead of reload to avoid any session/state issues
    if (typeof window !== 'undefined' && window.location) {
        window.location.href = `/r/${receiptSlug}/`;
    }
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
    
    // Start real-time polling for claim updates
    if (receiptSlug) {
        startPolling();
    }
    
    // Clean up polling when page unloads
    window.addEventListener('beforeunload', () => {
        stopPolling();
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
        
        // Polling functionality
        startPolling,
        stopPolling,
        pollClaimStatus,
        updateUIFromPollData,
        updateParticipantTotals,
        updateTotalAmounts,
        updateMyTotal,
        updateFinalizationStatus,
        updateItemClaims,
        updateItemClaimsDisplay,
        showPollingError,
        hidePollingError,
        
        // Helper functions
        getClaimInputClasses,
        
        // State variables (for testing)
        _getState: () => ({ 
            receiptSlug, 
            receiptId, 
            currentClaims, 
            viewerName,
            pollingEnabled, 
            pollingErrorCount 
        }),
        _setState: (state) => {
            if (state.receiptSlug !== undefined) receiptSlug = state.receiptSlug;
            if (state.receiptId !== undefined) receiptId = state.receiptId;
            if (state.currentClaims !== undefined) currentClaims = state.currentClaims;
            if (state.viewerName !== undefined) viewerName = state.viewerName;
            if (state.pollingEnabled !== undefined) pollingEnabled = state.pollingEnabled;
            if (state.pollingErrorCount !== undefined) pollingErrorCount = state.pollingErrorCount;
        }
    };
}