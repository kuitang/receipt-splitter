/**
 * Tests for view-page.js claiming functionality
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  createTestDOM, setupMocks, createViewPageDOM, createPollData,
  mockAuthFetch, mockSuccessResponse, mockErrorResponse,
  setClaim, getClaimInputs, assertValidationError, assertVisible,
  testButtonState, resetTestEnvironment
} from './test-helpers.js';

createTestDOM();
const mocks = setupMocks();

const utilsModule = await import('../../static/js/utils.js');
const viewPageModule = await import('../../static/js/view-page.js');

const {
  validateClaims, hasActiveClaims, updateButtonState, updateTotal,
  confirmClaims, initializeViewPage, startPolling, stopPolling,
  pollClaimStatus, updateUIFromPollData, updateParticipantTotals,
  updateTotalAmounts, updateMyTotal, updateItemClaims,
  updateItemClaimsDisplay, showPollingError, hidePollingError,
  _getState, _setState
} = viewPageModule;

function setupTestDOM(items = []) {
  if (!items.length) {
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
      const input1 = setClaim('1', '2');
      setClaim('2', '1');
      
      expect(validateClaims()).toBe(true);
      expect(input1.classList.contains('border-red-500')).toBe(false);
      
      setClaim('1', '3');
      expect(validateClaims()).toBe(false);
      assertValidationError(input1, true);
    });

    it('should clear validation errors when fixed', () => {
      const input = setClaim('1', '5');
      validateClaims();
      assertValidationError(input, true);
      
      setClaim('1', '2');
      validateClaims();
      assertValidationError(input, false);
    });

    it('should show validation banner with specific error messages', () => {
      const warningBanner = document.getElementById('claiming-warning');
      const errorDetails = document.getElementById('claiming-error-details');
      
      assertVisible(warningBanner, false);
      
      setClaim('1', '5');
      setClaim('2', '3');
      validateClaims();
      
      assertVisible(warningBanner, true);
      expect(errorDetails.innerHTML).toContain('Burger: trying to claim 5 but only 2 available');
      expect(errorDetails.innerHTML).toContain('Fries: trying to claim 3 but only 1 available');
      
      setClaim('1', '2');
      setClaim('2', '1');
      validateClaims();
      assertVisible(warningBanner, false);
    });

    it('should handle edge cases in validation', () => {
      setClaim('1', '0');
      expect(validateClaims()).toBe(true);
      
      setClaim('1', '-1');
      expect(validateClaims()).toBe(true);
      
      setClaim('1', '');
      expect(validateClaims()).toBe(true);
      
      setClaim('1', 'abc');
      expect(validateClaims()).toBe(true);
    });
  });

  describe('Button State Management', () => {
    it('should disable button when no pending claims', () => {
      const totalElement = document.getElementById('my-total');
      totalElement.dataset.existingTotal = '25.50';
      
      getClaimInputs().forEach(input => input.value = '0');
      
      testButtonState({
        button: document.getElementById('claim-button'),
        shouldBeDisabled: true,
        updateStateFn: updateButtonState
      });
    });

    it('should enable button only when user has pending claims', () => {
      setClaim('1', '1');
      
      testButtonState({
        button: document.getElementById('claim-button'),
        shouldBeDisabled: false,
        updateStateFn: updateButtonState
      });
    });

    it('should disable button when user clears all pending claims', () => {
      setClaim('1', '1');
      updateButtonState();
      expect(document.getElementById('claim-button').disabled).toBe(false);
      
      setClaim('1', '0');
      updateButtonState();
      expect(document.getElementById('claim-button').disabled).toBe(true);
    });

    it('should detect active claims correctly', () => {
      getClaimInputs().forEach(input => input.value = '0');
      expect(hasActiveClaims()).toBe(false);
      
      setClaim('2', '1');
      expect(hasActiveClaims()).toBe(true);
      
      setClaim('2', '');
      expect(hasActiveClaims()).toBe(false);
    });
  });

  describe('Claim Submission', () => {
    it('should prevent submission when validation fails', async () => {
      setClaim('1', '5');
      await confirmClaims();
      
      expect(mocks.alert).toHaveBeenCalledWith(
        'Please fix the highlighted items - you cannot claim more than available.'
      );
      expect(mocks.fetch).not.toHaveBeenCalled();
    });

    it('should prevent submission when no claims', async () => {
      getClaimInputs().forEach(input => input.value = '0');
      await confirmClaims();
      
      expect(mocks.alert).toHaveBeenCalledWith('Please select items to claim');
      expect(mocks.fetch).not.toHaveBeenCalled();
    });

    it('should submit valid claims correctly with new total protocol', async () => {
      setClaim('1', '2');
      setClaim('2', '1');
      
      const fetchCalls = [];
      mockAuthFetch((url, options) => {
        fetchCalls.push({ url, options });
        return Promise.resolve(mockSuccessResponse({ 
          finalized: true,
          claims_count: 2
        }));
      });
      
      await confirmClaims();
      
      expect(fetchCalls).toHaveLength(1);
      const requestData = JSON.parse(fetchCalls[0].options.body);
      expect(requestData).toEqual({ 
        claims: [
          { line_item_id: '1', quantity: 2 },
          { line_item_id: '2', quantity: 1 },
          { line_item_id: '3', quantity: 0 }
        ]
      });
    });

    it('should handle API errors gracefully', async () => {
      setClaim('1', '1');
      mockAuthFetch(mockErrorResponse('Item not available'));
      await confirmClaims();
      expect(mocks.alert).toHaveBeenCalledWith('Error finalizing claims: Item not available');
    });

    it('should finalize claims without success dialog', async () => {
      setClaim('1', '2');
      setClaim('2', '1');
      mockAuthFetch(mockSuccessResponse({ finalized: true, claims_count: 2 }));
      await confirmClaims();
      expect(mocks.alert).not.toHaveBeenCalled();
    });
  });

  describe('Integration Tests', () => {
    it('should work end-to-end with realistic user interaction', () => {
      const totalElement = document.getElementById('my-total');
      const warningBanner = document.getElementById('claiming-warning');
      
      updateButtonState();
      expect(document.getElementById('claim-button').disabled).toBe(true);
      
      const input1 = setClaim('1', '1');
      updateTotal();
      expect(totalElement.textContent).toBe('$15.50');
      
      setClaim('2', '1');
      updateTotal();
      expect(totalElement.textContent).toBe('$24.25');
      
      setClaim('1', '3');
      updateTotal();
      expect(validateClaims()).toBe(false);
      assertValidationError(input1, true);
      assertVisible(warningBanner, true);
      
      setClaim('1', '2');
      updateTotal();
      expect(validateClaims()).toBe(true);
      assertValidationError(input1, false);
      assertVisible(warningBanner, false);
      expect(totalElement.textContent).toBe('$39.75');
      expect(document.getElementById('claim-button').disabled).toBe(false);
    });

    it('should handle user with no existing claims', () => {
      const totalElement = document.getElementById('my-total');
      totalElement.textContent = '$0.00';
      
      updateButtonState();
      expect(document.getElementById('claim-button').disabled).toBe(true);
      
      setClaim('1', '1');
      updateTotal();
      expect(document.getElementById('claim-button').disabled).toBe(false);
      expect(totalElement.textContent).toBe('$15.50');
      
      setClaim('1', '0');
      updateTotal();
      expect(document.getElementById('claim-button').disabled).toBe(true);
      expect(totalElement.textContent).toBe('$0.00');
    });
  });

  describe('Real-time Polling Functionality', () => {
    beforeEach(() => {
      vi.useFakeTimers();
      _setState({
        receiptSlug: 'test-receipt',
        pollingEnabled: false,
        pollingErrorCount: 0
      });
      
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
        mockAuthFetch(mockSuccessResponse(createPollData()));
        startPolling();
        
        const state = _getState();
        expect(state.pollingEnabled).toBe(true);
        expect(state.pollingErrorCount).toBe(0);
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
        
        Object.defineProperty(document, 'hidden', { value: true, writable: true });
        document.dispatchEvent(new Event('visibilitychange'));
        
        global.authenticatedJsonFetch.mockClear();
        vi.advanceTimersByTime(6000);
        expect(global.authenticatedJsonFetch).not.toHaveBeenCalled();
        
        Object.defineProperty(document, 'hidden', { value: false, writable: true });
        document.dispatchEvent(new Event('visibilitychange'));
        expect(global.authenticatedJsonFetch).toHaveBeenCalledWith('/claim/test-receipt/status/');
      });
    });

    describe('Error Handling', () => {
      it('should handle network errors gracefully', async () => {
        global.authenticatedJsonFetch = vi.fn().mockRejectedValue(new Error('Network error'));
        await pollClaimStatus();
        expect(_getState().pollingErrorCount).toBe(1);
      });

      it('should stop polling after max errors', async () => {
        global.authenticatedJsonFetch = vi.fn().mockRejectedValue(new Error('Network error'));
        
        await pollClaimStatus();
        await pollClaimStatus();
        await pollClaimStatus();
        
        expect(_getState().pollingErrorCount).toBe(3);
        expect(_getState().pollingEnabled).toBe(false);
        
        const errorBanner = document.getElementById('polling-error-banner');
        expect(errorBanner).toBeTruthy();
        expect(errorBanner.textContent).toContain('Lost connection to server');
      });

      it('should reset error count on successful poll', async () => {
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
        
        const participantsDiv = document.querySelector('.space-y-2');
        const entries = participantsDiv.querySelectorAll('.flex.justify-between.items-center');
        
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

      it('should update user total from server', () => {
        setClaim('1', '1');
        updateMyTotal(15.50);
        
        const totalElement = document.getElementById('my-total');
        expect(totalElement.textContent).toBe('$15.50');
      });

      it('should update item claims and availability', () => {
        const itemsData = [
          {
            item_id: '1',
            available_quantity: 1,
            claims: [{ claimer_name: 'Alice', quantity_claimed: 1 }]
          },
          {
            item_id: '2',
            available_quantity: 0,
            claims: [{ claimer_name: 'Bob', quantity_claimed: 1 }]
          }
        ];
        
        updateItemClaims(itemsData);
        
        const item1Input = document.querySelector('.claim-quantity[data-item-id="1"]');
        expect(item1Input.getAttribute('max')).toBe('1');
        
        const item2Container = document.querySelector('[data-item-id="2"]');
        const item2ClaimSection = item2Container.querySelector('.ml-4');
        expect(item2ClaimSection.textContent.trim()).toBe('Fully Claimed');
      });

      it('should restore claim input when item becomes available', () => {
        const item2Container = document.querySelector('[data-item-id="2"]');
        expect(item2Container.querySelector('.ml-4').textContent.trim()).toBe('Fully Claimed');
        
        const itemsData = [{
          item_id: '2',
          available_quantity: 1,
          claims: []
        }];
        
        updateItemClaims(itemsData);
        
        const claimInput = item2Container.querySelector('.claim-quantity');
        expect(claimInput).toBeTruthy();
        expect(claimInput.getAttribute('max')).toBe('1');
      });

      it('should use context-aware "Fully Claimed" styling', () => {
        const { generateFullyClaimedHTML } = viewPageModule;
        
        const nonFinalizedHTML = generateFullyClaimedHTML(false);
        expect(nonFinalizedHTML).toBe('<span class="text-orange-600 font-semibold">Fully Claimed</span>');
        
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
        const item2Container = document.querySelector('[data-item-id="2"]');
        expect(item2Container.querySelector('.border-t')).toBeTruthy();
        
        updateItemClaimsDisplay(item2Container, []);
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
        
        await pollClaimStatus();
        expect(_getState().pollingEnabled).toBe(false);
      });

      it('should handle complete polling update cycle', async () => {
        setClaim('1', '1');
        updateTotal();
        
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
              claims: [{ claimer_name: 'Bob', quantity_claimed: 1 }]
            },
            {
              item_id: '2',
              available_quantity: 0,
              claims: [{ claimer_name: 'Alice', quantity_claimed: 1 }]
            }
          ]
        });
        
        mockAuthFetch(mockSuccessResponse(mockPollData));
        await pollClaimStatus();
        
        const participantsDiv = document.querySelector('.space-y-2');
        expect(participantsDiv.textContent).toContain('Alice');
        expect(participantsDiv.textContent).toContain('Bob');
        expect(participantsDiv.textContent).toContain('$25.75');
        
        const notClaimedEntry = document.querySelector('.text-orange-600 .tabular-nums');
        expect(notClaimedEntry.textContent).toBe('$8.75');
        
        const myTotalElement = document.getElementById('my-total');
        expect(myTotalElement.textContent).toBe('$15.50');
        
        const item1Input = document.querySelector('.claim-quantity[data-item-id="1"]');
        expect(item1Input.getAttribute('max')).toBe('1');
        
        const item1Container = document.querySelector('[data-item-id="1"]');
        const claimsSection = item1Container.querySelector('.border-t');
        expect(claimsSection.textContent).toContain('Bob (1)');
      });
    });
  });
});