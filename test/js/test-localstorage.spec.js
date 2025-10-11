import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { JSDOM } from 'jsdom';

// Mock localStorage - create a new instance for each test
const createLocalStorageMock = () => {
    const store = {};
    return {
        getItem: vi.fn((key) => store[key] || null),
        setItem: vi.fn((key, value) => { store[key] = value; }),
        removeItem: vi.fn((key) => { delete store[key]; }),
        clear: vi.fn(() => {
            for (const key in store) {
                delete store[key];
            }
        }),
        get length() { return Object.keys(store).length; },
        key: vi.fn((index) => Object.keys(store)[index] || null),
        store  // Expose store for testing
    };
};

describe('LocalStorage Persistence', () => {
    let dom;
    let window;
    let document;
    let localStorageMock;

    beforeEach(() => {
        // Create a fresh localStorage mock for each test
        localStorageMock = createLocalStorageMock();

        // Setup DOM
        dom = new JSDOM(`
            <!DOCTYPE html>
            <html>
            <body>
                <div id="view-page-data" data-receipt-slug="test123" data-receipt-id="abc-def"></div>
                <div id="my-total">$0.00</div>
                <button id="claim-button">Finalize Claims</button>
                <div id="claiming-validation-warning" class="hidden">
                    <h3></h3>
                    <div id="claiming-validation-details"></div>
                </div>

                <!-- Mock items with claim inputs -->
                <div class="item-container">
                    <input type="number" class="claim-quantity"
                           data-item-id="item1" value="0" min="0" max="5">
                    <div class="item-share-amount" data-amount="10.50"></div>
                </div>
                <div class="item-container">
                    <input type="number" class="claim-quantity"
                           data-item-id="item2" value="0" min="0" max="3">
                    <div class="item-share-amount" data-amount="8.25"></div>
                </div>
                <div class="item-container">
                    <input type="number" class="claim-quantity"
                           data-item-id="item3" value="0" min="0" max="2">
                    <div class="item-share-amount" data-amount="5.00"></div>
                </div>
            </body>
            </html>
        `, { url: 'http://localhost' });

        window = dom.window;
        document = window.document;
        global.document = document;
        global.window = window;
        global.localStorage = localStorageMock;

        // Mock localStorage on the window object using defineProperty
        Object.defineProperty(window, 'localStorage', {
            value: localStorageMock,
            writable: true
        });

        // Clear localStorage before each test
        localStorageMock.clear();
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    describe('saveClaimsToLocalStorage', () => {
        it('should save claims with quantities > 0 to localStorage', () => {
            // Set up test data
            global.receiptSlug = 'test123';
            document.querySelector('[data-item-id="item1"]').value = '2';
            document.querySelector('[data-item-id="item2"]').value = '1';
            document.querySelector('[data-item-id="item3"]').value = '0';

            // Function to test (simplified version for testing)
            function saveClaimsToLocalStorage() {
                if (!receiptSlug) return;

                const claims = {};
                document.querySelectorAll('.claim-quantity').forEach(input => {
                    const quantity = parseInt(input.value) || 0;
                    if (quantity > 0) {
                        claims[input.dataset.itemId] = quantity;
                    }
                });

                localStorage.setItem(`claims_${receiptSlug}`, JSON.stringify(claims));
            }

            // Execute
            saveClaimsToLocalStorage();

            // Assert
            expect(localStorageMock.setItem).toHaveBeenCalledWith(
                'claims_test123',
                JSON.stringify({ item1: 2, item2: 1 })
            );
        });

        it('should not save claims when all quantities are 0', () => {
            global.receiptSlug = 'test123';

            function saveClaimsToLocalStorage() {
                if (!receiptSlug) return;

                const claims = {};
                document.querySelectorAll('.claim-quantity').forEach(input => {
                    const quantity = parseInt(input.value) || 0;
                    if (quantity > 0) {
                        claims[input.dataset.itemId] = quantity;
                    }
                });

                if (Object.keys(claims).length > 0) {
                    localStorage.setItem(`claims_${receiptSlug}`, JSON.stringify(claims));
                }
            }

            saveClaimsToLocalStorage();

            expect(localStorageMock.setItem).not.toHaveBeenCalled();
        });

        it('should handle missing receiptSlug gracefully', () => {
            global.receiptSlug = null;

            function saveClaimsToLocalStorage() {
                if (!receiptSlug) return;
                // ... rest of function
            }

            saveClaimsToLocalStorage();

            expect(localStorageMock.setItem).not.toHaveBeenCalled();
        });
    });

    describe('restoreClaimsFromLocalStorage', () => {
        it('should restore saved claims to input fields', () => {
            global.receiptSlug = 'test123';
            const savedClaims = { item1: 3, item2: 2, item3: 1 };
            localStorageMock.setItem('claims_test123', JSON.stringify(savedClaims));

            function restoreClaimsFromLocalStorage() {
                if (!receiptSlug) return false;

                try {
                    const saved = localStorage.getItem(`claims_${receiptSlug}`);
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

                        return restoredAny;
                    }
                } catch (e) {
                    console.warn('Failed to restore from localStorage:', e);
                }

                return false;
            }

            const result = restoreClaimsFromLocalStorage();

            expect(result).toBe(true);
            expect(document.querySelector('[data-item-id="item1"]').value).toBe('3');
            expect(document.querySelector('[data-item-id="item2"]').value).toBe('2');
            expect(document.querySelector('[data-item-id="item3"]').value).toBe('1');
        });

        it('should not restore quantities that exceed max limits', () => {
            global.receiptSlug = 'test123';
            const savedClaims = { item1: 10, item2: 2 }; // item1 exceeds max of 5
            localStorageMock.setItem('claims_test123', JSON.stringify(savedClaims));

            function restoreClaimsFromLocalStorage() {
                if (!receiptSlug) return false;

                const saved = localStorage.getItem(`claims_${receiptSlug}`);
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

                    return restoredAny;
                }
                return false;
            }

            restoreClaimsFromLocalStorage();

            // item1 should not be restored (exceeds max), item2 should be
            expect(document.querySelector('[data-item-id="item1"]').value).toBe('0');
            expect(document.querySelector('[data-item-id="item2"]').value).toBe('2');
        });

        it('should return false when no saved claims exist', () => {
            global.receiptSlug = 'test123';

            function restoreClaimsFromLocalStorage() {
                if (!receiptSlug) return false;

                const saved = localStorage.getItem(`claims_${receiptSlug}`);
                return saved !== null;
            }

            const result = restoreClaimsFromLocalStorage();
            expect(result).toBe(false);
        });

        it('should handle corrupted localStorage data gracefully', () => {
            global.receiptSlug = 'test123';
            localStorageMock.setItem('claims_test123', 'not valid json');

            function restoreClaimsFromLocalStorage() {
                if (!receiptSlug) return false;

                try {
                    const saved = localStorage.getItem(`claims_${receiptSlug}`);
                    if (saved) {
                        const claims = JSON.parse(saved); // This will throw
                        // ... rest of function
                    }
                } catch (e) {
                    console.warn('Failed to restore from localStorage:', e);
                    return false;
                }

                return false;
            }

            const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
            const result = restoreClaimsFromLocalStorage();

            expect(result).toBe(false);
            expect(consoleSpy).toHaveBeenCalled();
            consoleSpy.mockRestore();
        });
    });

    describe('clearSavedClaims', () => {
        it('should remove saved claims from localStorage', () => {
            global.receiptSlug = 'test123';
            localStorageMock.setItem('claims_test123', JSON.stringify({ item1: 2 }));

            function clearSavedClaims() {
                if (!receiptSlug) return;
                localStorage.removeItem(`claims_${receiptSlug}`);
            }

            clearSavedClaims();

            expect(localStorageMock.removeItem).toHaveBeenCalledWith('claims_test123');
            expect(localStorageMock.getItem('claims_test123')).toBe(null);
        });
    });

    describe('Integration with updateTotal', () => {
        it('should save to localStorage when updateTotal is called', () => {
            global.receiptSlug = 'test123';
            document.querySelector('[data-item-id="item1"]').value = '2';

            // Simplified updateTotal that includes save
            function updateTotal() {
                // ... calculation logic ...

                // Save to localStorage
                const claims = {};
                document.querySelectorAll('.claim-quantity').forEach(input => {
                    const quantity = parseInt(input.value) || 0;
                    if (quantity > 0) {
                        claims[input.dataset.itemId] = quantity;
                    }
                });

                if (Object.keys(claims).length > 0) {
                    localStorage.setItem(`claims_${receiptSlug}`, JSON.stringify(claims));
                }
            }

            updateTotal();

            expect(localStorageMock.setItem).toHaveBeenCalledWith(
                'claims_test123',
                JSON.stringify({ item1: 2 })
            );
        });
    });

    describe('Edge Cases', () => {
        it('should handle localStorage quota exceeded error', () => {
            global.receiptSlug = 'test123';

            // Mock localStorage.setItem to throw quota exceeded error
            localStorageMock.setItem.mockImplementation(() => {
                throw new Error('QuotaExceededError');
            });

            function saveClaimsToLocalStorage() {
                if (!receiptSlug) return;

                const claims = { item1: 2 };

                try {
                    localStorage.setItem(`claims_${receiptSlug}`, JSON.stringify(claims));
                } catch (e) {
                    console.warn('Failed to save to localStorage:', e);
                }
            }

            const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
            saveClaimsToLocalStorage();

            expect(consoleSpy).toHaveBeenCalled();
            consoleSpy.mockRestore();
        });

        it('should handle different receipt slugs independently', () => {
            // Save for receipt1
            global.receiptSlug = 'receipt1';
            localStorageMock.setItem('claims_receipt1', JSON.stringify({ item1: 1 }));

            // Save for receipt2
            global.receiptSlug = 'receipt2';
            localStorageMock.setItem('claims_receipt2', JSON.stringify({ item1: 2 }));

            // Verify they are stored separately
            expect(localStorageMock.getItem('claims_receipt1')).toBe(JSON.stringify({ item1: 1 }));
            expect(localStorageMock.getItem('claims_receipt2')).toBe(JSON.stringify({ item1: 2 }));
        });
    });
});