/**
 * Template utilities for Django template integration
 * Provides functions for cloning and manipulating server-rendered templates
 */

window.TemplateUtils = {
    /**
     * Clone a template by ID
     * @param {string} templateId - The ID of the template element
     * @returns {DocumentFragment|null} The cloned template content
     */
    cloneTemplate(templateId) {
        const template = document.getElementById(templateId);
        if (!template) {
            console.warn(`Template with ID '${templateId}' not found`);
            return null;
        }
        return template.content.cloneNode(true);
    },

    /**
     * Create a new item row from template
     * @returns {DocumentFragment|null} The cloned item row
     */
    createItemRow() {
        const clone = this.cloneTemplate('item-row-template');
        if (clone) {
            // Set a temporary ID for the row
            const row = clone.querySelector('.item-row');
            if (row) {
                row.dataset.itemId = 'temp-' + Date.now();
            }
        }
        return clone;
    },

    /**
     * Create claim input controls from template
     * @param {string} itemId - The item ID
     * @param {number} maxQuantity - Maximum claimable quantity
     * @param {number} currentValue - Current claim value
     * @param {boolean} disabled - Whether controls should be disabled
     * @returns {DocumentFragment|null} The cloned claim input
     */
    createClaimInput(itemId, maxQuantity = 0, currentValue = 0, disabled = false) {
        const clone = this.cloneTemplate('claim-input-template');
        if (!clone) return null;

        // Update data attributes and values
        const minusBtn = clone.querySelector('.claim-minus');
        const plusBtn = clone.querySelector('.claim-plus');
        const input = clone.querySelector('.claim-quantity');

        if (minusBtn) {
            minusBtn.dataset.itemId = itemId;
            if (disabled) {
                minusBtn.disabled = true;
                minusBtn.classList.remove('bg-orange-600', 'hover:bg-orange-700');
                minusBtn.classList.add('bg-gray-300', 'cursor-not-allowed');
            }
        }

        if (plusBtn) {
            plusBtn.dataset.itemId = itemId;
            if (disabled) {
                plusBtn.disabled = true;
                plusBtn.classList.remove('bg-green-600', 'hover:bg-green-700');
                plusBtn.classList.add('bg-gray-300', 'cursor-not-allowed');
            }
        }

        if (input) {
            input.dataset.itemId = itemId;
            input.max = maxQuantity;
            input.value = currentValue;
            if (disabled) {
                input.readOnly = true;
                input.disabled = true;
                input.classList.remove('border-gray-300', 'focus:ring-2', 'focus:ring-blue-500');
                input.classList.add('border-gray-200', 'bg-gray-50', 'text-gray-600');
            }
        }

        return clone;
    },

    /**
     * Create claims display section from template
     * @param {Array} claims - Array of claim objects
     * @returns {DocumentFragment|null} The cloned claims display
     */
    createClaimsDisplay(claims) {
        if (!claims || claims.length === 0) return null;

        const clone = this.cloneTemplate('claims-display-template');
        if (!clone) return null;

        const container = clone.querySelector('[data-claims-container]');
        if (container) {
            // Add each claim badge
            claims.forEach(claim => {
                // Support both old and new claim formats
                const numerator = claim.quantity_numerator || claim.quantity_claimed || 0;
                const denominator = claim.quantity_denominator || 1;
                const legacyQuantity = claim.quantity_claimed || numerator;

                const badge = this.createClaimBadge(
                    claim.claimer_name,
                    legacyQuantity,
                    numerator,
                    denominator
                );
                if (badge) {
                    container.appendChild(badge);
                }
            });
        }

        return clone;
    },

    /**
     * Create a single claim badge
     * @param {string} claimerName - Name of the claimer
     * @param {number} quantity - Quantity claimed
     * @returns {Element|null} The claim badge element
     */
    createClaimBadge(claimerName, quantity, quantityNumerator = null, quantityDenominator = null) {
        const clone = this.cloneTemplate('claim-badge-template');
        if (!clone) return null;

        const nameSpan = clone.querySelector('[data-claimer-name]');
        const numeratorSpan = clone.querySelector('[data-quantity-numerator]');
        const denominatorSpan = clone.querySelector('[data-quantity-denominator]');
        const legacyQuantitySpan = clone.querySelector('[data-quantity]');

        if (nameSpan) nameSpan.textContent = claimerName;

        // Handle fractional quantity fields (new format)
        if (numeratorSpan && denominatorSpan) {
            // Use explicit numerator/denominator if provided
            const num = quantityNumerator !== null ? quantityNumerator : (quantity || 0);
            const den = quantityDenominator !== null ? quantityDenominator : 1;

            // Format the fraction for display (matching Python's format_fraction filter)
            const formattedQuantity = this.formatFraction(num, den);

            // The template has <span data-quantity-numerator></span>/<span data-quantity-denominator></span>
            // But we want to show it as a single formatted string like "2" or "½" or "2 ½"
            // So we'll put the formatted value in the numerator span and hide/remove the denominator and slash
            numeratorSpan.textContent = formattedQuantity;

            // Remove the slash and denominator span for clean display
            if (denominatorSpan.previousSibling && denominatorSpan.previousSibling.textContent === '/') {
                denominatorSpan.previousSibling.remove();
            }
            denominatorSpan.remove();
        }

        // Also support legacy single quantity field for backward compatibility
        if (legacyQuantitySpan) {
            legacyQuantitySpan.textContent = quantity;
        }

        return clone.firstElementChild;
    },

    /**
     * Format a fraction for display (matches Python's format_fraction filter)
     * @param {number} numerator
     * @param {number} denominator
     * @returns {string} Formatted fraction
     */
    formatFraction(numerator, denominator) {
        // If denominator is 1, just return the numerator
        if (denominator === 1) {
            return String(numerator);
        }

        // Simplify the fraction
        const gcd = (a, b) => b === 0 ? a : gcd(b, a % b);
        const divisor = gcd(numerator, denominator);
        const num = numerator / divisor;
        const den = denominator / divisor;

        // If simplified to whole number
        if (den === 1) {
            return String(num);
        }

        // Unicode fractions map
        const unicodeFractions = {
            '1/2': '½', '1/3': '⅓', '2/3': '⅔',
            '1/4': '¼', '3/4': '¾', '1/5': '⅕',
            '2/5': '⅖', '3/5': '⅗', '4/5': '⅘',
            '1/6': '⅙', '5/6': '⅚', '1/8': '⅛',
            '3/8': '⅜', '5/8': '⅝', '7/8': '⅞'
        };

        // Handle mixed numbers
        const integerPart = Math.floor(num / den);
        const fractionalPart = num % den;

        let display = '';
        if (integerPart > 0) {
            display += String(integerPart);
            if (fractionalPart > 0) {
                display += ' ';
            }
        }

        if (fractionalPart > 0) {
            const fractionKey = `${fractionalPart}/${den}`;
            if (unicodeFractions[fractionKey]) {
                display += unicodeFractions[fractionKey];
            } else {
                display += fractionKey;
            }
        }

        return display.trim();
    },

    /**
     * Create participant entry from template
     * @param {string} name - Participant name
     * @param {number} amount - Amount owed
     * @returns {DocumentFragment|null} The participant entry
     */
    createParticipantEntry(name, amount) {
        const clone = this.cloneTemplate('participant-entry-template');
        if (!clone) return null;

        const nameSpan = clone.querySelector('[data-participant-name]');
        const amountSpan = clone.querySelector('[data-participant-amount]');

        if (nameSpan) nameSpan.textContent = name;
        if (amountSpan) amountSpan.textContent = `$${amount.toFixed(2)}`;

        return clone;
    },

    /**
     * Create polling error banner from template
     * @param {string} message - Error message to display
     * @returns {DocumentFragment|null} The error banner
     */
    createPollingErrorBanner(message) {
        const clone = this.cloneTemplate('polling-error-template');
        if (!clone) return null;

        const messageDiv = clone.querySelector('[data-error-message]');
        if (messageDiv) messageDiv.textContent = message;

        return clone;
    },

    /**
     * Check if a template exists
     * @param {string} templateId - The template ID to check
     * @returns {boolean} Whether the template exists
     */
    hasTemplate(templateId) {
        return document.getElementById(templateId) !== null;
    },

    /**
     * Initialize template system - checks for required templates
     * @returns {boolean} Whether all required templates are available
     */
    initialize() {
        const requiredTemplates = [
            'item-row-template',
            'claim-input-template',
            'claims-display-template',
            'claim-badge-template',
            'participant-entry-template'
        ];

        const missingTemplates = requiredTemplates.filter(id => !this.hasTemplate(id));
        
        if (missingTemplates.length > 0) {
            console.warn('Missing templates:', missingTemplates);
            console.warn('Make sure to include js_templates.html in your page');
            return false;
        }

        return true;
    }
};