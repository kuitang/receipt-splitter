/**
 * REGRESSION TEST: Finalized claims must remain visible
 * This test ensures that after finalizing claims, they remain visible to:
 * - The person who finalized
 * - The uploader
 * - New viewers in new sessions
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

// Mock functions
global.alert = vi.fn();
global.confirm = vi.fn(() => true);
global.fetch = vi.fn();
global.authenticatedJsonFetch = vi.fn();
global.escapeHtml = (text) => text;

// Import module
const viewPageModule = await import('../../static/js/view-page.js');
const { updateItemClaims, updateFinalizationStatus } = viewPageModule;

describe('REGRESSION: Finalized Claims Visibility', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = '';
  });

  describe('Critical: Claims must remain visible after finalization', () => {
    it('should show claim inputs for viewer regardless of receipt finalization status', () => {
      // This tests that the template condition {% if viewer_name %} works
      // without requiring receipt.is_finalized
      
      document.body.innerHTML = `
        <div class="item-container" data-item-id="100">
          <h3>Pizza</h3>
          <div class="ml-4">
            <!-- Input should be here when viewer_name exists -->
          </div>
        </div>
      `;
      
      const itemsData = [{
        item_id: '100',
        available_quantity: 0,
        claims: [
          { claimer_name: 'Alice', quantity_claimed: 2 }
        ]
      }];
      
      // Update claims as Alice who has finalized
      updateItemClaims(itemsData, 'Alice', true);
      
      const container = document.querySelector('[data-item-id="100"]');
      const input = container.querySelector('.claim-quantity');
      
      // Input MUST exist and show Alice's claims
      expect(input).toBeTruthy();
      expect(input.value).toBe('2');
      expect(input.disabled).toBe(true); // Disabled because finalized
    });

    it('should show finalized claims to new viewers', () => {
      document.body.innerHTML = `
        <div class="item-container" data-item-id="200">
          <h3>Salad</h3>
          <div class="ml-4"></div>
        </div>
      `;
      
      const itemsData = [{
        item_id: '200',
        available_quantity: 1,
        claims: [
          { claimer_name: 'Bob', quantity_claimed: 1 }
        ]
      }];
      
      // New viewer "Charlie" viewing receipt with Bob's finalized claims
      updateItemClaims(itemsData, 'Charlie', false);
      
      const container = document.querySelector('[data-item-id="200"]');
      const input = container.querySelector('.claim-quantity');
      
      // Charlie should see input to make his own claims
      expect(input).toBeTruthy();
      expect(input.value).toBe('0'); // Charlie has no claims yet
      expect(input.disabled).toBe(false); // Charlie can still claim
      
      // Bob's claims should be visible in the claims display
      const claimsSection = container.querySelector('.border-t');
      expect(claimsSection).toBeTruthy();
      expect(claimsSection.textContent).toContain('Bob');
      expect(claimsSection.textContent).toContain('1');
    });

    it('should show all finalized claims to uploader', () => {
      document.body.innerHTML = `
        <div class="space-y-3">
          <div class="item-container" data-item-id="301">
            <h3>Burger</h3>
            <div class="ml-4"></div>
          </div>
          <div class="item-container" data-item-id="302">
            <h3>Fries</h3>
            <div class="ml-4"></div>
          </div>
        </div>
      `;
      
      const itemsData = [
        {
          item_id: '301',
          available_quantity: 0,
          claims: [
            { claimer_name: 'David', quantity_claimed: 1 }
          ]
        },
        {
          item_id: '302',
          available_quantity: 0,
          claims: [
            { claimer_name: 'Eve', quantity_claimed: 2 }
          ]
        }
      ];
      
      // Uploader viewing their receipt with multiple finalized claims
      updateItemClaims(itemsData, 'Uploader', false);
      
      // Check first item
      const item1 = document.querySelector('[data-item-id="301"]');
      const claims1 = item1.querySelector('.border-t');
      expect(claims1).toBeTruthy();
      expect(claims1.textContent).toContain('David');
      
      // Check second item
      const item2 = document.querySelector('[data-item-id="302"]');
      const claims2 = item2.querySelector('.border-t');
      expect(claims2).toBeTruthy();
      expect(claims2.textContent).toContain('Eve');
      
      // Uploader should see disabled inputs (can't claim on fully claimed items)
      const input1 = item1.querySelector('.claim-quantity');
      const input2 = item2.querySelector('.claim-quantity');
      expect(input1).toBeTruthy();
      expect(input2).toBeTruthy();
      expect(input1.disabled).toBe(true);
      expect(input2.disabled).toBe(true);
    });

    it('should maintain visibility through finalization process', () => {
      // Start with active claiming
      document.body.innerHTML = `
        <div class="sticky bottom-4 border-green-500">
          <p class="text-sm text-gray-600">Your Total (Frank)</p>
          <p id="my-total" class="text-green-600">$25.00</p>
          <button id="claim-button">Finalize Claims</button>
        </div>
        <div class="item-container" data-item-id="400">
          <h3>Steak</h3>
          <div class="ml-4">
            <div class="flex items-center space-x-2">
              <label class="text-sm text-gray-600">Claim:</label>
              <input type="number" class="claim-quantity border-gray-300" value="1" data-item-id="400">
            </div>
          </div>
        </div>
      `;
      
      const input = document.querySelector('.claim-quantity');
      expect(input).toBeTruthy();
      expect(input.disabled).toBe(false);
      expect(input.value).toBe('1');
      
      // Finalize claims
      updateFinalizationStatus(true);
      
      // After finalization, input should still exist but be disabled
      const finalizedInput = document.querySelector('.claim-quantity');
      expect(finalizedInput).toBeTruthy();
      expect(finalizedInput.disabled).toBe(true);
      expect(finalizedInput.value).toBe('1'); // Value preserved
      
      // UI should show finalized state
      const stickySection = document.querySelector('.sticky.bottom-4');
      expect(stickySection.classList.contains('border-blue-500')).toBe(true);
      
      const label = document.querySelector('label');
      expect(label.textContent).toBe('Claimed:');
    });
  });

  describe('Edge Cases', () => {
    it('should handle receipt with no claims yet', () => {
      document.body.innerHTML = `
        <div class="item-container" data-item-id="500">
          <h3>Dessert</h3>
          <div class="ml-4"></div>
        </div>
      `;
      
      const itemsData = [{
        item_id: '500',
        available_quantity: 3,
        claims: []
      }];
      
      updateItemClaims(itemsData, 'NewUser', false);
      
      const input = document.querySelector('.claim-quantity');
      expect(input).toBeTruthy();
      expect(input.disabled).toBe(false);
      expect(input.getAttribute('max')).toBe('3');
    });

    it('should handle mixed finalized and unfinalized users', () => {
      document.body.innerHTML = `
        <div class="item-container" data-item-id="600">
          <h3>Appetizer</h3>
          <div class="ml-4"></div>
        </div>
      `;
      
      const itemsData = [{
        item_id: '600',
        available_quantity: 1,
        claims: [
          { claimer_name: 'Grace', quantity_claimed: 2 } // Grace finalized
        ]
      }];
      
      // Henry viewing (not finalized)
      updateItemClaims(itemsData, 'Henry', false);
      
      const input = document.querySelector('.claim-quantity');
      expect(input).toBeTruthy();
      expect(input.disabled).toBe(false); // Henry can still claim
      
      // Grace's claims visible
      const claimsSection = document.querySelector('.border-t');
      expect(claimsSection.textContent).toContain('Grace (2)');
    });
  });
});