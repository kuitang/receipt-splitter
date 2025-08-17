/**
 * Comprehensive tests for view-page.js claiming functionality
 * Tests validation, total calculation, and button state management
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { JSDOM } from 'jsdom';

// Set up DOM environment
const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
  url: 'http://localhost',
  pretendToBeVisual: true,
  resources: 'usable'
});

global.window = dom.window;
global.document = window.document;
global.navigator = window.navigator;

// Mock alert and confirm
global.alert = vi.fn();
global.confirm = vi.fn(() => true);

// Mock fetch for claims
global.fetch = vi.fn(() => 
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve({ success: true })
  })
);

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
  _getState,
  _setState
} = viewPageModule;

const { authenticatedJsonFetch } = utilsModule;

describe('View Page Claiming Functionality', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    // Set up realistic DOM structure
    document.body.innerHTML = `
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
      <div id="claiming-warning" class="hidden">
        <div id="claiming-error-details"></div>
      </div>
      
      <!-- Total display and button -->
      <p id="my-total" data-existing-total="25.50">$25.50</p>
      <button id="claim-button" data-action="confirm-claims" disabled>Claim</button>
    `;
    
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
      const warningBanner = document.getElementById('claiming-warning');
      const errorDetails = document.getElementById('claiming-error-details');
      
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
      totalElement.dataset.existingTotal = '0.00';
      
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

  describe('Total Calculation Bug Fix', () => {
    it('should show cumulative total including existing claims', () => {
      const totalElement = document.getElementById('my-total');
      totalElement.dataset.existingTotal = '25.50'; // User already claimed $25.50
      
      // User adds new claims
      document.querySelector('.claim-quantity[data-item-id="1"]').value = '2'; // 2 × $15.50 = $31.00
      document.querySelector('.claim-quantity[data-item-id="2"]').value = '1'; // 1 × $8.75 = $8.75
      
      updateTotal();
      
      // Should show existing ($25.50) + new claims ($39.75) = $65.25
      expect(totalElement.textContent).toBe('$65.25');
    });

    it('should handle zero existing total correctly', () => {
      const totalElement = document.getElementById('my-total');
      totalElement.dataset.existingTotal = '0.00'; // New user
      
      // User makes first claims
      document.querySelector('.claim-quantity[data-item-id="1"]').value = '1'; // 1 × $15.50 = $15.50
      
      updateTotal();
      
      // Should show just the new claims
      expect(totalElement.textContent).toBe('$15.50');
    });

    it('should not zero out when existing total exists', () => {
      const totalElement = document.getElementById('my-total');
      totalElement.dataset.existingTotal = '50.25'; // User has significant existing claims
      
      // User makes small additional claim
      document.querySelector('.claim-quantity[data-item-id="2"]').value = '1'; // 1 × $8.75 = $8.75
      
      updateTotal();
      
      // Should preserve existing total
      expect(totalElement.textContent).toBe('$59.00');
      
      // User removes their pending claim
      document.querySelector('.claim-quantity[data-item-id="2"]').value = '0';
      
      updateTotal();
      
      // Should go back to just existing total, not zero
      expect(totalElement.textContent).toBe('$50.25');
    });

    it('should handle floating point precision correctly', () => {
      const totalElement = document.getElementById('my-total');
      totalElement.dataset.existingTotal = '10.01';
      
      // Set up item with price that causes floating point issues
      const itemContainer = document.querySelector('.claim-quantity[data-item-id="1"]').parentElement;
      const shareElement = itemContainer.querySelector('.item-share-amount');
      shareElement.dataset.amount = '0.1'; // Classic JS floating point issue
      
      document.querySelector('.claim-quantity[data-item-id="1"]').value = '3'; // 3 × $0.1 = $0.3 (but JS might give 0.30000000000000004)
      
      updateTotal();
      
      // Should display correctly rounded total
      expect(totalElement.textContent).toBe('$10.31');
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

    it('should submit valid claims correctly', async () => {
      // Set up valid claims
      document.querySelector('.claim-quantity[data-item-id="1"]').value = '2';
      document.querySelector('.claim-quantity[data-item-id="2"]').value = '1';
      
      // Mock fetch to capture the calls
      const fetchCalls = [];
      global.authenticatedJsonFetch = vi.fn().mockImplementation((url, options) => {
        fetchCalls.push({ url, options });
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ success: true })
        });
      });
      
      await confirmClaims();
      
      // Should make 2 API calls
      expect(fetchCalls).toHaveLength(2);
      
      // Check the claim data
      const claim1 = JSON.parse(fetchCalls[0].options.body);
      const claim2 = JSON.parse(fetchCalls[1].options.body);
      
      expect(claim1).toEqual({ line_item_id: '1', quantity: 2 });
      expect(claim2).toEqual({ line_item_id: '2', quantity: 1 });
    });

    it('should handle API errors gracefully', async () => {
      document.querySelector('.claim-quantity[data-item-id="1"]').value = '1';
      
      global.authenticatedJsonFetch = vi.fn().mockResolvedValue({
        ok: false,
        json: () => Promise.resolve({ error: 'Item not available' })
      });
      
      await confirmClaims();
      
      expect(global.alert).toHaveBeenCalledWith('Error claiming item: Item not available');
    });
  });

  describe('Integration Tests', () => {
    it('should work end-to-end with realistic user interaction', () => {
      // User starts with existing claims
      const totalElement = document.getElementById('my-total');
      const warningBanner = document.getElementById('claiming-warning');
      totalElement.dataset.existingTotal = '15.75';
      
      // Initial state - button should be disabled until user makes new claims
      updateButtonState();
      expect(document.getElementById('claim-button').disabled).toBe(true);
      
      // User adds more claims
      const input1 = document.querySelector('.claim-quantity[data-item-id="1"]');
      const input2 = document.querySelector('.claim-quantity[data-item-id="2"]');
      
      input1.value = '1'; // $15.50
      updateTotal();
      expect(totalElement.textContent).toBe('$31.25'); // $15.75 + $15.50
      
      input2.value = '1'; // $8.75
      updateTotal();
      expect(totalElement.textContent).toBe('$40.00'); // $15.75 + $15.50 + $8.75
      
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
      expect(totalElement.textContent).toBe('$55.50'); // $15.75 + $31.00 + $8.75
      
      // Button should still be enabled (has pending claims)
      expect(document.getElementById('claim-button').disabled).toBe(false);
    });

    it('should handle user with no existing claims', () => {
      // New user with no existing claims
      const totalElement = document.getElementById('my-total');
      totalElement.dataset.existingTotal = '0.00';
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
});