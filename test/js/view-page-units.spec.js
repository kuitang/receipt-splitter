/**
 * Unit tests for view-page.js individual functions
 * Tests each function in isolation with minimal DOM setup
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { JSDOM } from 'jsdom';

// Set up minimal DOM environment
const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>');
global.window = dom.window;
global.document = window.document;

// Import the module
const viewPageModule = await import('../../static/js/view-page.js');

const {
  validateClaims,
  hasActiveClaims,
  updateButtonState,
  updateTotal,
  initializeViewPage,
  _getState,
  _setState
} = viewPageModule;

describe('View Page Unit Tests', () => {
  beforeEach(() => {
    // Reset DOM for each test
    document.body.innerHTML = '';
  });

  describe('hasActiveClaims', () => {
    it('should return false when no inputs exist', () => {
      expect(hasActiveClaims()).toBe(false);
    });

    it('should return false when all inputs are zero', () => {
      document.body.innerHTML = `
        <input class="claim-quantity" value="0">
        <input class="claim-quantity" value="0">
      `;
      expect(hasActiveClaims()).toBe(false);
    });

    it('should return true when any input has value > 0', () => {
      document.body.innerHTML = `
        <input class="claim-quantity" value="0">
        <input class="claim-quantity" value="2">
        <input class="claim-quantity" value="0">
      `;
      expect(hasActiveClaims()).toBe(true);
    });

    it('should handle empty and invalid values correctly', () => {
      document.body.innerHTML = `
        <input class="claim-quantity" value="">
        <input class="claim-quantity" value="abc">
        <input class="claim-quantity" value="0">
      `;
      expect(hasActiveClaims()).toBe(false);
    });
  });

  describe('validateClaims', () => {
    it('should return true when no inputs exist', () => {
      expect(validateClaims()).toBe(true);
    });

    it('should validate max quantities correctly', () => {
      document.body.innerHTML = `
        <input class="claim-quantity" value="2" max="5">
        <input class="claim-quantity" value="1" max="3">
      `;
      expect(validateClaims()).toBe(true);
    });

    it('should return false when exceeding max quantity', () => {
      document.body.innerHTML = `
        <input class="claim-quantity" value="6" max="5">
      `;
      expect(validateClaims()).toBe(false);
    });

    it('should add error classes to invalid inputs', () => {
      document.body.innerHTML = `
        <input class="claim-quantity" value="10" max="2">
      `;
      const input = document.querySelector('.claim-quantity');
      
      validateClaims();
      
      expect(input.classList.contains('border-red-500')).toBe(true);
      expect(input.classList.contains('bg-red-50')).toBe(true);
    });

    it('should show validation banner with errors', () => {
      document.body.innerHTML = `
        <div id="claiming-warning" class="hidden">
          <div id="claiming-error-details"></div>
        </div>
        <div class="item-container">
          <h3>Test Item</h3>
          <input class="claim-quantity" value="5" max="2">
        </div>
      `;
      
      validateClaims();
      
      const banner = document.getElementById('claiming-warning');
      const details = document.getElementById('claiming-error-details');
      
      expect(banner.classList.contains('hidden')).toBe(false);
      expect(details.innerHTML).toContain('Test Item: trying to claim 5 but only 2 available');
    });

    it('should hide banner when validation passes', () => {
      document.body.innerHTML = `
        <div id="claiming-warning" class="">
          <div id="claiming-error-details">Previous errors</div>
        </div>
        <input class="claim-quantity" value="1" max="2">
      `;
      
      validateClaims();
      
      const banner = document.getElementById('claiming-warning');
      expect(banner.classList.contains('hidden')).toBe(true);
    });

    it('should handle missing banner elements gracefully', () => {
      document.body.innerHTML = `
        <input class="claim-quantity" value="5" max="2">
      `;
      
      // Should not throw even without banner elements
      expect(() => validateClaims()).not.toThrow();
      expect(validateClaims()).toBe(false);
    });
  });

  describe('updateButtonState', () => {
    it('should handle missing button gracefully', () => {
      expect(() => updateButtonState()).not.toThrow();
    });

    it('should disable button when no active claims', () => {
      document.body.innerHTML = `
        <button id="claim-button">Claim</button>
        <input class="claim-quantity" value="0">
      `;
      
      updateButtonState();
      
      expect(document.getElementById('claim-button').disabled).toBe(true);
    });

    it('should enable button when has active claims', () => {
      document.body.innerHTML = `
        <button id="claim-button" disabled>Claim</button>
        <input class="claim-quantity" value="2">
      `;
      
      updateButtonState();
      
      expect(document.getElementById('claim-button').disabled).toBe(false);
    });
  });

  describe('updateTotal', () => {
    it('should handle missing total element gracefully', () => {
      expect(() => updateTotal()).not.toThrow();
    });

    it('should calculate total correctly with existing amount', () => {
      document.body.innerHTML = `
        <p id="my-total" data-existing-total="25.50">$25.50</p>
        <div class="item-container">
          <div class="item-share-amount" data-amount="10.00"></div>
          <input class="claim-quantity" value="2" data-item-id="1">
        </div>
        <button id="claim-button">Claim</button>
        <div id="claiming-warning" class="hidden">
          <div id="claiming-error-details"></div>
        </div>
      `;
      
      updateTotal();
      
      const totalElement = document.getElementById('my-total');
      expect(totalElement.textContent).toBe('$45.50'); // 25.50 + (2 * 10.00)
    });

    it('should handle zero existing total', () => {
      document.body.innerHTML = `
        <p id="my-total" data-existing-total="0.00">$0.00</p>
        <div class="item-container">
          <div class="item-share-amount" data-amount="15.75"></div>
          <input class="claim-quantity" value="1" data-item-id="1">
        </div>
        <button id="claim-button">Claim</button>
        <div id="claiming-warning" class="hidden">
          <div id="claiming-error-details"></div>
        </div>
      `;
      
      updateTotal();
      
      const totalElement = document.getElementById('my-total');
      expect(totalElement.textContent).toBe('$15.75');
    });

    it('should handle missing share elements gracefully', () => {
      document.body.innerHTML = `
        <p id="my-total" data-existing-total="10.00">$10.00</p>
        <input class="claim-quantity" value="2" data-item-id="1">
        <button id="claim-button">Claim</button>
        <div id="claiming-warning" class="hidden">
          <div id="claiming-error-details"></div>
        </div>
      `;
      
      expect(() => updateTotal()).not.toThrow();
      
      const totalElement = document.getElementById('my-total');
      expect(totalElement.textContent).toBe('$10.00'); // Should preserve existing total
    });

    it('should handle floating point precision correctly', () => {
      document.body.innerHTML = `
        <p id="my-total" data-existing-total="0.10">$0.10</p>
        <div class="item-container">
          <div class="item-share-amount" data-amount="0.20"></div>
          <input class="claim-quantity" value="1" data-item-id="1">
        </div>
        <button id="claim-button">Claim</button>
        <div id="claiming-warning" class="hidden">
          <div id="claiming-error-details"></div>
        </div>
      `;
      
      updateTotal();
      
      const totalElement = document.getElementById('my-total');
      expect(totalElement.textContent).toBe('$0.30'); // Should be properly rounded
    });
  });

  describe('initializeViewPage', () => {
    it('should handle missing data container gracefully', () => {
      expect(() => initializeViewPage()).not.toThrow();
    });

    it('should read data attributes correctly', () => {
      document.body.innerHTML = `
        <div id="view-page-data" 
             data-receipt-slug="test-receipt" 
             data-receipt-id="123">
        </div>
      `;
      
      initializeViewPage();
      
      const state = _getState();
      expect(state.receiptSlug).toBe('test-receipt');
      expect(state.receiptId).toBe('123');
    });
  });

  describe('Edge Cases and Error Handling', () => {
    it('should handle malformed DOM structures', () => {
      document.body.innerHTML = `
        <input class="claim-quantity" value="2">
        <!-- Missing container or share elements -->
      `;
      
      expect(() => {
        hasActiveClaims();
        validateClaims();
        updateButtonState();
        updateTotal();
      }).not.toThrow();
    });

    it('should handle extreme numeric values', () => {
      document.body.innerHTML = `
        <p id="my-total" data-existing-total="999999999.99">$999999999.99</p>
        <div class="item-container">
          <div class="item-share-amount" data-amount="0.01"></div>
          <input class="claim-quantity" value="1000000" data-item-id="1">
        </div>
        <button id="claim-button">Claim</button>
        <div id="claiming-warning" class="hidden">
          <div id="claiming-error-details"></div>
        </div>
      `;
      
      expect(() => updateTotal()).not.toThrow();
      
      const totalElement = document.getElementById('my-total');
      const result = parseFloat(totalElement.textContent.replace('$', ''));
      expect(result).toBeGreaterThan(999999999);
    });

    it('should handle concurrent function calls', () => {
      document.body.innerHTML = `
        <p id="my-total" data-existing-total="10.00">$10.00</p>
        <div class="item-container">
          <div class="item-share-amount" data-amount="5.00"></div>
          <input class="claim-quantity" value="2" data-item-id="1">
        </div>
        <button id="claim-button">Claim</button>
        <div id="claiming-warning" class="hidden">
          <div id="claiming-error-details"></div>
        </div>
      `;
      
      // Call multiple functions rapidly
      expect(() => {
        for (let i = 0; i < 100; i++) {
          hasActiveClaims();
          validateClaims();
          updateButtonState();
          updateTotal();
        }
      }).not.toThrow();
      
      // Final state should be consistent
      expect(hasActiveClaims()).toBe(true);
      expect(document.getElementById('my-total').textContent).toBe('$20.00');
    });
  });
});