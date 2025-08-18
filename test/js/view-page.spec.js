/**
 * Comprehensive tests for view-page.js claiming functionality
 * Tests validation, total calculation, and button state management
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  createTestDOM,
  setupMocks,
  createViewPageDOM,
  createItemContainer,
  createPollData,
  mockAuthFetch,
  mockSuccessResponse,
  mockErrorResponse,
  setClaim,
  getClaimInputs,
  assertValidationError,
  assertVisible,
  testButtonState,
  resetTestEnvironment
} from './test-helpers.js';

// Set up environment
createTestDOM();
const mocks = setupMocks();

// Import the modules
const utilsModule = await import('../../static/js/utils.js');
const viewPageModule = await import('../../static/js/view-page.js');

const {
  validateClaims,
  hasActiveClaims,
  updateButtonState,
  updateTotal,
  confirmClaims,
  initializeViewPage,
  startPolling,
  stopPolling,
  pollClaimStatus,
  updateUIFromPollData,
  updateParticipantTotals,
  updateTotalAmounts,
  updateMyTotal,
  updateItemClaims,
  updateItemClaimsDisplay,
  showPollingError,
  hidePollingError,
  _getState,
  _setState
} = viewPageModule;

const { authenticatedJsonFetch } = utilsModule;

// Helper to create a standard test DOM
function setupTestDOM(items = []) {
  if (items.length === 0) {
    items = [
      { itemId: '1', name: 'Burger', shareAmount: '15.50', max: 2 },
      { itemId: '2', name: 'Fries', shareAmount: '8.75', max: 1 },
      { itemId: '3', name: 'Drink', shareAmount: '12.25', max: 3 }
    ];
  }
  
  document.body.innerHTML = createViewPageDOM({ items, myTotal: '25.50' });
  initializeViewPage();
}

describe('View Page Claiming Functionality', () => {
  beforeEach(() => {
    resetTestEnvironment();
    setupTestDOM();
  });

  describe('Frontend Validation', () => {
    it('should prevent claiming more than available quantity', () => {
      const input1 = setClaim('1', '2'); // max is 2
      const input2 = setClaim('2', '1'); // max is 1
      
      // Valid claims
      expect(validateClaims()).toBe(true);
      expect(input1.classList.contains('border-red-500')).toBe(false);
      
      // Invalid claim - exceeds maximum
      setClaim('1', '3'); // max is 2
      
      expect(validateClaims()).toBe(false);
      assertValidationError(input1, true);
    });

    it('should clear validation errors when fixed', () => {
      const input = setClaim('1', '5'); // max is 2
      validateClaims();
      assertValidationError(input, true);
      
      // Fix the value
      setClaim('1', '2');
      validateClaims();
      assertValidationError(input, false);
    });

    it('should show validation banner with specific error messages', () => {
      const warningBanner = document.getElementById('claiming-warning');
      const errorDetails = document.getElementById('claiming-error-details');
      
      // Initially hidden
      assertVisible(warningBanner, false);
      
      // Set invalid values
      setClaim('1', '5'); // max is 2
      setClaim('2', '3'); // max is 1
      
      validateClaims();
      
      // Banner should be visible
      assertVisible(warningBanner, true);
      
      // Should show specific error messages with item names
      expect(errorDetails.innerHTML).toContain('Burger: trying to claim 5 but only 2 available');
      expect(errorDetails.innerHTML).toContain('Fries: trying to claim 3 but only 1 available');
      
      // Fix errors
      setClaim('1', '2');
      setClaim('2', '1');
      
      validateClaims();
      
      // Banner should be hidden again
      assertVisible(warningBanner, false);
    });

    it('should handle edge cases in validation', () => {
      const input = setClaim('1', '0');
      expect(validateClaims()).toBe(true);
      
      // Test negative value (should be treated as 0)
      setClaim('1', '-1');
      expect(validateClaims()).toBe(true);
      
      // Test empty value (should be treated as 0)
      setClaim('1', '');
      expect(validateClaims()).toBe(true);
      
      // Test non-numeric value
      setClaim('1', 'abc');
      expect(validateClaims()).toBe(true); // parseInt('abc') = NaN, treated as 0
    });
  });

  describe('Button State Management', () => {
    it('should disable button when no pending claims (regardless of existing total)', () => {
      // User might have existing claims but no new pending claims
      const totalElement = document.getElementById('my-total');
      totalElement.dataset.existingTotal = '25.50';
      
      // No pending claims
      getClaimInputs().forEach(input => {
        input.value = '0';
      });
      
      testButtonState({
        button: document.getElementById('claim-button'),
        shouldBeDisabled: true,
        updateStateFn: updateButtonState
      });
    });

    it('should enable button only when user has pending claims', () => {
      // Has pending claims
      setClaim('1', '1');
      
      testButtonState({
        button: document.getElementById('claim-button'),
        shouldBeDisabled: false,
        updateStateFn: updateButtonState
      });
    });

    it('should disable button when user clears all pending claims', () => {
      // User adds then removes claims
      setClaim('1', '1');
      updateButtonState();
      expect(document.getElementById('claim-button').disabled).toBe(false);
      
      // User removes the claim
      setClaim('1', '0');
      updateButtonState();
      expect(document.getElementById('claim-button').disabled).toBe(true);
    });

    it('should detect active claims correctly', () => {
      // No active claims
      getClaimInputs().forEach(input => {
        input.value = '0';
      });
      expect(hasActiveClaims()).toBe(false);
      
      // Has active claims
      setClaim('2', '1');
      expect(hasActiveClaims()).toBe(true);
      
      // Reset and test empty value
      setClaim('2', '');
      expect(hasActiveClaims()).toBe(false);
    });
  });

  describe('Claim Submission', () => {
    it('should prevent submission when validation fails', async () => {
      // Set invalid claim
      setClaim('1', '5'); // max is 2
      
      await confirmClaims();
      
      expect(mocks.alert).toHaveBeenCalledWith(
        'Please fix the highlighted items - you cannot claim more than available.'
      );
      expect(mocks.fetch).not.toHaveBeenCalled();
    });

    it('should prevent submission when no claims', async () => {
      // No claims
      getClaimInputs().forEach(input => {
        input.value = '0';
      });
      
      await confirmClaims();
      
      expect(mocks.alert).toHaveBeenCalledWith('Please select items to claim');
      expect(mocks.fetch).not.toHaveBeenCalled();
    });

    it('should submit valid claims correctly with new total protocol', async () => {
      // Set up valid claims
      setClaim('1', '2');
      setClaim('2', '1');
      
      // Mock fetch to capture the call
      const fetchCalls = [];
      mockAuthFetch((url, options) => {
        fetchCalls.push({ url, options });
        return Promise.resolve(mockSuccessResponse({ 
          finalized: true,
          claims_count: 2
        }));
      });
      
      await confirmClaims();
      
      // Should make 1 API call with all claims
      expect(fetchCalls).toHaveLength(1);
      
      // Check the new protocol format
      const requestData = JSON.parse(fetchCalls[0].options.body);
      expect(requestData).toEqual({ 
        claims: [
          { line_item_id: '1', quantity: 2 },
          { line_item_id: '2', quantity: 1 },
          { line_item_id: '3', quantity: 0 }  // All items included, even zero quantities
        ]
      });
    });

    it('should handle API errors gracefully with new protocol', async () => {
      setClaim('1', '1');
      
      mockAuthFetch(mockErrorResponse('Item not available'));
      
      await confirmClaims();
      
      // Check that error shows finalization context
      expect(mocks.alert).toHaveBeenCalledWith('Error finalizing claims: Item not available');
    });

    it('should finalize claims without success dialog', async () => {
      setClaim('1', '2');
      setClaim('2', '1');
      
      mockAuthFetch(mockSuccessResponse({ 
        finalized: true, 
        claims_count: 2 
      }));
      
      await confirmClaims();
      
      // Should not show success alert (page reload shows result)
      expect(mocks.alert).not.toHaveBeenCalled();
    });
  });

  describe('Integration Tests', () => {
    it('should work end-to-end with realistic user interaction', () => {
      const totalElement = document.getElementById('my-total');
      const warningBanner = document.getElementById('claiming-warning');
      
      // Initial state - button should be disabled when no claims
      updateButtonState();
      expect(document.getElementById('claim-button').disabled).toBe(true);
      
      // User adds more claims
      const input1 = setClaim('1', '1'); // $15.50
      updateTotal();
      expect(totalElement.textContent).toBe('$15.50');
      
      setClaim('2', '1'); // $8.75  
      updateTotal();
      expect(totalElement.textContent).toBe('$24.25');
      
      // User tries to claim too much
      setClaim('1', '3'); // max is 2
      updateTotal();
      expect(validateClaims()).toBe(false);
      assertValidationError(input1, true);
      assertVisible(warningBanner, true);
      
      // User fixes the error
      setClaim('1', '2'); // valid
      updateTotal();
      expect(validateClaims()).toBe(true);
      assertValidationError(input1, false);
      assertVisible(warningBanner, false);
      expect(totalElement.textContent).toBe('$39.75');
      
      // Button should still be enabled (has pending claims)
      expect(document.getElementById('claim-button').disabled).toBe(false);
    });

    it('should handle user with no existing claims', () => {
      // New user with no existing claims
      const totalElement = document.getElementById('my-total');
      totalElement.textContent = '$0.00';
      
      // Initial state - button should be disabled
      updateButtonState();
      expect(document.getElementById('claim-button').disabled).toBe(true);
      
      // User adds their first claim
      setClaim('1', '1');
      updateTotal();
      
      // Button should now be enabled
      expect(document.getElementById('claim-button').disabled).toBe(false);
      expect(totalElement.textContent).toBe('$15.50');
      
      // User removes their claim
      setClaim('1', '0');
      updateTotal();
      
      // Button should be disabled again
      expect(document.getElementById('claim-button').disabled).toBe(true);
      expect(totalElement.textContent).toBe('$0.00');
    });
  });

  describe('Real-time Polling Functionality', () => {
    beforeEach(() => {
      // Mock timer functions
      vi.useFakeTimers();
      
      // Reset polling state
      _setState({
        receiptSlug: 'test-receipt',
        pollingEnabled: false,
        pollingErrorCount: 0
      });
      
      // Set up more comprehensive DOM for polling tests
      const items = [
        { itemId: '1', name: 'Burger', shareAmount: '15.50', max: 2 },
        { 
          itemId: '2', 
          name: 'Fries', 
          shareAmount: '8.75', 
          fullyClaimed: true,
          claims: [{ name: 'Bob', qty: 1 }]
        }
      ];
      
      document.body.innerHTML = createViewPageDOM({ 
        items, 
        includePollingElements: true 
      });
      
      initializeViewPage();
    });

    afterEach(() => {
      vi.useRealTimers();
      stopPolling();
    });

    describe('Polling State Management', () => {
      it('should start polling with correct state', () => {
        // Mock fetch for polling endpoint
        mockAuthFetch(mockSuccessResponse(createPollData()));

        startPolling();
        
        const state = _getState();
        expect(state.pollingEnabled).toBe(true);
        expect(state.pollingErrorCount).toBe(0);
        
        // Should poll immediately
        expect(global.authenticatedJsonFetch).toHaveBeenCalledWith('/claim/test-receipt/status/');
      });

      it('should stop polling and clean up', () => {
        startPolling();
        expect(_getState().pollingEnabled).toBe(true);
        
        stopPolling();
        expect(_getState().pollingEnabled).toBe(false);
      });

      it('should handle page visibility changes', () => {
        mockAuthFetch(mockSuccessResponse(createPollData()));

        startPolling();
        
        // Simulate page becoming hidden
        Object.defineProperty(document, 'hidden', { value: true, writable: true });
        document.dispatchEvent(new Event('visibilitychange'));
        
        // Clear previous calls
        global.authenticatedJsonFetch.mockClear();
        
        // Advance timer - should not poll while hidden
        vi.advanceTimersByTime(6000);
        expect(global.authenticatedJsonFetch).not.toHaveBeenCalled();
        
        // Simulate page becoming visible
        Object.defineProperty(document, 'hidden', { value: false, writable: true });
        document.dispatchEvent(new Event('visibilitychange'));
        
        // Should resume polling immediately
        expect(global.authenticatedJsonFetch).toHaveBeenCalledWith('/claim/test-receipt/status/');
      });
    });

    describe('Error Handling', () => {
      it('should handle network errors gracefully', async () => {
        global.authenticatedJsonFetch = vi.fn().mockRejectedValue(new Error('Network error'));
        
        await pollClaimStatus();
        
        expect(_getState().pollingErrorCount).toBe(1);
      });

      it('should stop polling after max errors and show error banner', async () => {
        global.authenticatedJsonFetch = vi.fn().mockRejectedValue(new Error('Network error'));
        
        // Trigger multiple errors
        await pollClaimStatus();
        await pollClaimStatus();
        await pollClaimStatus();
        
        expect(_getState().pollingErrorCount).toBe(3);
        expect(_getState().pollingEnabled).toBe(false);
        
        // Should show error banner
        const errorBanner = document.getElementById('polling-error-banner');
        expect(errorBanner).toBeTruthy();
        expect(errorBanner.textContent).toContain('Lost connection to server');
      });

      it('should reset error count on successful poll', async () => {
        // Start with some errors
        _setState({ pollingErrorCount: 2 });
        
        mockAuthFetch(mockSuccessResponse(createPollData()));
        
        await pollClaimStatus();
        
        expect(_getState().pollingErrorCount).toBe(0);
      });

      it('should handle HTTP errors', async () => {
        global.authenticatedJsonFetch = vi.fn().mockResolvedValue({
          ok: false,
          status: 404
        });
        
        await pollClaimStatus();
        
        expect(_getState().pollingErrorCount).toBe(1);
      });
    });

    describe('UI Updates from Polling Data', () => {
      it('should update participant totals correctly', () => {
        const pollData = {
          participant_totals: [
            { name: 'Alice', amount: 25.50 },
            { name: 'Bob', amount: 18.75 }
          ]
        };
        
        updateParticipantTotals(pollData.participant_totals);
        
        // Should update existing Alice entry and add Bob
        const participantsDiv = document.querySelector('.space-y-2');
        const entries = participantsDiv.querySelectorAll('.flex.justify-between.items-center');
        
        // Find Alice and Bob entries (excluding "Not Claimed")
        const aliceEntry = Array.from(entries).find(entry => 
          entry.querySelector('.text-gray-700')?.textContent === 'Alice'
        );
        const bobEntry = Array.from(entries).find(entry => 
          entry.querySelector('.text-gray-700')?.textContent === 'Bob'
        );
        
        expect(aliceEntry).toBeTruthy();
        expect(bobEntry).toBeTruthy();
        expect(aliceEntry.querySelector('.tabular-nums').textContent).toBe('$25.50');
        expect(bobEntry.querySelector('.tabular-nums').textContent).toBe('$18.75');
      });

      it('should update total amounts correctly', () => {
        updateTotalAmounts(45.25, 5.75);
        
        const notClaimedEntry = document.querySelector('.text-orange-600');
        const amountSpan = notClaimedEntry.querySelector('.tabular-nums');
        expect(amountSpan.textContent).toBe('$5.75');
      });

      it('should hide "Not Claimed" row when amount is zero', () => {
        updateTotalAmounts(50.00, 0);
        
        const notClaimedEntry = document.querySelector('.text-orange-600');
        const parentDiv = notClaimedEntry.closest('.flex');
        expect(parentDiv.style.display).toBe('none');
      });

      it('should update user total from server (new total claims protocol)', () => {
        // User has input showing desired total
        setClaim('1', '1');
        
        // Server updates user's total (should match input calculation)
        updateMyTotal(15.50);  // Server says user has $15.50 total
        
        // Should show server total directly (input-based calculation not needed during polling)
        const totalElement = document.getElementById('my-total');
        expect(totalElement.textContent).toBe('$15.50');
      });

      it('should update item claims and availability', () => {
        const itemsData = [
          {
            item_id: '1',
            available_quantity: 1, // Was 2, now 1
            claims: [
              { claimer_name: 'Alice', quantity_claimed: 1 }
            ]
          },
          {
            item_id: '2',
            available_quantity: 0, // Still fully claimed
            claims: [
              { claimer_name: 'Bob', quantity_claimed: 1 }
            ]
          }
        ];
        
        updateItemClaims(itemsData);
        
        // Check item 1 - should update max (quantity text removed)
        const item1Input = document.querySelector('.claim-quantity[data-item-id="1"]');
        expect(item1Input.getAttribute('max')).toBe('1');
        
        // Check item 2 - should still be "Fully Claimed"
        const item2Container = document.querySelector('[data-item-id="2"]');
        const item2ClaimSection = item2Container.querySelector('.ml-4');
        expect(item2ClaimSection.textContent.trim()).toBe('Fully Claimed');
      });

      it('should restore claim input when item becomes available again', () => {
        // Item 2 starts as fully claimed
        const item2Container = document.querySelector('[data-item-id="2"]');
        expect(item2Container.querySelector('.ml-4').textContent.trim()).toBe('Fully Claimed');
        
        // Update with availability
        const itemsData = [
          {
            item_id: '2',
            available_quantity: 1, // Now available
            claims: []
          }
        ];
        
        updateItemClaims(itemsData);
        
        // Should restore claim input
        const claimInput = item2Container.querySelector('.claim-quantity');
        expect(claimInput).toBeTruthy();
        expect(claimInput.getAttribute('max')).toBe('1');
      });

      it('should use DRY abstraction for context-aware "Fully Claimed" styling', () => {
        // Test the DRY abstraction function directly
        const { generateFullyClaimedHTML } = viewPageModule;
        
        // Non-finalized context should use orange (warning color)
        const nonFinalizedHTML = generateFullyClaimedHTML(false);
        expect(nonFinalizedHTML).toBe('<span class="text-orange-600 font-semibold">Fully Claimed</span>');
        
        // Finalized context should use grey (disabled color)
        const finalizedHTML = generateFullyClaimedHTML(true);
        expect(finalizedHTML).toBe('<span class="text-gray-600 font-semibold">Fully Claimed</span>');
      });

      it('should update claims display for items', () => {
        const itemContainer = document.querySelector('[data-item-id="1"]');
        const claims = [
          { claimer_name: 'Alice', quantity_claimed: 1 },
          { claimer_name: 'Bob', quantity_claimed: 1 }
        ];
        
        updateItemClaimsDisplay(itemContainer, claims);
        
        const claimsSection = itemContainer.querySelector('.border-t');
        expect(claimsSection).toBeTruthy();
        
        const claimTags = claimsSection.querySelectorAll('.bg-blue-100');
        expect(claimTags).toHaveLength(2);
        expect(claimTags[0].textContent.trim()).toBe('Alice (1)');
        expect(claimTags[1].textContent.trim()).toBe('Bob (1)');
      });

      it('should remove claims display when no claims exist', () => {
        // Item 2 starts with claims
        const item2Container = document.querySelector('[data-item-id="2"]');
        expect(item2Container.querySelector('.border-t')).toBeTruthy();
        
        updateItemClaimsDisplay(item2Container, []);
        
        // Claims section should be removed
        expect(item2Container.querySelector('.border-t')).toBeFalsy();
      });
    });

    describe('Error Banner Management', () => {
      it('should show polling error banner', () => {
        showPollingError('Test error message');
        
        const banner = document.getElementById('polling-error-banner');
        expect(banner).toBeTruthy();
        expect(banner.textContent).toContain('Test error message');
        expect(banner.textContent).toContain('Connection Issue');
      });

      it('should hide polling error banner', () => {
        showPollingError('Test error');
        expect(document.getElementById('polling-error-banner')).toBeTruthy();
        
        hidePollingError();
        expect(document.getElementById('polling-error-banner')).toBeFalsy();
      });

      it('should replace existing error banner', () => {
        showPollingError('First error');
        const firstBanner = document.getElementById('polling-error-banner');
        
        showPollingError('Second error');
        const secondBanner = document.getElementById('polling-error-banner');
        
        expect(firstBanner).not.toBe(secondBanner);
        expect(secondBanner.textContent).toContain('Second error');
      });
    });

    describe('Integration - Full Polling Cycle', () => {
      it('should stop polling when user becomes finalized', async () => {
        mockAuthFetch(mockSuccessResponse(createPollData({ is_finalized: true })));

        startPolling();
        expect(_getState().pollingEnabled).toBe(true);
        
        // Simulate polling update that shows user is finalized
        await pollClaimStatus();
        
        // Polling should be stopped
        expect(_getState().pollingEnabled).toBe(false);
      });

      it('should handle complete polling update cycle', async () => {
        // Set up user with some pending claims
        setClaim('1', '1');
        updateTotal(); // Sets initial total display
        
        const mockPollData = createPollData({
          participant_totals: [
            { name: 'Alice', amount: 15.50 },
            { name: 'Bob', amount: 25.75 }
          ],
          total_claimed: 41.25,
          total_unclaimed: 8.75,
          my_total: 15.50,
          items_with_claims: [
            {
              item_id: '1',
              available_quantity: 1,
              claims: [
                { claimer_name: 'Bob', quantity_claimed: 1 }
              ]
            },
            {
              item_id: '2',
              available_quantity: 0,
              claims: [
                { claimer_name: 'Alice', quantity_claimed: 1 }
              ]
            }
          ]
        });
        
        mockAuthFetch(mockSuccessResponse(mockPollData));
        
        // Simulate polling update
        await pollClaimStatus();
        
        // Verify all updates
        // 1. Participant totals updated
        const participantsDiv = document.querySelector('.space-y-2');
        expect(participantsDiv.textContent).toContain('Alice');
        expect(participantsDiv.textContent).toContain('Bob');
        expect(participantsDiv.textContent).toContain('$25.75');
        
        // 2. Total unclaimed updated
        const notClaimedEntry = document.querySelector('.text-orange-600 .tabular-nums');
        expect(notClaimedEntry.textContent).toBe('$8.75');
        
        // 3. User's total updated by server (new protocol)
        const myTotalElement = document.getElementById('my-total');
        expect(myTotalElement.textContent).toBe('$15.50');
        
        // 4. Item availability updated
        const item1Input = document.querySelector('.claim-quantity[data-item-id="1"]');
        expect(item1Input.getAttribute('max')).toBe('1');
        
        // 5. Claims display updated
        const item1Container = document.querySelector('[data-item-id="1"]');
        const claimsSection = item1Container.querySelector('.border-t');
        expect(claimsSection.textContent).toContain('Bob (1)');
      });
    });
  });
});