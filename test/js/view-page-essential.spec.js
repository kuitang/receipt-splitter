/**
 * Essential unit tests for view-page.js (non-trivial cases only)
 * Trivial multiplication tests removed after protocol change
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

// Mock functions
global.alert = vi.fn();
global.confirm = vi.fn(() => true);

// Import the modules
const utilsModule = await import('../../static/js/utils.js');
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

describe('View Page Essential Unit Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    // Set up minimal realistic DOM structure
    setBodyHTML(`
      <div id="view-page-data" 
           data-receipt-slug="test-receipt" 
           data-receipt-id="123">
      </div>
      
      <div class="item-container" data-item-id="1">
        <h3>Burger</h3>
        <div class="item-share-amount" data-amount="15.50"></div>
        <input type="number" class="claim-quantity" 
               data-item-id="1" min="0" max="2" value="0">
      </div>
      
      <div id="claiming-warning" class="hidden">
        <div id="claiming-error-details"></div>
      </div>
      
      <p id="my-total">$0.00</p>
      <button id="claim-button" disabled>Finalize Claims</button>
    `);
    
    initializeViewPage();
  });

  describe('Essential Error Handling', () => {
    it('should handle missing total element gracefully', () => {
      document.getElementById('my-total').remove();
      expect(() => updateTotal()).not.toThrow();
    });

    it('should handle missing share elements gracefully', () => {
      document.querySelector('.item-share-amount').remove();
      
      expect(() => updateTotal()).not.toThrow();
      
      // Should show $0 when no price data available
      const totalElement = document.getElementById('my-total');
      expect(totalElement.textContent).toBe('$0.00');
    });

    it('should handle malformed input values', () => {
      const input = document.querySelector('.claim-quantity');
      
      // Test various malformed inputs
      const malformedValues = ['abc', '', null, 'undefined', '1.5.5', 'NaN'];
      
      malformedValues.forEach(value => {
        input.value = value;
        expect(() => updateTotal()).not.toThrow();
        
        // Should treat as 0 and calculate accordingly
        const totalElement = document.getElementById('my-total');
        expect(totalElement.textContent).toBe('$0.00');
      });
    });
  });

  describe('Essential State Management', () => {
    it('should properly initialize view page state', () => {
      const state = _getState();
      expect(state.receiptSlug).toBe('test-receipt');
      expect(state.receiptId).toBe('123');
    });

    it('should detect active claims correctly', () => {
      // No claims
      expect(hasActiveClaims()).toBe(false);
      
      // Has claims
      document.querySelector('.claim-quantity').value = '1';
      expect(hasActiveClaims()).toBe(true);
      
      // Back to no claims
      document.querySelector('.claim-quantity').value = '0';
      expect(hasActiveClaims()).toBe(false);
    });

    it('should update button state based on claims', () => {
      const button = document.getElementById('claim-button');
      
      // Initially disabled (no claims)
      updateButtonState();
      expect(button.disabled).toBe(true);
      
      // Enable when user has claims
      document.querySelector('.claim-quantity').value = '1';
      updateButtonState();
      expect(button.disabled).toBe(false);
      
      // Disable when no claims again
      document.querySelector('.claim-quantity').value = '0';
      updateButtonState();
      expect(button.disabled).toBe(true);
    });
  });

  describe('Essential Validation', () => {
    it('should validate quantity constraints', () => {
      const input = document.querySelector('.claim-quantity');
      
      // Valid quantity
      input.value = '2'; // max is 2
      expect(validateClaims()).toBe(true);
      
      // Invalid quantity (exceeds max)
      input.value = '3'; // max is 2
      expect(validateClaims()).toBe(false);
      expect(input.classList.contains('border-red-500')).toBe(true);
    });

    it('should show validation banner for errors', () => {
      const input = document.querySelector('.claim-quantity');
      const warningBanner = document.getElementById('claiming-warning');
      
      // Set invalid value
      input.value = '5'; // max is 2
      validateClaims();
      
      // Banner should be visible with specific error
      expect(warningBanner.classList.contains('hidden')).toBe(false);
      const errorDetails = document.getElementById('claiming-error-details');
      expect(errorDetails.innerHTML).toContain('Burger: trying to claim 5 but only 2 available');
    });
  });
});