/**
 * Comprehensive tests for invalid claim scenarios
 * These tests prevent security vulnerabilities and business logic bugs
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { JSDOM } from 'jsdom';
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

// Note: Navigation errors in JSDOM are expected but don't break test functionality

// Mock functions
global.alert = vi.fn();
global.confirm = vi.fn(() => true);

// Import modules
const viewPageModule = await import('../../static/js/view-page.js');

const {
  initializeViewPage,
  confirmClaims,
  validateClaims,
  updateTotal,
  _setState
} = viewPageModule;

describe('Invalid Claims Security Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Negative Quantity Protection', () => {
    it('should reject negative quantities at frontend level', async () => {
      setBodyHTML(`
        <div id="view-page-data" data-receipt-slug="test-receipt"></div>
        <div class="item-container" data-item-id="1">
          <h3>Burger</h3>
          <input type="number" class="claim-quantity" value="-5" min="0" data-item-id="1">
        </div>
        <p id="my-total">$0.00</p>
        <div id="claiming-warning" class="hidden"></div>
      `);
      
      initializeViewPage();
      _setState({ receiptSlug: 'test-receipt' });
      
      global.authenticatedJsonFetch = vi.fn();
      
      await confirmClaims();
      
      // Should not make API call with negative quantities
      expect(global.authenticatedJsonFetch).not.toHaveBeenCalled();
      expect(global.alert).toHaveBeenCalledWith('Please select items to claim');
    });

    it('should handle frontend validation of negative quantities', async () => {
      setBodyHTML(`
        <div id="view-page-data" data-receipt-slug="test-receipt"></div>
        <div class="item-container" data-item-id="1">
          <h3>Burger</h3>
          <input type="number" class="claim-quantity" value="-1" min="0" max="2" data-item-id="1">
        </div>
        <div id="claiming-warning" class="hidden">
          <div id="claiming-error-details"></div>
        </div>
        <p id="my-total">$15.00</p>
      `);
      
      initializeViewPage();
      _setState({ receiptSlug: 'test-receipt' });
      
      global.authenticatedJsonFetch = vi.fn();
      
      await confirmClaims();
      
      // Negative quantities are treated as 0 (no positive claims)
      expect(global.authenticatedJsonFetch).not.toHaveBeenCalled();
      expect(global.alert).toHaveBeenCalledWith('Please select items to claim');
    });
  });

  describe('Extreme Quantity Protection', () => {
    it('should handle extremely large quantities', () => {
      setBodyHTML(`
        <div class="item-container" data-item-id="1">
          <div class="item-share-amount" data-amount="10.00"></div>
          <input type="number" class="claim-quantity" value="999999999" max="1" data-item-id="1">
        </div>
        <p id="my-total">$0.00</p>
        <div id="claiming-warning" class="hidden">
          <div id="claiming-error-details"></div>
        </div>
      `);
      
      // Should trigger validation error (exceeds max)
      const isValid = validateClaims();
      expect(isValid).toBe(false);
      
      // Should show validation banner
      const warningBanner = document.getElementById('claiming-warning');
      expect(warningBanner.classList.contains('hidden')).toBe(false);
    });

    it('should prevent claims exceeding available quantity', () => {
      setBodyHTML(`
        <div class="item-container" data-item-id="1">
          <h3>Burger</h3>
          <input type="number" class="claim-quantity" value="5" max="2" data-item-id="1">
        </div>
        <div id="claiming-warning" class="hidden">
          <div id="claiming-error-details"></div>
        </div>
      `);
      
      const isValid = validateClaims();
      expect(isValid).toBe(false);
      
      // Should show specific error message
      const errorDetails = document.getElementById('claiming-error-details');
      expect(errorDetails.innerHTML).toContain('Burger: trying to claim 5 but only 2 available');
    });
  });

  describe('Double Finalization Protection', () => {
    it('should lock UI after finalization status update', () => {
      setBodyHTML(`
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
      `);
      
      // Simulate finalization status update
      const { updateFinalizationStatus } = viewPageModule;
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
      setBodyHTML(`
        <div id="view-page-data" data-receipt-slug="test-receipt"></div>
        <div class="item-container" data-item-id="1">
          <h3>Burger</h3>
          <div class="item-share-amount" data-amount="10.00"></div>
          <input type="number" class="claim-quantity" value="1" min="0" max="2" data-item-id="1">
        </div>
        <p id="my-total">$10.00</p>
        <div id="claiming-warning" class="hidden"></div>
      `);
      
      initializeViewPage();
      _setState({ receiptSlug: 'test-receipt' });
      
      // Mock server rejection of double finalization
      global.authenticatedJsonFetch = vi.fn().mockResolvedValue({
        ok: false,
        json: () => Promise.resolve({ 
          error: 'Claims have already been finalized and cannot be changed' 
        })
      });
      
      await confirmClaims();
      
      // Should show clear error message
      expect(global.alert).toHaveBeenCalledWith(
        'Error finalizing claims: Claims have already been finalized and cannot be changed\n\nIf the error persists, refresh the page.'
      );
    });
  });

  describe('Invalid Data Protection', () => {
    it('should handle backend rejection of invalid item IDs', async () => {
      setBodyHTML(`
        <div id="view-page-data" data-receipt-slug="test-receipt"></div>
        <div class="item-container" data-item-id="999">
          <h3>Invalid Item</h3>
          <div class="item-share-amount" data-amount="10.00"></div>
          <input type="number" class="claim-quantity" value="1" min="0" max="2" data-item-id="999">
        </div>
        <p id="my-total">$10.00</p>
        <div id="claiming-warning" class="hidden"></div>
      `);
      
      initializeViewPage();
      _setState({ receiptSlug: 'test-receipt' });
      
      // Frontend validation passes, but backend rejects invalid item ID
      global.authenticatedJsonFetch = vi.fn().mockResolvedValue({
        ok: false,
        json: () => Promise.resolve({ error: 'Item 999 not found' })
      });
      
      await confirmClaims();

      expect(global.alert).toHaveBeenCalledWith('Error finalizing claims: Item 999 not found\n\nIf the error persists, refresh the page.');
    });

    it('should handle zero quantities correctly (valid case)', async () => {
      setBodyHTML(`
        <div id="view-page-data" data-receipt-slug="test-receipt"></div>
        <div class="item-container" data-item-id="1">
          <h3>Burger</h3>
          <div class="item-share-amount" data-amount="10.00"></div>
          <input type="number" class="claim-quantity" value="0" min="0" max="2" data-item-id="1">
        </div>
        <div class="item-container" data-item-id="2">
          <h3>Fries</h3>
          <div class="item-share-amount" data-amount="5.00"></div>
          <input type="number" class="claim-quantity" value="1" min="0" max="2" data-item-id="2">
        </div>
        <p id="my-total">$5.00</p>
        <div id="claiming-warning" class="hidden"></div>
      `);
      
      initializeViewPage();
      _setState({ receiptSlug: 'test-receipt' });
      
      global.authenticatedJsonFetch = vi.fn().mockResolvedValue({
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
      setBodyHTML(`
        <div class="item-container" data-item-id="1">
          <div class="item-share-amount" data-amount="10.00"></div>
          <input type="number" class="claim-quantity" value="abc" data-item-id="1">
        </div>
        <p id="my-total">$10.00</p>
      `);
      
      updateTotal();
      
      // Should treat non-numeric as 0
      const totalElement = document.getElementById('my-total');
      expect(totalElement.textContent).toBe('$0.00');
    });

    it('should handle decimal quantities (round down)', () => {
      setBodyHTML(`
        <div class="item-container" data-item-id="1">
          <div class="item-share-amount" data-amount="10.00"></div>
          <input type="number" class="claim-quantity" value="2.7" data-item-id="1">
        </div>
        <p id="my-total">$0.00</p>
      `);
      
      updateTotal();
      
      // parseInt should round down to 2
      const totalElement = document.getElementById('my-total');
      expect(totalElement.textContent).toBe('$20.00'); // 2 * $10.00
    });
  });
});