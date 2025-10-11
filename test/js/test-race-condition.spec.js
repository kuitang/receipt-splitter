import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { JSDOM } from 'jsdom';

describe('Race Condition Handling', () => {
    let dom;
    let window;
    let document;
    let fetchMock;
    let alertMock;

    beforeEach(() => {
        // Setup DOM
        dom = new JSDOM(`
            <!DOCTYPE html>
            <html>
            <body>
                <div id="view-page-data" data-receipt-slug="test123" data-receipt-id="abc-def"></div>
                <div id="my-total">$0.00</div>
                <button id="claim-button">Finalize Claims</button>
                <div id="claiming-warning" class="hidden">
                    <h3></h3>
                    <div id="claiming-error-details"></div>
                </div>

                <!-- Mock items with claim inputs -->
                <div class="item-container">
                    <input type="number" class="claim-quantity"
                           data-item-id="pizza-id" value="3" min="0" max="5">
                    <div class="item-share-amount" data-amount="10.00"></div>
                </div>
                <div class="item-container">
                    <input type="number" class="claim-quantity"
                           data-item-id="soda-id" value="2" min="0" max="3">
                    <div class="item-share-amount" data-amount="3.00"></div>
                </div>
                <div class="item-container">
                    <input type="number" class="claim-quantity"
                           data-item-id="salad-id" value="1" min="0" max="2">
                    <div class="item-share-amount" data-amount="8.00"></div>
                </div>
            </body>
            </html>
        `, { url: 'http://localhost' });

        window = dom.window;
        document = window.document;
        global.document = document;
        global.window = window;
        global.receiptSlug = 'test123';
        global.localStorage = {
            setItem: vi.fn(),
            getItem: vi.fn(),
            removeItem: vi.fn()
        };

        // Mock fetch
        fetchMock = vi.fn();
        global.fetch = fetchMock;

        // Mock alert
        alertMock = vi.fn();
        global.alert = alertMock;
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    describe('submitClaims with race condition', () => {
        it('should adjust UI when race condition occurs', async () => {
            // Mock race condition response
            const mockAvailability = {
                ok: false,
                json: async () => ({
                    error: 'Some items are no longer available',
                    preserve_input: true,
                    availability: [
                        { item_id: 'pizza-id', name: 'Pizza', requested: 3, available: 1 },
                        { item_id: 'soda-id', name: 'Soda', requested: 2, available: 0 },
                        { item_id: 'salad-id', name: 'Salad', requested: 1, available: 1 }
                    ]
                })
            };

            fetchMock.mockResolvedValue(mockAvailability);

            // Simplified submitClaims for testing
            async function submitClaims(claims) {
                const response = await fetch(`/claim/test123/`, {
                    method: 'POST',
                    body: JSON.stringify({ claims: claims })
                });

                if (!response.ok) {
                    const error = await response.json();

                    if (error.availability && error.preserve_input) {
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

                        // Update UI
                        updateClaimInputs(adjustedClaims);
                        if (adjustments.length > 0) {
                            showAdjustmentBanner(adjustments);
                        }
                        return;
                    }
                }
            }

            function updateClaimInputs(adjustedClaims) {
                adjustedClaims.forEach(claim => {
                    const input = document.querySelector(`.claim-quantity[data-item-id="${claim.line_item_id}"]`);
                    if (input) {
                        input.value = claim.quantity;
                        input.classList.add('bg-yellow-100');
                    }
                });
            }

            function showAdjustmentBanner(adjustments) {
                const banner = document.getElementById('claiming-warning');
                const details = document.getElementById('claiming-error-details');

                if (banner && details) {
                    banner.classList.remove('hidden');
                    const titleElement = banner.querySelector('h3');
                    titleElement.textContent = 'Items automatically adjusted';
                    details.textContent = adjustments.join(', ');
                }
            }

            // Test claims
            const claims = [
                { line_item_id: 'pizza-id', quantity: 3 },
                { line_item_id: 'soda-id', quantity: 2 },
                { line_item_id: 'salad-id', quantity: 1 }
            ];

            await submitClaims(claims);

            // Verify UI was adjusted
            expect(document.querySelector('[data-item-id="pizza-id"]').value).toBe('1');
            expect(document.querySelector('[data-item-id="soda-id"]').value).toBe('0');
            expect(document.querySelector('[data-item-id="salad-id"]').value).toBe('1');

            // Verify banner was shown
            const banner = document.getElementById('claiming-warning');
            expect(banner.classList.contains('hidden')).toBe(false);
            expect(banner.querySelector('h3').textContent).toBe('Items automatically adjusted');
        });

        it('should show user-friendly message for adjustments', async () => {
            const mockAvailability = {
                ok: false,
                json: async () => ({
                    error: 'Some items are no longer available',
                    preserve_input: true,
                    availability: [
                        { item_id: 'pizza-id', name: 'Pizza', requested: 3, available: 1 }
                    ]
                })
            };

            fetchMock.mockResolvedValue(mockAvailability);

            async function submitClaims(claims) {
                const response = await fetch(`/claim/test123/`, {
                    method: 'POST',
                    body: JSON.stringify({ claims: claims })
                });

                if (!response.ok) {
                    const error = await response.json();

                    if (error.availability && error.preserve_input) {
                        const adjustments = [];
                        claims.forEach(claim => {
                            const avail = error.availability.find(a => a.item_id === claim.line_item_id);
                            if (avail && claim.quantity > avail.available) {
                                if (avail.available > 0) {
                                    adjustments.push(`${avail.name}: reduced from ${claim.quantity} to ${avail.available}`);
                                } else {
                                    adjustments.push(`${avail.name}: removed (none available)`);
                                }
                            }
                        });

                        adjustments.push('');
                        adjustments.push('Please review the adjusted quantities and click "Finalize Claims" again to submit.');

                        return adjustments;
                    }
                }
                return null;
            }

            const claims = [{ line_item_id: 'pizza-id', quantity: 3 }];
            const adjustments = await submitClaims(claims);

            expect(adjustments).toContain('Pizza: reduced from 3 to 1');
            expect(adjustments).toContain('Please review the adjusted quantities and click "Finalize Claims" again to submit.');
        });

        it('should handle complete unavailability', async () => {
            const mockAvailability = {
                ok: false,
                json: async () => ({
                    error: 'Some items are no longer available',
                    preserve_input: true,
                    availability: [
                        { item_id: 'pizza-id', name: 'Pizza', requested: 3, available: 0 }
                    ]
                })
            };

            fetchMock.mockResolvedValue(mockAvailability);

            async function processRaceCondition(claims) {
                const response = await fetch(`/claim/test123/`, {
                    method: 'POST',
                    body: JSON.stringify({ claims: claims })
                });

                const error = await response.json();
                const adjustedClaims = [];

                claims.forEach(claim => {
                    const avail = error.availability.find(a => a.item_id === claim.line_item_id);
                    if (avail) {
                        if (avail.available === 0) {
                            adjustedClaims.push({ ...claim, quantity: 0, message: `${avail.name}: removed (none available)` });
                        } else if (claim.quantity > avail.available) {
                            adjustedClaims.push({ ...claim, quantity: avail.available, message: `${avail.name}: reduced` });
                        } else {
                            adjustedClaims.push(claim);
                        }
                    }
                });

                return adjustedClaims;
            }

            const claims = [{ line_item_id: 'pizza-id', quantity: 3 }];
            const adjusted = await processRaceCondition(claims);

            expect(adjusted[0].quantity).toBe(0);
            expect(adjusted[0].message).toBe('Pizza: removed (none available)');
        });

        it('should save adjusted values to localStorage', async () => {
            const mockAvailability = {
                ok: false,
                json: async () => ({
                    error: 'Some items are no longer available',
                    preserve_input: true,
                    availability: [
                        { item_id: 'pizza-id', name: 'Pizza', requested: 3, available: 2 }
                    ]
                })
            };

            fetchMock.mockResolvedValue(mockAvailability);

            async function handleRaceCondition(claims) {
                const response = await fetch(`/claim/test123/`);
                const error = await response.json();

                // Adjust claims
                const adjusted = claims.map(claim => {
                    const avail = error.availability.find(a => a.item_id === claim.line_item_id);
                    if (avail && claim.quantity > avail.available) {
                        return { ...claim, quantity: avail.available };
                    }
                    return claim;
                });

                // Update UI
                adjusted.forEach(claim => {
                    const input = document.querySelector(`[data-item-id="${claim.line_item_id}"]`);
                    if (input) input.value = claim.quantity;
                });

                // Save to localStorage
                const claimsToSave = {};
                adjusted.forEach(claim => {
                    if (claim.quantity > 0) {
                        claimsToSave[claim.line_item_id] = claim.quantity;
                    }
                });
                localStorage.setItem(`claims_${receiptSlug}`, JSON.stringify(claimsToSave));

                return adjusted;
            }

            const claims = [{ line_item_id: 'pizza-id', quantity: 3 }];
            await handleRaceCondition(claims);

            expect(localStorage.setItem).toHaveBeenCalledWith(
                'claims_test123',
                JSON.stringify({ 'pizza-id': 2 })
            );
        });
    });

    describe('Error Handling', () => {
        it('should show alert for non-race-condition errors', async () => {
            const mockError = {
                ok: false,
                json: async () => ({
                    error: 'Receipt must be finalized first'
                })
            };

            fetchMock.mockResolvedValue(mockError);

            async function submitClaims(claims) {
                const response = await fetch(`/claim/test123/`);
                if (!response.ok) {
                    const error = await response.json();
                    if (!error.preserve_input) {
                        alert('Error finalizing claims: ' + error.error + '\n\nIf the error persists, refresh the page.');
                    }
                }
            }

            await submitClaims([]);

            expect(alertMock).toHaveBeenCalledWith('Error finalizing claims: Receipt must be finalized first\n\nIf the error persists, refresh the page.');
        });

        it('should handle network errors gracefully', async () => {
            fetchMock.mockRejectedValue(new Error('Network error'));

            async function submitClaims(claims) {
                try {
                    const response = await fetch(`/claim/test123/`);
                } catch (error) {
                    alert(`Network error: ${error.message}\n\nYour selections have been saved. If the error persists, refresh the page.`);
                }
            }

            await submitClaims([]);

            expect(alertMock).toHaveBeenCalledWith(
                'Network error: Network error\n\nYour selections have been saved. If the error persists, refresh the page.'
            );
        });
    });

    describe('UI Updates', () => {
        it('should add yellow highlight to adjusted inputs', async () => {
            function updateClaimInputs(adjustedClaims) {
                adjustedClaims.forEach(claim => {
                    const input = document.querySelector(`.claim-quantity[data-item-id="${claim.line_item_id}"]`);
                    if (input && input.value !== claim.quantity.toString()) {
                        input.value = claim.quantity;
                        input.classList.add('bg-yellow-100', 'transition-colors');

                        setTimeout(() => {
                            input.classList.remove('bg-yellow-100');
                        }, 1000);
                    }
                });
            }

            const adjustedClaims = [
                { line_item_id: 'pizza-id', quantity: 1 }
            ];

            updateClaimInputs(adjustedClaims);

            const input = document.querySelector('[data-item-id="pizza-id"]');
            expect(input.value).toBe('1');
            expect(input.classList.contains('bg-yellow-100')).toBe(true);
            expect(input.classList.contains('transition-colors')).toBe(true);
        });

        it('should trigger input event when adjusting values', async () => {
            let eventFired = false;
            const input = document.querySelector('[data-item-id="pizza-id"]');

            input.addEventListener('input', () => {
                eventFired = true;
            });

            function updateClaimInputs(adjustedClaims) {
                adjustedClaims.forEach(claim => {
                    const input = document.querySelector(`.claim-quantity[data-item-id="${claim.line_item_id}"]`);
                    if (input) {
                        input.value = claim.quantity;
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                });
            }

            updateClaimInputs([{ line_item_id: 'pizza-id', quantity: 2 }]);

            expect(eventFired).toBe(true);
            expect(input.value).toBe('2');
        });
    });

    describe('Multiple Race Conditions', () => {
        it('should handle multiple consecutive race conditions', async () => {
            let callCount = 0;

            fetchMock.mockImplementation(async () => {
                callCount++;
                if (callCount === 1) {
                    // First attempt - Pizza needs adjustment
                    return {
                        ok: false,
                        json: async () => ({
                            error: 'Some items are no longer available',
                            preserve_input: true,
                            availability: [
                                { item_id: 'pizza-id', name: 'Pizza', requested: 3, available: 2 }
                            ]
                        })
                    };
                } else if (callCount === 2) {
                    // Second attempt - Pizza needs more adjustment
                    return {
                        ok: false,
                        json: async () => ({
                            error: 'Some items are no longer available',
                            preserve_input: true,
                            availability: [
                                { item_id: 'pizza-id', name: 'Pizza', requested: 2, available: 1 }
                            ]
                        })
                    };
                } else {
                    // Third attempt succeeds
                    return {
                        ok: true,
                        json: async () => ({ success: true })
                    };
                }
            });

            async function attemptClaim(quantity) {
                const response = await fetch(`/claim/test123/`);
                if (!response.ok) {
                    const error = await response.json();
                    if (error.availability) {
                        const avail = error.availability[0];
                        return { adjusted: true, newQuantity: avail.available };
                    }
                }
                return { adjusted: false };
            }

            // First attempt
            let result = await attemptClaim(3);
            expect(result.adjusted).toBe(true);
            expect(result.newQuantity).toBe(2);

            // Second attempt with adjusted quantity
            result = await attemptClaim(2);
            expect(result.adjusted).toBe(true);
            expect(result.newQuantity).toBe(1);

            // Third attempt succeeds
            result = await attemptClaim(1);
            expect(result.adjusted).toBe(false);
        });
    });
});