/**
 * Comprehensive tests for invalid claim scenarios
 * These tests prevent security vulnerabilities and business logic bugs
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  createTestDOM,
  setupMocks,
  createViewPageDOM,
  mockAuthFetch,
  mockErrorResponse,
  resetTestEnvironment
} from './test-helpers.js';

// Set up environment
createTestDOM();
const mocks = setupMocks();

// Import modules
const viewPageModule = await import('../../static/js/view-page.js');

const {
  initializeViewPage,
  confirmClaims,
  validateClaims,
  updateTotal,
  updateFinalizationStatus,
  _setState
} = viewPageModule;

// Helper for common test setup
function setupTestCase(itemsConfig = {}) {
  const defaultItem = {
    itemId: '1',
    name: 'Burger',
    shareAmount: '15.00',
    quantity: 0,
    min: 0,
    max: 2
  };
  
  const items = [{ ...defaultItem, ...itemsConfig }];
  document.body.innerHTML = createViewPageDOM({ items });
  initializeViewPage();
  _setState({ receiptSlug: 'test-receipt' });
}

describe('Invalid Claims Security Tests', () => {
  beforeEach(() => {
    resetTestEnvironment();
  });

  describe('Negative Quantity Protection', () => {
    it('should reject negative quantities at frontend level', async () => {
      setupTestCase({ quantity: -5 });
      
      mockAuthFetch();
      
      await confirmClaims();
      
      // Should not make API call with negative quantities
      expect(global.authenticatedJsonFetch).not.toHaveBeenCalled();
      expect(mocks.alert).toHaveBeenCalledWith('Please select items to claim');
    });

    it('should handle frontend validation of negative quantities', async () => {
      setupTestCase({ quantity: -1, max: 2 });
      
      mockAuthFetch();
      
      await confirmClaims();
      
      // Negative quantities are treated as 0 (no positive claims)
      expect(global.authenticatedJsonFetch).not.toHaveBeenCalled();
      expect(mocks.alert).toHaveBeenCalledWith('Please select items to claim');
    });
  });

  describe('Extreme Quantity Protection', () => {
    it('should handle extremely large quantities', () => {
      document.body.innerHTML = `
        <div class="item-container" data-item-id="1">
          <div class="item-share-amount" data-amount="10.00"></div>
          <input type="number" class="claim-quantity" value="999999999" max="1" data-item-id="1">
        </div>
        <p id="my-total">$0.00</p>
        <div id="claiming-warning" class="hidden">
          <div id="claiming-error-details"></div>
        </div>
      `;
      
      // Should trigger validation error (exceeds max)
      const isValid = validateClaims();
      expect(isValid).toBe(false);
      
      // Should show validation banner
      const warningBanner = document.getElementById('claiming-warning');
      expect(warningBanner.classList.contains('hidden')).toBe(false);
    });

    it('should prevent claims exceeding available quantity', () => {
      document.body.innerHTML = createViewPageDOM({
        items: [{
          itemId: '1',
          name: 'Burger',
          shareAmount: '15.00',
          quantity: 5,
          max: 2
        }]
      });
      
      const isValid = validateClaims();
      expect(isValid).toBe(false);
      
      // Should show specific error message
      const errorDetails = document.getElementById('claiming-error-details');
      expect(errorDetails.innerHTML).toContain('Burger: trying to claim 5 but only 2 available');
    });
  });

  describe('Double Finalization Protection', () => {
    it('should lock UI after finalization status update', () => {
      document.body.innerHTML = `
        <div class="sticky bottom-4 border-green-500">
          <p class="text-sm text-gray-600">Your Total (test)</p>
          <p id="my-total" class="text-green-600">$10.00</p>
          <button id="claim-button">Finalize Claims</button>
        </div>
        <div class="item-container" data-item-id="1">
          <div class="ml-4">
            <input type="number" class="claim-quantity border-gray-300" value="1" data-item-id="1">
          </div>
        </div>
      `;
      
      // Simulate finalization status update
      updateFinalizationStatus(true);
      
      // UI should be locked
      const input = document.querySelector('.claim-quantity');
      expect(input.readOnly).toBe(true);
      expect(input.classList.contains('bg-gray-50')).toBe(true);
      
      // Button should be replaced with checkmark
      const button = document.getElementById('claim-button');
      expect(button).toBeFalsy(); // Button should be replaced
      
      // Total should be blue (finalized state)
      const total = document.getElementById('my-total');
      expect(total.classList.contains('text-blue-600')).toBe(true);
    });

    it('should handle server rejection of double finalization', async () => {
      setupTestCase({ quantity: 1, max: 2 });
      
      // Mock server rejection of double finalization
      mockAuthFetch(mockErrorResponse('Claims have already been finalized and cannot be changed'));
      
      await confirmClaims();
      
      // Should show clear error message
      expect(mocks.alert).toHaveBeenCalledWith(
        'Error finalizing claims: Claims have already been finalized and cannot be changed'
      );
    });
  });

  describe('Invalid Data Protection', () => {
    it('should handle backend rejection of invalid item IDs', async () => {
      document.body.innerHTML = createViewPageDOM({
        items: [{
          itemId: '999',
          name: 'Invalid Item',
          shareAmount: '10.00',
          quantity: 1,
          max: 2
        }]
      });
      
      initializeViewPage();
      _setState({ receiptSlug: 'test-receipt' });
      
      // Frontend validation passes, but backend rejects invalid item ID
      mockAuthFetch(mockErrorResponse('Item 999 not found'));
      
      await confirmClaims();
      
      expect(mocks.alert).toHaveBeenCalledWith('Error finalizing claims: Item 999 not found');
    });

    it('should handle zero quantities correctly (valid case)', async () => {
      document.body.innerHTML = createViewPageDOM({
        items: [
          {
            itemId: '1',
            name: 'Burger',
            shareAmount: '10.00',
            quantity: 0,
            max: 2
          },
          {
            itemId: '2',
            name: 'Fries',
            shareAmount: '5.00',
            quantity: 1,
            max: 2
          }
        ],
        myTotal: '5.00'
      });
      
      initializeViewPage();
      _setState({ receiptSlug: 'test-receipt' });
      
      mockAuthFetch({ 
        ok: true,
        json: () => Promise.resolve({ success: true, finalized: true, claims_count: 1 })
      });
      
      await confirmClaims();
      
      // Should succeed - zero quantities are valid (user doesn't want that item)
      expect(global.authenticatedJsonFetch).toHaveBeenCalled();
      
      // Should send both items (including zero)
      const fetchCall = global.authenticatedJsonFetch.mock.calls[0];
      const requestData = JSON.parse(fetchCall[1].body);
      expect(requestData.claims).toEqual([
        { line_item_id: '1', quantity: 0 },
        { line_item_id: '2', quantity: 1 }
      ]);
    });
  });

  describe('Malformed Input Protection', () => {
    it('should handle non-numeric input values', () => {
      document.body.innerHTML = `
        <div class="item-container" data-item-id="1">
          <div class="item-share-amount" data-amount="10.00"></div>
          <input type="number" class="claim-quantity" value="abc" data-item-id="1">
        </div>
        <p id="my-total">$10.00</p>
      `;
      
      updateTotal();
      
      // Should treat non-numeric as 0
      const totalElement = document.getElementById('my-total');
      expect(totalElement.textContent).toBe('$0.00');
    });

    it('should handle decimal quantities (round down)', () => {
      document.body.innerHTML = `
        <div class="item-container" data-item-id="1">
          <div class="item-share-amount" data-amount="10.00"></div>
          <input type="number" class="claim-quantity" value="2.7" data-item-id="1">
        </div>
        <p id="my-total">$0.00</p>
      `;
      
      updateTotal();
      
      // parseInt should round down to 2
      const totalElement = document.getElementById('my-total');
      expect(totalElement.textContent).toBe('$20.00'); // 2 * $10.00
    });
  });
});