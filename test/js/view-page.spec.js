/**
 * Comprehensive tests for view-page.js claiming functionality
 * Tests validation, total calculation, and button state management
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { JSDOM } from 'jsdom';
import { testTemplates, setupTestTemplates } from './generated-templates.js';
import { setBodyHTML } from './test-setup.js';

// Set up DOM environment
const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
  url: 'http://localhost',
  pretendToBeVisual: true,
  resources: 'usable'
});

global.window = dom.window;
global.document = window.document;
global.navigator = window.navigator;

// Note: Navigation errors in JSDOM are expected but handled with try-catch in the code

// Mock alert and confirm
global.alert = vi.fn();
global.confirm = vi.fn(() => true);

// Mock escapeHtml function from utils
global.escapeHtml = vi.fn((text) => {
  // Simple HTML escaping for tests
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
});

// Mock fetch for claims
global.fetch = vi.fn(() => 
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve({ success: true })
  })
);

// Import template utils (this attaches to window automatically)
await import('../../static/js/template-utils.js');

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

describe('View Page Claiming Functionality', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    // Set up realistic DOM structure
    setBodyHTML(`
      <div id="view-page-data" 
           data-receipt-slug="test-receipt" 
           data-receipt-id="123">
      </div>
      
      <!-- Items container with claim inputs -->
      <div class="items-container">
        <div class="item-container" data-item-id="1">
          <h3>Burger</h3>
          <div class="item-share-amount" data-amount="15.50"></div>
          <input type="number" class="claim-quantity" 
                 data-item-id="1" min="0" max="2" value="0">
        </div>
        <div class="item-container" data-item-id="2">
          <h3>Fries</h3>
          <div class="item-share-amount" data-amount="8.75"></div>
          <input type="number" class="claim-quantity" 
                 data-item-id="2" min="0" max="1" value="0">
        </div>
        <div class="item-container" data-item-id="3">
          <h3>Drink</h3>
          <div class="item-share-amount" data-amount="12.25"></div>
          <input type="number" class="claim-quantity" 
                 data-item-id="3" min="0" max="3" value="0">
        </div>
      </div>
      
      <!-- Validation banner -->
      <div id="claiming-validation-warning" class="hidden">
        <div id="claiming-validation-details"></div>
      </div>
      
      <!-- Total display and button -->
      <p id="my-total" data-existing-total="25.50">$25.50</p>
      <button id="claim-button" data-action="confirm-claims" disabled>Claim</button>
    `);
    
    // Add the Django-generated templates to the DOM
    setupTestTemplates(document);
    
    // Initialize
    initializeViewPage();
  });

  describe('Frontend Validation', () => {
    it('should prevent claiming more than available quantity', () => {
      const input1 = document.querySelector('.claim-quantity[data-item-id="1"]');
      const input2 = document.querySelector('.claim-quantity[data-item-id="2"]');
      
      // Valid claims
      input1.value = '2'; // max is 2
      input2.value = '1'; // max is 1
      
      expect(validateClaims()).toBe(true);
      expect(input1.classList.contains('border-red-500')).toBe(false);
      
      // Invalid claim - exceeds maximum
      input1.value = '3'; // max is 2
      
      expect(validateClaims()).toBe(false);
      expect(input1.classList.contains('border-red-500')).toBe(true);
      expect(input1.classList.contains('bg-red-50')).toBe(true);
    });

    it('should clear validation errors when fixed', () => {
      const input = document.querySelector('.claim-quantity[data-item-id="1"]');
      
      // Set invalid value
      input.value = '5'; // max is 2
      validateClaims();
      expect(input.classList.contains('border-red-500')).toBe(true);
      
      // Fix the value
      input.value = '2';
      validateClaims();
      expect(input.classList.contains('border-red-500')).toBe(false);
      expect(input.classList.contains('bg-red-50')).toBe(false);
    });

    it('should show validation banner with specific error messages', () => {
      const input1 = document.querySelector('.claim-quantity[data-item-id="1"]');
      const input2 = document.querySelector('.claim-quantity[data-item-id="2"]');
      const warningBanner = document.getElementById('claiming-validation-warning');
      const errorDetails = document.getElementById('claiming-validation-details');
      
      // Initially hidden
      expect(warningBanner.classList.contains('hidden')).toBe(true);
      
      // Set invalid values
      input1.value = '5'; // max is 2
      input2.value = '3'; // max is 1
      
      validateClaims();
      
      // Banner should be visible
      expect(warningBanner.classList.contains('hidden')).toBe(false);
      
      // Should show specific error messages with item names
      expect(errorDetails.innerHTML).toContain('Burger: trying to claim 5 but only 2 available');
      expect(errorDetails.innerHTML).toContain('Fries: trying to claim 3 but only 1 available');
      
      // Fix errors
      input1.value = '2';
      input2.value = '1';
      
      validateClaims();
      
      // Banner should be hidden again
      expect(warningBanner.classList.contains('hidden')).toBe(true);
    });

    it('should handle edge cases in validation', () => {
      const input = document.querySelector('.claim-quantity[data-item-id="1"]');
      
      // Test zero value (should be valid)
      input.value = '0';
      expect(validateClaims()).toBe(true);
      
      // Test negative value (should be treated as 0)
      input.value = '-1';
      expect(validateClaims()).toBe(true); // Our validation only checks max, not min
      
      // Test empty value (should be treated as 0)
      input.value = '';
      expect(validateClaims()).toBe(true);
      
      // Test non-numeric value
      input.value = 'abc';
      expect(validateClaims()).toBe(true); // parseInt('abc') = NaN, treated as 0
    });
  });

  describe('Button State Management', () => {
    it('should disable button when no pending claims (regardless of existing total)', () => {
      // User might have existing claims but no new pending claims
      const totalElement = document.getElementById('my-total');
      totalElement.dataset.existingTotal = '25.50';
      
      // No pending claims
      document.querySelectorAll('.claim-quantity').forEach(input => {
        input.value = '0';
      });
      
      updateButtonState();
      expect(document.getElementById('claim-button').disabled).toBe(true);
    });

    it('should enable button only when user has pending claims', () => {
      // Even with no existing total, should enable if user has pending claims
      const totalElement = document.getElementById('my-total');
      
      // Has pending claims
      document.querySelector('.claim-quantity[data-item-id="1"]').value = '1';
      
      updateButtonState();
      expect(document.getElementById('claim-button').disabled).toBe(false);
    });

    it('should disable button when user clears all pending claims', () => {
      // User adds then removes claims
      document.querySelector('.claim-quantity[data-item-id="1"]').value = '1';
      updateButtonState();
      expect(document.getElementById('claim-button').disabled).toBe(false);
      
      // User removes the claim
      document.querySelector('.claim-quantity[data-item-id="1"]').value = '0';
      updateButtonState();
      expect(document.getElementById('claim-button').disabled).toBe(true);
    });

    it('should detect active claims correctly', () => {
      // No active claims
      document.querySelectorAll('.claim-quantity').forEach(input => {
        input.value = '0';
      });
      expect(hasActiveClaims()).toBe(false);
      
      // Has active claims
      document.querySelector('.claim-quantity[data-item-id="2"]').value = '1';
      expect(hasActiveClaims()).toBe(true);
      
      // Reset and test empty value
      document.querySelector('.claim-quantity[data-item-id="2"]').value = '';
      expect(hasActiveClaims()).toBe(false);
    });
  });


  describe('Claim Submission', () => {
    it('should prevent submission when validation fails', async () => {
      // Set invalid claim
      document.querySelector('.claim-quantity[data-item-id="1"]').value = '5'; // max is 2
      
      await confirmClaims();
      
      expect(global.alert).toHaveBeenCalledWith(
        'Please fix the highlighted items - you cannot claim more than available.'
      );
      expect(global.fetch).not.toHaveBeenCalled();
    });

    it('should prevent submission when no claims', async () => {
      // No claims
      document.querySelectorAll('.claim-quantity').forEach(input => {
        input.value = '0';
      });
      
      await confirmClaims();
      
      expect(global.alert).toHaveBeenCalledWith('Please select items to claim');
      expect(global.fetch).not.toHaveBeenCalled();
    });

    it('should submit valid claims correctly with new total protocol', async () => {
      // Set up valid claims
      document.querySelector('.claim-quantity[data-item-id="1"]').value = '2';
      document.querySelector('.claim-quantity[data-item-id="2"]').value = '1';
      
      // Mock fetch to capture the call
      const fetchCalls = [];
      global.authenticatedJsonFetch = vi.fn().mockImplementation((url, options) => {
        fetchCalls.push({ url, options });
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ 
            success: true, 
            finalized: true,
            claims_count: 2
          })
        });
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
      document.querySelector('.claim-quantity[data-item-id="1"]').value = '1';
      
      global.authenticatedJsonFetch = vi.fn().mockResolvedValue({
        ok: false,
        json: () => Promise.resolve({ error: 'Item not available' })
      });
      
      await confirmClaims();
      
      // Check that error shows finalization context
      expect(global.alert).toHaveBeenCalledWith('Error finalizing claims: Item not available\n\nIf the error persists, refresh the page.');
    });

    it('should finalize claims without success dialog', async () => {
      document.querySelector('.claim-quantity[data-item-id="1"]').value = '2';
      document.querySelector('.claim-quantity[data-item-id="2"]').value = '1';
      
      global.authenticatedJsonFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ 
          success: true, 
          finalized: true, 
          claims_count: 2 
        })
      });
      
      await confirmClaims();
      
      // Should not show success alert (page reload shows result)
      expect(global.alert).not.toHaveBeenCalled();
    });
  });

  describe('Integration Tests', () => {
    it('should work end-to-end with realistic user interaction', () => {
      // User starts with no claims (new total claims protocol)
      const totalElement = document.getElementById('my-total');
      const warningBanner = document.getElementById('claiming-validation-warning');
      
      // Initial state - button should be disabled when no claims
      updateButtonState();
      expect(document.getElementById('claim-button').disabled).toBe(true);
      
      // User adds more claims
      const input1 = document.querySelector('.claim-quantity[data-item-id="1"]');
      const input2 = document.querySelector('.claim-quantity[data-item-id="2"]');
      
      input1.value = '1'; // $15.50
      updateTotal();
      expect(totalElement.textContent).toBe('$15.50'); // 1 * $15.50 = $15.50
      
      input2.value = '1'; // $8.75  
      updateTotal();
      expect(totalElement.textContent).toBe('$24.25'); // 1 * $15.50 + 1 * $8.75 = $24.25
      
      // User tries to claim too much
      input1.value = '3'; // max is 2
      updateTotal();
      expect(validateClaims()).toBe(false);
      expect(input1.classList.contains('border-red-500')).toBe(true);
      expect(warningBanner.classList.contains('hidden')).toBe(false); // Banner should be visible
      
      // User fixes the error
      input1.value = '2'; // valid
      updateTotal();
      expect(validateClaims()).toBe(true);
      expect(input1.classList.contains('border-red-500')).toBe(false);
      expect(warningBanner.classList.contains('hidden')).toBe(true); // Banner should be hidden
      expect(totalElement.textContent).toBe('$39.75'); // 2 * $15.50 + 1 * $8.75 = $39.75
      
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
      document.querySelector('.claim-quantity[data-item-id="1"]').value = '1';
      updateTotal();
      
      // Button should now be enabled
      expect(document.getElementById('claim-button').disabled).toBe(false);
      expect(totalElement.textContent).toBe('$15.50');
      
      // User removes their claim
      document.querySelector('.claim-quantity[data-item-id="1"]').value = '0';
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
      setBodyHTML(`
        <div id="view-page-data" 
             data-receipt-slug="test-receipt" 
             data-receipt-id="123">
        </div>
        
        <!-- Participants section -->
        <div class="space-y-2">
          <div class="flex justify-between items-center">
            <span class="text-gray-700">Alice</span>
            <span class="font-medium tabular-nums">$15.50</span>
          </div>
          <div class="flex justify-between items-center text-orange-600 font-medium">
            <span>Not Claimed</span>
            <span class="tabular-nums">$10.25</span>
          </div>
          <p class="text-gray-400 italic">No items claimed yet</p>
        </div>
        
        <!-- Items with claims -->
        <div class="item-container" data-item-id="1">
          <h3>Burger</h3>
          <div class="item-share-amount" data-amount="15.50"></div>
          <div class="ml-4">
            <div class="flex items-center space-x-2">
              <input type="number" class="claim-quantity w-12 h-8 px-2 py-1 border border-gray-300 rounded-lg text-center tabular-nums"
                     min="0" max="2" value="0" data-item-id="1">
              <span class="text-sm text-gray-600">of 2</span>
            </div>
          </div>
        </div>
        
        <div class="item-container" data-item-id="2">
          <h3>Fries</h3>
          <div class="item-share-amount" data-amount="8.75"></div>
          <div class="ml-4">
            <span class="text-red-600 font-semibold">Fully Claimed</span>
          </div>
          <div class="mt-3 pt-3 border-t">
            <p class="text-sm text-gray-600 mb-1">Claimed by:</p>
            <div class="flex flex-wrap gap-2">
              <span class="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">Bob (1)</span>
            </div>
          </div>
        </div>
        
        <p id="my-total" data-existing-total="0.00">$0.00</p>
        <button id="claim-button" data-action="confirm-claims" disabled>Claim</button>
      `);
      
      
      initializeViewPage();
    });

    afterEach(() => {
      vi.useRealTimers();
      stopPolling();
    });

    describe('Polling State Management', () => {
      it('should start polling with correct state', () => {
        // Mock fetch for polling endpoint
        global.authenticatedJsonFetch = vi.fn().mockResolvedValue({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            participant_totals: [],
            total_claimed: 0,
            total_unclaimed: 0,
            my_total: 0,
            items_with_claims: []
          })
        });

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
        global.authenticatedJsonFetch = vi.fn().mockResolvedValue({
          ok: true,
          json: () => Promise.resolve({ success: true, participant_totals: [], total_claimed: 0, total_unclaimed: 0, my_total: 0, items_with_claims: [] })
        });

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
        
        global.authenticatedJsonFetch = vi.fn().mockResolvedValue({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            participant_totals: [],
            total_claimed: 0,
            total_unclaimed: 0,
            my_total: 0,
            items_with_claims: []
          })
        });
        
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
        document.querySelector('.claim-quantity[data-item-id="1"]').value = '1';
        
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
        
        // Check item 2 - should show disabled input
        const item2Container = document.querySelector('[data-item-id="2"]');
        const item2Input = item2Container.querySelector('.claim-quantity');
        expect(item2Input).toBeTruthy();
        expect(item2Input.disabled).toBe(true);
        expect(item2Input.className).toContain('bg-gray-50');
      });

      it('should restore claim input when item becomes available again', () => {
        // Item 2 starts as fully claimed (old HTML with "Fully Claimed" text)
        const item2Container = document.querySelector('[data-item-id="2"]');
        // Initially has "Fully Claimed" text, not input
        const initialClaimSection = item2Container.querySelector('.ml-4');
        expect(initialClaimSection.textContent).toContain('Fully Claimed');
        
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

      it('should use DRY abstraction for consistent disabled input classes', () => {
        // Test the DRY helper function
        const { getClaimInputClasses } = viewPageModule;
        
        // Enabled input should use gray-300 border
        const enabledClasses = getClaimInputClasses(false);
        expect(enabledClasses).toBe('claim-quantity w-12 h-8 px-2 py-1 border rounded-lg text-center tabular-nums border-gray-300 focus:ring-2 focus:ring-blue-500');
        
        // Disabled input should use gray-200 border and gray-50 background
        const disabledClasses = getClaimInputClasses(true);
        expect(disabledClasses).toBe('claim-quantity w-12 h-8 px-2 py-1 border rounded-lg text-center tabular-nums border-gray-200 bg-gray-50 text-gray-600');
        
        // Test in actual DOM update scenario
        setBodyHTML(`
          <div class="item-container" data-item-id="1">
            <div class="ml-4">
              <div class="flex items-center space-x-2">
                <input class="claim-quantity" data-item-id="1">
              </div>
            </div>
          </div>
        `);
        
        
        // Update item to fully claimed state
        const itemsData = [{
          item_id: '1',
          available_quantity: 0,
          claims: [{ claimer_name: 'SomeoneElse', quantity_claimed: 1 }]
        }];
        
        updateItemClaims(itemsData, 'CurrentUser', false);
        
        const input = document.querySelector('.claim-quantity[data-item-id="1"]');
        expect(input).toBeTruthy();
        expect(input.disabled).toBe(true);
        expect(input.className).toBe('claim-quantity w-12 h-8 px-2 py-1 border rounded-lg text-center tabular-nums border-gray-200 bg-gray-50 text-gray-600');
      });

      it('should maintain consistent disabled input styling between server and real-time updates', () => {
        // Start with item 1 that has availability
        const item1Container = document.querySelector('[data-item-id="1"]');
        const claimSection = item1Container.querySelector('.ml-4');
        
        // Verify initial state has enabled claim input
        const initialInput = claimSection.querySelector('.claim-quantity');
        expect(initialInput).toBeTruthy();
        expect(initialInput.disabled).toBe(false);
        
        // Update via polling to make item fully claimed
        const itemsData = [
          {
            item_id: '1',
            available_quantity: 0, // Now fully claimed
            claims: [
              { claimer_name: 'Someone', quantity_claimed: 2 }
            ]
          }
        ];
        
        updateItemClaims(itemsData, null, false); // Non-finalized user
        
        // Verify disabled input was set (no viewer means item is fully claimed for them)
        const disabledInput = claimSection.querySelector('.claim-quantity');
        expect(disabledInput).toBeTruthy();
        expect(disabledInput.disabled).toBe(true);
        expect(disabledInput.className).toContain('bg-gray-50');
        expect(disabledInput.className).toContain('text-gray-600');
        
        // Verify item container has opacity
        expect(item1Container.classList.contains('opacity-50')).toBe(true);
        
        // Test restoration maintains proper structure  
        const restorationData = [
          {
            item_id: '1',
            available_quantity: 1, // Available again
            claims: [
              { claimer_name: 'Someone', quantity_claimed: 1 } // Partial claim
            ]
          }
        ];
        
        updateItemClaims(restorationData, 'TestUser', false); // Provide viewer name
        
        // Verify claim input was restored with proper structure
        const restoredInput = claimSection.querySelector('.claim-quantity');
        expect(restoredInput).toBeTruthy();
        expect(restoredInput.getAttribute('max')).toBe('1');
        
        // Verify the input is wrapped in proper flex container
        const flexContainer = restoredInput.closest('.flex.items-center.space-x-2');
        expect(flexContainer).toBeTruthy();
        
        // Verify input is now enabled again
        expect(restoredInput.disabled).toBe(false);
        expect(restoredInput.className).not.toContain('bg-gray-50');
        
        // Verify item container opacity is removed
        expect(item1Container.classList.contains('opacity-50')).toBe(false);
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
        global.authenticatedJsonFetch = vi.fn().mockResolvedValue({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            viewer_name: 'TestUser',
            is_finalized: true,  // User is now finalized
            participant_totals: [],
            total_claimed: 0,
            total_unclaimed: 0,
            my_total: 0,
            items_with_claims: []
          })
        });

        startPolling();
        expect(_getState().pollingEnabled).toBe(true);
        
        // Simulate polling update that shows user is finalized
        await pollClaimStatus();
        
        // Polling should be stopped
        expect(_getState().pollingEnabled).toBe(false);
      });

      it('should handle complete polling update cycle', async () => {
        // Set up user with some pending claims
        document.querySelector('.claim-quantity[data-item-id="1"]').value = '1';
        updateTotal(); // Sets initial total display
        
        const mockPollData = {
          success: true,
          participant_totals: [
            { name: 'Alice', amount: 15.50 },
            { name: 'Bob', amount: 25.75 }
          ],
          total_claimed: 41.25,
          total_unclaimed: 8.75,
          my_total: 15.50, // User now has existing claims
          items_with_claims: [
            {
              item_id: '1',
              available_quantity: 1, // Reduced from 2
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
        };
        
        global.authenticatedJsonFetch = vi.fn().mockResolvedValue({
          ok: true,
          json: () => Promise.resolve(mockPollData)
        });
        
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
        expect(myTotalElement.textContent).toBe('$15.50'); // Server total directly displayed
        
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