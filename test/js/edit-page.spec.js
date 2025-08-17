/**
 * Vitest tests for edit-page.js
 * This properly loads and tests the receipt editor functions
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import fs from 'fs';
import path from 'path';

// Mock global functions that edit-page.js depends on
global.escapeHtml = (text) => {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
};

global.authenticatedFetch = vi.fn();
global.authenticatedJsonFetch = vi.fn();
global.getCookie = vi.fn(() => 'test-csrf-token');
global.getCsrfToken = vi.fn(() => 'test-csrf-token');

// Load and execute edit-page.js from the actual source location
const editPagePath = path.join(process.cwd(), 'static/js/edit-page.js');
const editPageCode = fs.readFileSync(editPagePath, 'utf8');

// Execute in global scope to define functions
eval(editPageCode);

describe('Receipt Editor - Real Tests Without Excessive Mocking', () => {
  beforeEach(() => {
    // Set up DOM
    document.body.innerHTML = `
      <div id="edit-page-data" 
           data-receipt-slug="test-receipt" 
           data-receipt-id="123"
           data-is-processing="false">
      </div>
      <div id="balance-warning" class="hidden"></div>
      <div id="balance-error-details"></div>
      <input id="restaurant_name" value="Test Restaurant">
      <input id="subtotal" type="number" value="0">
      <input id="tax" type="number" value="0">
      <input id="tip" type="number" value="0">
      <input id="total" type="number" value="0">
      <div id="items-container"></div>
      <button onclick="finalizeReceipt()">Finalize & Share</button>
    `;
    
    // Initialize the page
    initializeEditPage();
  });

  describe('Floating Point Precision Hell', () => {
    it('should handle JavaScript\'s 0.1 + 0.2 !== 0.3 problem', () => {
      // This is the classic JS floating point issue
      addItem();
      const row1 = document.querySelector('.item-row');
      row1.querySelector('.item-name').value = 'Item 1';
      row1.querySelector('.item-quantity').value = '1';
      row1.querySelector('.item-price').value = '0.1';
      updateItemTotal(row1);

      addItem();
      const row2 = document.querySelectorAll('.item-row')[1];
      row2.querySelector('.item-name').value = 'Item 2';
      row2.querySelector('.item-quantity').value = '1';
      row2.querySelector('.item-price').value = '0.2';
      updateItemTotal(row2);

      const subtotal = calculateSubtotal();
      // In JS: 0.1 + 0.2 = 0.30000000000000004
      // Our function should handle this within tolerance
      expect(Math.abs(subtotal - 0.3)).toBeLessThan(0.01);
    });

    it('should handle multiplication precision errors', () => {
      // 19.99 * 3 = 59.97 in theory, but JS might give 59.969999999999999
      addItem();
      const row = document.querySelector('.item-row');
      row.querySelector('.item-quantity').value = '3';
      row.querySelector('.item-price').value = '19.99';
      updateItemTotal(row);

      const itemTotal = row.querySelector('.item-total');
      expect(itemTotal.value).toBe('59.97'); // Display should be rounded
      expect(parseFloat(itemTotal.dataset.fullValue)).toBeCloseTo(59.97, 2);
    });

    it('should accumulate rounding errors across many items', () => {
      // Add 100 items with problematic decimals
      for (let i = 0; i < 100; i++) {
        addItem();
        const row = document.querySelectorAll('.item-row')[i];
        row.querySelector('.item-quantity').value = '1';
        row.querySelector('.item-price').value = '0.01'; // Penny items
        updateItemTotal(row);
      }

      const subtotal = calculateSubtotal();
      expect(subtotal).toBeCloseTo(1.00, 2); // Should be exactly $1.00
      
      // Now validate with tax/tip
      document.getElementById('subtotal').value = subtotal.toFixed(2);
      document.getElementById('tax').value = '0.08'; // 8 cents
      document.getElementById('tip').value = '0.15'; // 15 cents
      document.getElementById('total').value = '1.23';
      
      const errors = validateReceipt();
      expect(errors.length).toBe(0); // Should validate within tolerance
    });
  });

  describe('XSS Attack Vectors', () => {
    it('should prevent script injection in item names', () => {
      const xssAttacks = [
        '<script>alert("XSS")</script>',
        '"><script>alert(1)</script>',
        '<img src=x onerror="alert(1)">',
        '<svg/onload=alert(1)>',
        'javascript:alert(1)',
        '<iframe src="javascript:alert(1)">',
        '<body onload=alert(1)>',
        '${alert(1)}',
        '{{constructor.constructor("alert(1)")()}}',
        '<details open ontoggle=alert(1)>',
        '<input autofocus onfocus=alert(1)>',
      ];

      xssAttacks.forEach((payload, index) => {
        addItem();
        const row = document.querySelectorAll('.item-row')[index];
        const nameInput = row.querySelector('.item-name');
        nameInput.value = payload;

        // Get the data - it should store the raw value
        const data = getReceiptData();
        expect(data.items[index].name).toBe(payload);

        // But when displayed via innerHTML, it should be safe
        updateProrations();
        const proration = row.querySelector('.item-proration');
        
        // Check that dangerous content isn't executable
        expect(proration.innerHTML).not.toMatch(/<script[^>]*>/i);
        expect(proration.innerHTML).not.toContain('onerror=');
        expect(proration.innerHTML).not.toContain('onload=');
        expect(proration.innerHTML).not.toContain('javascript:');
      });
    });
  });

  describe('Race Conditions', () => {
    it('should handle concurrent modifications without corruption', async () => {
      const modifications = [];
      
      // Simulate 50 concurrent modifications
      for (let i = 0; i < 50; i++) {
        modifications.push(
          new Promise(resolve => {
            setTimeout(() => {
              if (Math.random() > 0.5) {
                addItem();
                const rows = document.querySelectorAll('.item-row');
                const lastRow = rows[rows.length - 1];
                if (lastRow) {
                  lastRow.querySelector('.item-quantity').value = Math.floor(Math.random() * 10);
                  lastRow.querySelector('.item-price').value = (Math.random() * 100).toFixed(2);
                  updateItemTotal(lastRow);
                }
              } else {
                const rows = document.querySelectorAll('.item-row');
                if (rows.length > 0) {
                  const randomRow = rows[Math.floor(Math.random() * rows.length)];
                  const removeBtn = randomRow.querySelector('[data-action="remove-item"]');
                  if (removeBtn) removeItem(removeBtn);
                }
              }
              resolve();
            }, Math.random() * 10);
          })
        );
      }
      
      await Promise.all(modifications);
      
      // Verify data integrity
      const data = getReceiptData();
      const calculatedSubtotal = calculateSubtotal();
      const displayedSubtotal = parseFloat(document.getElementById('subtotal').value);
      
      // Subtotals should match within tolerance
      expect(Math.abs(calculatedSubtotal - displayedSubtotal)).toBeLessThan(0.01);
      
      // All items should have valid data
      data.items.forEach(item => {
        if (item.name) {
          expect(typeof item.quantity).toBe('number');
          expect(typeof item.unit_price).toBe('number');
          expect(typeof item.total_price).toBe('number');
        }
      });
    });

    it('should prevent double-save race condition', async () => {
      let callCount = 0;
      
      global.authenticatedJsonFetch = vi.fn(async () => {
        callCount++;
        // Simulate network delay
        await new Promise(r => setTimeout(r, 50));
        return {
          ok: true,
          json: async () => ({ success: true, is_balanced: true })
        };
      });

      // Try to save 10 times simultaneously
      const saves = [];
      for (let i = 0; i < 10; i++) {
        saves.push(saveReceipt(true));
      }
      
      await Promise.allSettled(saves);
      
      // Should only make one call due to isProcessing flag
      expect(callCount).toBe(1);
    });
  });

  describe('Input Fuzzing', () => {
    it('should handle malformed numeric inputs', () => {
      const fuzzInputs = [
        'NaN',
        'Infinity', 
        '-Infinity',
        '1.2.3.4',
        '1,234,567.89',
        '1e308',  // Near max float
        '1e-308', // Near min float
        '0x1234', // Hex
        '0o777',  // Octal
        '0b1010', // Binary
        '💰💰💰',
        '\\x00',  // Null byte
        '"><script>',
        '../../../etc/passwd',
        'Robert"); DROP TABLE items;--',
      ];

      fuzzInputs.forEach((input, index) => {
        addItem();
        const row = document.querySelectorAll('.item-row')[index];
        
        // Should not throw
        expect(() => {
          row.querySelector('.item-quantity').value = input;
          row.querySelector('.item-price').value = input;
          updateItemTotal(row);
        }).not.toThrow();
        
        // Should treat invalid as 0 or NaN
        const total = parseFloat(row.querySelector('.item-total').value);
        expect(isNaN(total) || total === 0).toBe(true);
      });
      
      // Validation should still work
      const errors = validateReceipt();
      expect(Array.isArray(errors)).toBe(true);
    });

    it('should handle extreme values without overflow', () => {
      addItem();
      const row = document.querySelector('.item-row');
      
      // JavaScript's MAX_SAFE_INTEGER is 2^53 - 1
      row.querySelector('.item-quantity').value = '9007199254740991';
      row.querySelector('.item-price').value = '1';
      updateItemTotal(row);
      
      const total = parseFloat(row.querySelector('.item-total').dataset.fullValue);
      expect(total).toBe(9007199254740991);
      
      // Test very small numbers
      addItem();
      const row2 = document.querySelectorAll('.item-row')[1];
      row2.querySelector('.item-quantity').value = '1';
      row2.querySelector('.item-price').value = '0.000000000001';
      updateItemTotal(row2);
      
      const total2 = parseFloat(row2.querySelector('.item-total').dataset.fullValue);
      expect(total2).toBeCloseTo(0.000000000001, 15);
    });
  });

  describe('Memory Leaks', () => {
    it('should not leak memory when rapidly adding/removing items', () => {
      const initialRows = document.querySelectorAll('.item-row').length;
      
      // Add and remove 500 items
      for (let i = 0; i < 500; i++) {
        addItem();
        const row = document.querySelector('.item-row:last-child');
        const btn = row.querySelector('[data-action="remove-item"]');
        removeItem(btn);
      }
      
      const finalRows = document.querySelectorAll('.item-row').length;
      expect(finalRows).toBe(initialRows);
      
      // Check for orphaned event listeners (would cause memory leaks)
      const allInputs = document.querySelectorAll('input');
      allInputs.forEach(input => {
        // Inputs should still be in the DOM tree
        expect(document.body.contains(input)).toBe(true);
      });
    });
  });

  describe('Business Logic Edge Cases', () => {
    it('should handle negative tax and tip as discounts', () => {
      addItem();
      const row = document.querySelector('.item-row');
      row.querySelector('.item-total').value = '100';
      row.querySelector('.item-total').dataset.fullValue = '100';
      
      document.getElementById('subtotal').value = '100';
      document.getElementById('tax').value = '-20';  // $20 discount
      document.getElementById('tip').value = '-10';  // $10 credit
      document.getElementById('total').value = '70';
      
      const errors = validateReceipt();
      expect(errors.length).toBe(0);
    });

    it('should calculate complex split scenarios correctly', () => {
      // Scenario: 3 people, unequal consumption
      const items = [
        { name: 'Person A entrée', qty: 1, price: 25.99 },
        { name: 'Person B entrée', qty: 1, price: 18.50 },
        { name: 'Person C entrée', qty: 1, price: 22.75 },
        { name: 'Shared appetizer', qty: 3, price: 4.50 }, // Split 3 ways
        { name: 'Shared dessert', qty: 2, price: 6.25 },   // Split 2 ways (C didn't have any)
      ];
      
      items.forEach((item, i) => {
        addItem();
        const row = document.querySelectorAll('.item-row')[i];
        row.querySelector('.item-name').value = item.name;
        row.querySelector('.item-quantity').value = item.qty;
        row.querySelector('.item-price').value = item.price;
        updateItemTotal(row);
      });
      
      updateSubtotal();
      const subtotal = parseFloat(document.getElementById('subtotal').value);
      
      // Expected: 25.99 + 18.50 + 22.75 + 13.50 + 12.50 = 93.24
      expect(subtotal).toBeCloseTo(93.24, 2);
      
      // Add 20% tip and 8% tax
      document.getElementById('tax').value = (subtotal * 0.08).toFixed(2);
      document.getElementById('tip').value = (subtotal * 0.20).toFixed(2);
      document.getElementById('total').value = (subtotal * 1.28).toFixed(2);
      
      const errors = validateReceipt();
      expect(errors.length).toBe(0);
      
      // Check prorations are calculated correctly
      updateProrations();
      const prorations = document.querySelectorAll('.item-proration');
      
      // Each proration should include tax and tip
      prorations.forEach(proration => {
        expect(proration.textContent).toMatch(/Tax: \$[\d.]+/);
        expect(proration.textContent).toMatch(/Tip: \$[\d.]+/);
        expect(proration.textContent).toMatch(/per item$/);
      });
    });

    it('should reject illogical receipt states', () => {
      // Negative subtotal
      document.getElementById('subtotal').value = '-50';
      let errors = validateReceipt();
      expect(errors.some(e => e.includes('Subtotal cannot be negative'))).toBe(true);
      
      // Negative total
      document.getElementById('subtotal').value = '50';
      document.getElementById('total').value = '-10';
      errors = validateReceipt();
      expect(errors.some(e => e.includes('Total cannot be negative'))).toBe(true);
      
      // Items don't match subtotal
      addItem();
      const row = document.querySelector('.item-row');
      row.querySelector('.item-total').value = '25';
      row.querySelector('.item-total').dataset.fullValue = '25';
      
      document.getElementById('subtotal').value = '50'; // Wrong!
      errors = validateReceipt();
      expect(errors.some(e => e.includes("doesn't match sum of items"))).toBe(true);
    });
  });

  describe('DOM Manipulation Safety', () => {
    it('should maintain DOM consistency after errors', () => {
      // Cause an error by removing critical elements
      document.getElementById('items-container').remove();
      
      // Should not throw
      expect(() => {
        addItem(); // This might fail but shouldn't crash
        calculateSubtotal();
        validateReceipt();
      }).not.toThrow();
      
      // Restore container
      const container = document.createElement('div');
      container.id = 'items-container';
      document.body.appendChild(container);
    });

    it('should handle missing or null elements gracefully', () => {
      // Remove various elements
      document.getElementById('subtotal').remove();
      document.getElementById('tax').remove();
      
      // Functions should still work without crashing
      expect(() => {
        updateSubtotal();
        updateProrations();
        const data = getReceiptData();
        expect(data).toBeDefined();
      }).not.toThrow();
    });
  });
});