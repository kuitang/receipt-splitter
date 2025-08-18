/**
 * Tests for item display formatting
 */

import { describe, it, expect } from 'vitest';
import { createTestDOM } from './test-helpers.js';

// Set up DOM environment
createTestDOM();

describe('Item Display Formatting', () => {
  
  // Helper function to format item display
  function formatItemDisplay(item) {
    if (item.quantity > 1) {
      return `$${item.unit_price.toFixed(2)} × ${item.quantity} = $${item.total_price.toFixed(2)}`;
    } else {
      return `$${item.total_price.toFixed(2)}`;
    }
  }
  
  describe('Single Item Display (× 1 omission)', () => {
    it('should omit "× 1" for single quantity items', () => {
      // Simulate server template logic for single item
      const singleItem = {
        name: 'Burger',
        unit_price: 15.50,
        quantity: 1,
        total_price: 15.50
      };
      
      const displayText = formatItemDisplay(singleItem);
      
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
      
      const displayText = formatItemDisplay(multipleItem);
      
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
      
      const displayText = formatItemDisplay(zeroItem);
      
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
        const displayText = formatItemDisplay(item);
        expect(displayText).toBe(item.expected);
      });
    });
  });
});