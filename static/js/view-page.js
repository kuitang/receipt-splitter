/**
 * View page specific functionality for claiming items
 * Depends on: common.js
 */

// Global variables from template (will be set by data attributes)
let receiptSlug = null;
let receiptId = null;
let currentClaims = {};
let viewerName = null; // Current user's name
let hasUnsavedChanges = false;

// Polling state
let pollingInterval = null;
let pollingEnabled = false;
let pollingErrorCount = 0;
const POLLING_INTERVAL_MS = 5000; // 5 seconds
const MAX_POLLING_ERRORS = 3;

// CSS class constants for claim inputs
const CLAIM_INPUT_CLASSES = {
    base: 'claim-quantity w-12 h-8 px-2 py-1 border rounded-lg text-center tabular-nums',
    enabled: 'border-gray-300 focus:ring-2 focus:ring-blue-500',
    disabled: 'border-gray-200 bg-gray-50 text-gray-600'
};

/**
 * Helper to get input classes based on disabled state
 */
function getClaimInputClasses(disabled) {
    return `${CLAIM_INPUT_CLASSES.base} ${disabled ? CLAIM_INPUT_CLASSES.disabled : CLAIM_INPUT_CLASSES.enabled}`;
}

/**
 * Update +/- button states to match input value constraints
 * @param {string} itemId - The item ID
 */
function updatePlusMinusButtonStates(itemId) {
    const input = document.querySelector(`.claim-quantity[data-item-id="${itemId}"]`);
    if (!input) return;

    const value = parseInt(input.value) || 0;
    const min = parseInt(input.getAttribute('min')) || 0;
    const max = parseInt(input.getAttribute('max')) || 0;
    const isInputDisabled = input.disabled || input.readOnly;

    const minusBtn = document.querySelector(`.claim-minus[data-item-id="${itemId}"]`);
    const plusBtn = document.querySelector(`.claim-plus[data-item-id="${itemId}"]`);

    // Update minus button
    if (minusBtn) {
        // Disable if: input disabled OR value <= min
        const shouldDisable = isInputDisabled || value <= min;
        minusBtn.disabled = shouldDisable;

        // Update styling
        if (shouldDisable) {
            minusBtn.classList.remove('bg-orange-600', 'hover:bg-orange-700');
            minusBtn.classList.add('bg-gray-300', 'cursor-not-allowed');
        } else {
            minusBtn.classList.remove('bg-gray-300', 'cursor-not-allowed');
            minusBtn.classList.add('bg-orange-600', 'hover:bg-orange-700');
        }
    }

    // Update plus button
    if (plusBtn) {
        // Disable if: input disabled OR value >= max
        const shouldDisable = isInputDisabled || value >= max;
        plusBtn.disabled = shouldDisable;

        // Update styling
        if (shouldDisable) {
            plusBtn.classList.remove('bg-green-600', 'hover:bg-green-700');
            plusBtn.classList.add('bg-gray-300', 'cursor-not-allowed');
        } else {
            plusBtn.classList.remove('bg-gray-300', 'cursor-not-allowed');
            plusBtn.classList.add('bg-green-600', 'hover:bg-green-700');
        }
    }
}

// ==========================================================================
// LocalStorage Functions
// ==========================================================================

/**
 * Get localStorage key for this receipt
 */
function getStorageKey() {
    return `claims_${receiptSlug || 'unknown'}`;
}

/**
 * Save current claims to localStorage
 */
function saveClaimsToLocalStorage() {
    if (!receiptSlug) return;

    const claims = {};
    document.querySelectorAll('.claim-quantity').forEach(input => {
        const quantity = parseInt(input.value) || 0;
        if (quantity > 0) {
            claims[input.dataset.itemId] = quantity;
        }
    });

    try {
        localStorage.setItem(getStorageKey(), JSON.stringify(claims));
        hasUnsavedChanges = Object.keys(claims).length > 0;
    } catch (e) {
        console.warn('Failed to save to localStorage:', e);
    }
}

/**
 * Restore claims from localStorage
 */
function restoreClaimsFromLocalStorage() {
    if (!receiptSlug) return false;

    try {
        const saved = localStorage.getItem(getStorageKey());
        if (saved) {
            const claims = JSON.parse(saved);
            let restoredAny = false;

            Object.entries(claims).forEach(([itemId, quantity]) => {
                const input = document.querySelector(`.claim-quantity[data-item-id="${itemId}"]`);
                if (input && parseInt(input.max) >= quantity) {
                    input.value = quantity;
                    restoredAny = true;
                }
            });

            if (restoredAny) {
                // Trigger update to recalculate totals
                updateTotal();
                hasUnsavedChanges = true;
                return true;
            }
        }
    } catch (e) {
        console.warn('Failed to restore from localStorage:', e);
    }

    return false;
}

/**
 * Clear saved claims from localStorage
 */
function clearSavedClaims() {
    if (!receiptSlug) return;

    try {
        localStorage.removeItem(getStorageKey());
        hasUnsavedChanges = false;
    } catch (e) {
        console.warn('Failed to clear localStorage:', e);
    }
}

// ==========================================================================
// Initialization Functions
// ==========================================================================

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
        let entry;
        
        // Use template to create participant entry
        const entryFragment = window.TemplateUtils.createParticipantEntry(participant.name, participant.amount);
        if (entryFragment) {
            entry = entryFragment.firstElementChild || entryFragment.querySelector('div');
        }
        
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
                // Use template to create claim input
                const claimInput = window.TemplateUtils.createClaimInput(
                    itemData.item_id,
                    totalPossible,
                    myExistingClaim,
                    shouldDisable
                );
                
                if (claimInput) {
                    claimSection.innerHTML = '';
                    claimSection.appendChild(claimInput);
                } else {
                    console.error('Failed to create claim input from template');
                }
                
                // Re-attach event listener for the new input (only if not disabled)
                if (!shouldDisable) {
                    const newInput = claimSection.querySelector('.claim-quantity');
                    if (newInput) {
                        newInput.addEventListener('input', updateTotal);
                    }
                    
                    // Attach +/- button event listeners
                    const minusBtn = claimSection.querySelector('.claim-minus');
                    const plusBtn = claimSection.querySelector('.claim-plus');
                    
                    if (minusBtn) {
                        minusBtn.addEventListener('click', () => {
                            const input = claimSection.querySelector('.claim-quantity');
                            if (input) {
                                const currentValue = parseInt(input.value) || 0;
                                const minValue = parseInt(input.getAttribute('min')) || 0;
                                if (currentValue > minValue) {
                                    input.value = currentValue - 1;
                                    updateTotal();
                                    updatePlusMinusButtonStates(itemData.item_id);
                                }
                            }
                        });
                    }
                    
                    if (plusBtn) {
                        plusBtn.addEventListener('click', () => {
                            const input = claimSection.querySelector('.claim-quantity');
                            if (input) {
                                const currentValue = parseInt(input.value) || 0;
                                const maxValue = parseInt(input.getAttribute('max')) || 0;
                                if (currentValue < maxValue) {
                                    input.value = currentValue + 1;
                                    updateTotal();
                                    updatePlusMinusButtonStates(itemData.item_id);
                                }
                            }
                        });
                    }

                    // Initialize button states for newly created input
                    updatePlusMinusButtonStates(itemData.item_id);
                }
            } else {
                // Update existing input's disabled state
                const existingInput = claimSection.querySelector('.claim-quantity');
                if (existingInput) {
                    existingInput.readOnly = shouldDisable;
                    existingInput.disabled = shouldDisable;
                    existingInput.className = getClaimInputClasses(shouldDisable);

                    // Update button states to match
                    updatePlusMinusButtonStates(itemData.item_id);
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
    
    // Update claims content using template
    const claimsDisplay = window.TemplateUtils.createClaimsDisplay(claims);
    if (claimsDisplay) {
        claimsSection.innerHTML = '';
        claimsSection.appendChild(claimsDisplay);
    }
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
    
    // Use template to create polling error banner
    const bannerFragment = window.TemplateUtils.createPollingErrorBanner(message);
    const banner = bannerFragment ? (bannerFragment.firstElementChild || bannerFragment.querySelector('#polling-error-banner')) : null;
    
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
    const warningBanner = document.getElementById('claiming-validation-warning');
    const errorDetails = document.getElementById('claiming-validation-details');
    
    if (errors.length > 0 && warningBanner && errorDetails) {
        // Clear and rebuild error list using DOM methods
        errorDetails.innerHTML = '';
        errors.forEach(error => {
            const div = document.createElement('div');
            div.textContent = `• ${error}`;
            errorDetails.appendChild(div);
        });
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

    // Save to localStorage
    saveClaimsToLocalStorage();
}

/**
 * Show adjustment banner when items are auto-adjusted
 */
function showAdjustmentBanner(adjustments) {
    const banner = document.getElementById('claiming-adjustment-warning');
    const details = document.getElementById('claiming-adjustment-details');

    if (banner && details) {
        // Find and update the title element
        const titleElement = banner.querySelector('h3');
        if (titleElement) {
            titleElement.textContent = 'Items automatically adjusted';
        }

        // Clear previous content and show adjustments
        details.innerHTML = '';

        if (adjustments.length > 0) {
            const container = document.createElement('div');
            container.className = 'space-y-1';

            adjustments.forEach(adjustment => {
                if (adjustment === '') {
                    // Empty string means add a line break
                    container.appendChild(document.createElement('br'));
                } else if (adjustment.includes('Please review')) {
                    // Special formatting for the action message
                    const div = document.createElement('div');
                    div.className = 'mt-2 font-semibold';
                    div.textContent = adjustment;
                    container.appendChild(div);
                } else {
                    // Regular adjustment item
                    const div = document.createElement('div');
                    div.textContent = `• ${adjustment}`;
                    container.appendChild(div);
                }
            });

            details.appendChild(container);
        }

        // Show banner
        banner.classList.remove('hidden');

        // Don't auto-hide for conflict adjustments - user needs to see and act
    }
}

/**
 * Update claim input fields with adjusted values
 */
function updateClaimInputs(adjustedClaims) {
    adjustedClaims.forEach(claim => {
        const input = document.querySelector(`.claim-quantity[data-item-id="${claim.line_item_id}"]`);
        if (input && input.value !== claim.quantity.toString()) {
            const originalValue = input.value;
            input.value = claim.quantity;

            // Visual feedback - flash yellow to show it changed
            input.classList.add('bg-yellow-100', 'transition-colors');
            setTimeout(() => {
                input.classList.remove('bg-yellow-100');
            }, 1000);

            // Trigger input event to update totals
            input.dispatchEvent(new Event('input', { bubbles: true }));

            // Update button states to match new value
            updatePlusMinusButtonStates(claim.line_item_id);
        }
    });
}

/**
 * Submit claims with conflict resolution (no auto-retry)
 */
async function submitClaims(claims) {
    try {
        const response = await authenticatedJsonFetch(`/claim/${receiptSlug}/`, {
            method: 'POST',
            body: JSON.stringify({ claims: claims })
        });

        if (!response.ok) {
            const error = await response.json();

            // Check if we got availability information (race condition occurred)
            if (error.availability && error.preserve_input) {
                // Adjust quantities in UI to available amounts
                const adjustments = [];
                const adjustedClaims = claims.map(claim => {
                    const avail = error.availability.find(a => a.item_id === claim.line_item_id);
                    if (avail && claim.quantity > avail.available) {
                        if (avail.available > 0) {
                            adjustments.push(`${avail.name}: reduced from ${claim.quantity} to ${avail.available}`);
                            return { ...claim, quantity: avail.available };
                        } else {
                            adjustments.push(`${avail.name}: removed (none available)`);
                            return { ...claim, quantity: 0 };
                        }
                    }
                    return claim;
                });

                // Update the input fields to show adjusted values
                updateClaimInputs(adjustedClaims);

                // Show adjustment banner with resubmit message
                if (adjustments.length > 0) {
                    const messages = [...adjustments];
                    messages.push('');
                    messages.push('Please review the adjusted quantities and click "Finalize Claims" again to submit.');
                    showAdjustmentBanner(messages);
                }
                return;
            }

            // Other errors - show simple alert
            alert('Error finalizing claims: ' + (error.error || 'Unknown error') + '\n\nIf the error persists, refresh the page.');
            return;
        }

        const result = await response.json();

        // Success - clear localStorage and redirect
        clearSavedClaims();

        if (typeof window !== 'undefined' && window.location) {
            try {
                window.location.href = `/r/${receiptSlug}/`;
            } catch (e) {
                console.log('Navigation attempted but not supported in test environment');
            }
        }

    } catch (error) {
        // Network error
        alert(`Network error: ${error.message}\n\nYour selections have been saved. If the error persists, refresh the page.`);
    }
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

    // Submit with retry logic
    await submitClaims(claims);
}

/**
 * Initialize view page on DOM ready
 */
function initializeEventListeners() {
    // Attach quantity input handlers
    document.querySelectorAll('.claim-quantity').forEach(input => {
        input.addEventListener('input', updateTotal);
    });

    // Attach +/- button handlers
    document.querySelectorAll('.claim-minus').forEach(btn => {
        btn.addEventListener('click', () => {
            if (btn.disabled) return;

            const itemId = btn.dataset.itemId;
            const input = document.querySelector(`.claim-quantity[data-item-id="${itemId}"]`);
            if (input) {
                const currentValue = parseInt(input.value) || 0;
                const minValue = parseInt(input.getAttribute('min')) || 0;
                if (currentValue > minValue) {
                    input.value = currentValue - 1;
                    updateTotal();
                    updatePlusMinusButtonStates(itemId);
                }
            }
        });
    });

    document.querySelectorAll('.claim-plus').forEach(btn => {
        btn.addEventListener('click', () => {
            if (btn.disabled) return;

            const itemId = btn.dataset.itemId;
            const input = document.querySelector(`.claim-quantity[data-item-id="${itemId}"]`);
            if (input) {
                const currentValue = parseInt(input.value) || 0;
                const maxValue = parseInt(input.getAttribute('max')) || 0;
                if (currentValue < maxValue) {
                    input.value = currentValue + 1;
                    updateTotal();
                    updatePlusMinusButtonStates(itemId);
                }
            }
        });
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

    // QR Code Modal handlers
    document.querySelectorAll('[data-action="show-qr-code"]').forEach(btn => {
        btn.addEventListener('click', function() {
            const widgetId = this.dataset.widgetId;
            const modal = document.getElementById(`qr-code-modal-${widgetId}`);
            const canvas = document.getElementById(`qr-code-modal-canvas-${widgetId}`);
            const shareUrlInput = document.getElementById(widgetId);

            if (modal && canvas && shareUrlInput && typeof QRCode !== 'undefined') {
                QRCode.toCanvas(canvas, shareUrlInput.value, function (error) {
                    if (error) console.error(error);
                    modal.classList.remove('hidden');
                });
            }
        });
    });

    document.querySelectorAll('[data-action="close-qr-code-modal"]').forEach(btn => {
        btn.addEventListener('click', function() {
            const widgetId = this.dataset.widgetId;
            const modal = document.getElementById(`qr-code-modal-${widgetId}`);
            if (modal) {
                modal.classList.add('hidden');
            }
        });
    });

    // Add dismiss handler for adjustment banner
    document.querySelectorAll('[data-dismiss-banner]').forEach(btn => {
        btn.addEventListener('click', function() {
            const bannerId = this.dataset.dismissBanner;
            const banner = document.getElementById(bannerId);
            if (banner) {
                banner.classList.add('hidden');
            }
        });
    });
}


document.addEventListener('DOMContentLoaded', () => {
    initializeViewPage();
    initializeEventListeners();

    // Restore saved claims from localStorage
    const restored = restoreClaimsFromLocalStorage();
    if (restored) {
        console.log('Restored saved claim selections from localStorage');
    }

    // Initialize button state
    updateButtonState();

    // Initialize all button states on page load
    document.querySelectorAll('.claim-quantity').forEach(input => {
        updatePlusMinusButtonStates(input.dataset.itemId);
    });

    // Start real-time polling for claim updates
    if (receiptSlug) {
        startPolling();
    }

    // Warn about unsaved changes when leaving
    window.addEventListener('beforeunload', (e) => {
        stopPolling();

        // Check if user has unsaved changes
        const hasQuantities = Array.from(document.querySelectorAll('.claim-quantity'))
            .some(input => parseInt(input.value) > 0);

        // Check if already finalized (look for finalized indicator)
        const isFinalized = document.querySelector('.text-blue-600.font-medium') ||
                          document.querySelector('#claim-button')?.style.display === 'none';

        if (hasQuantities && !isFinalized) {
            e.preventDefault();
            e.returnValue = 'You have unsaved claim selections. Are you sure you want to leave?';
            return e.returnValue;
        }
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
        initializeEventListeners,
        
        // Validation and State
        validateClaims,
        hasActiveClaims,
        updateButtonState,
        updatePlusMinusButtonStates,

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
        updateClaimInputs,
        showAdjustmentBanner,
        
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