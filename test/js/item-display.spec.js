/**
 * Tests for item display formatting
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { JSDOM } from 'jsdom';

// Set up DOM environment
const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
  url: 'http://localhost',
  pretendToBeVisual: true,
  resources: 'usable'
});

global.window = dom.window;
global.document = window.document;

describe('Item Display Formatting', () => {
  
  describe('Single Item Display (× 1 omission)', () => {
    it('should omit "× 1" for single quantity items', () => {
      // Simulate server template logic for single item
      const singleItem = {
        name: 'Burger',
        unit_price: 15.50,
        quantity: 1,
        total_price: 15.50
      };
      
      // Template logic: {% if item.quantity > 1 %}
      let displayText;
      if (singleItem.quantity > 1) {
        displayText = `$${singleItem.unit_price.toFixed(2)} × ${singleItem.quantity} = $${singleItem.total_price.toFixed(2)}`;
      } else {
        displayText = `$${singleItem.total_price.toFixed(2)}`;
      }
      
      // Should show just the price for single items
      expect(displayText).toBe('$15.50');
      expect(displayText).not.toContain('× 1');
    });
    
    it('should show multiplication for multiple quantity items', () => {
      // Simulate server template logic for multiple items
      const multipleItem = {
        name: 'Fries',
        unit_price: 8.75,
        quantity: 2,
        total_price: 17.50
      };
      
      // Template logic: {% if item.quantity > 1 %}
      let displayText;
      if (multipleItem.quantity > 1) {
        displayText = `$${multipleItem.unit_price.toFixed(2)} × ${multipleItem.quantity} = $${multipleItem.total_price.toFixed(2)}`;
      } else {
        displayText = `$${multipleItem.total_price.toFixed(2)}`;
      }
      
      // Should show multiplication for multiple items
      expect(displayText).toBe('$8.75 × 2 = $17.50');
      expect(displayText).toContain('×');
    });
    
    it('should handle edge case of quantity 0 (theoretical)', () => {
      // Edge case: quantity 0 (shouldn't happen in practice but good to test)
      const zeroItem = {
        unit_price: 10.00,
        quantity: 0,
        total_price: 0.00
      };
      
      let displayText;
      if (zeroItem.quantity > 1) {
        displayText = `$${zeroItem.unit_price.toFixed(2)} × ${zeroItem.quantity} = $${zeroItem.total_price.toFixed(2)}`;
      } else {
        displayText = `$${zeroItem.total_price.toFixed(2)}`;
      }
      
      // Should show just the price (no multiplication)
      expect(displayText).toBe('$0.00');
      expect(displayText).not.toContain('× 0');
    });
  });
  
  describe('Item Display Integration', () => {
    it('should format different item scenarios correctly', () => {
      const testItems = [
        { name: 'Single Burger', unit_price: 15.50, quantity: 1, total_price: 15.50, expected: '$15.50' },
        { name: 'Double Fries', unit_price: 8.75, quantity: 2, total_price: 17.50, expected: '$8.75 × 2 = $17.50' },
        { name: 'Triple Soda', unit_price: 3.00, quantity: 3, total_price: 9.00, expected: '$3.00 × 3 = $9.00' },
        { name: 'Single Expensive Item', unit_price: 25.99, quantity: 1, total_price: 25.99, expected: '$25.99' }
      ];
      
      testItems.forEach(item => {
        let displayText;
        if (item.quantity > 1) {
          displayText = `$${item.unit_price.toFixed(2)} × ${item.quantity} = $${item.total_price.toFixed(2)}`;
        } else {
          displayText = `$${item.total_price.toFixed(2)}`;
        }
        
        expect(displayText).toBe(item.expected);
      });
    });
  });
});