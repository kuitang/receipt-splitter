/**
 * Tests for consistent styling of fully claimed items
 * Ensures all scenarios result in the same disabled input appearance
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
global.escapeHtml = (text) => text; // Simple mock for escapeHtml

// Import module
const viewPageModule = await import('../../static/js/view-page.js');
const { updateItemClaims } = viewPageModule;

describe('Fully Claimed Items - Consistent Styling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = '';
  });

  describe('All fully claimed scenarios should have consistent disabled styling', () => {
    const expectedDisabledClasses = 'claim-quantity w-20 px-2 py-1 border rounded border-gray-200 bg-gray-50 text-gray-600';
    const expectedContainerOpacity = 'opacity-50';

    it('should show disabled input when item is fully claimed by others', () => {
      // Setup: Item fully claimed by other users
      document.body.innerHTML = `
        <div class="item-container" data-item-id="100">
          <div class="ml-4"></div>
        </div>
      `;

      const pollData = [{
        item_id: '100',
        available_quantity: 0,
        claims: [
          { claimer_name: 'Alice', quantity_claimed: 2 },
          { claimer_name: 'Bob', quantity_claimed: 1 }
        ]
      }];

      // Current user is 'Charlie' who has no claims
      updateItemClaims(pollData, 'Charlie', false);

      const container = document.querySelector('[data-item-id="100"]');
      const input = container.querySelector('.claim-quantity');

      // Assert: Should show disabled input with consistent styling
      expect(input).toBeTruthy();
      expect(input.className).toBe(expectedDisabledClasses);
      expect(input.disabled).toBe(true);
      expect(input.readOnly).toBe(true);
      expect(input.value).toBe('0');
      
      // Container should have opacity
      expect(container.classList.contains('opacity-50')).toBe(true);
    });

    it('should show disabled input when user has finalized their claims', () => {
      // Setup: User has finalized claims
      document.body.innerHTML = `
        <div class="item-container" data-item-id="200">
          <div class="ml-4"></div>
        </div>
      `;

      const pollData = [{
        item_id: '200',
        available_quantity: 2,
        claims: [
          { claimer_name: 'CurrentUser', quantity_claimed: 1 }
        ]
      }];

      // User is finalized (third parameter = true)
      updateItemClaims(pollData, 'CurrentUser', true);

      const container = document.querySelector('[data-item-id="200"]');
      const input = container.querySelector('.claim-quantity');

      // Assert: Should show disabled input with consistent styling
      expect(input).toBeTruthy();
      expect(input.className).toBe(expectedDisabledClasses);
      expect(input.disabled).toBe(true);
      expect(input.readOnly).toBe(true);
      
      // Container should NOT have opacity (user has claims)
      expect(container.classList.contains('opacity-50')).toBe(false);
    });

    it('should show disabled input when item has no availability and user has no claims', () => {
      // Setup: Mixed scenario - some claimed by user, some by others, none available
      document.body.innerHTML = `
        <div class="item-container" data-item-id="300">
          <div class="ml-4"></div>
        </div>
      `;

      const pollData = [{
        item_id: '300',
        available_quantity: 0,
        claims: [
          { claimer_name: 'Alice', quantity_claimed: 3 }
        ]
      }];

      // Current user has no claims on this item
      updateItemClaims(pollData, 'Bob', false);

      const container = document.querySelector('[data-item-id="300"]');
      const input = container.querySelector('.claim-quantity');

      // Assert: Disabled input with consistent styling
      expect(input).toBeTruthy();
      expect(input.className).toBe(expectedDisabledClasses);
      expect(input.disabled).toBe(true);
      expect(input.readOnly).toBe(true);
      
      // Container should have opacity
      expect(container.classList.contains('opacity-50')).toBe(true);
    });

    it('should show enabled input when item is available and user not finalized', () => {
      // Setup: Item has availability and user hasn't finalized
      document.body.innerHTML = `
        <div class="item-container" data-item-id="400">
          <div class="ml-4"></div>
        </div>
      `;

      const pollData = [{
        item_id: '400',
        available_quantity: 2,
        claims: [
          { claimer_name: 'Alice', quantity_claimed: 1 }
        ]
      }];

      // Current user can still claim
      updateItemClaims(pollData, 'Bob', false);

      const container = document.querySelector('[data-item-id="400"]');
      const input = container.querySelector('.claim-quantity');

      // Assert: Should show ENABLED input
      expect(input).toBeTruthy();
      expect(input.className).toBe('claim-quantity w-20 px-2 py-1 border border-gray-300 rounded');
      expect(input.disabled).toBe(false);
      expect(input.readOnly).toBe(false);
      
      // Container should NOT have opacity
      expect(container.classList.contains('opacity-50')).toBe(false);
    });

    it('should show enabled input when user has existing claims and more available', () => {
      // Setup: User has claims but can claim more
      document.body.innerHTML = `
        <div class="item-container" data-item-id="500">
          <div class="ml-4"></div>
        </div>
      `;

      const pollData = [{
        item_id: '500',
        available_quantity: 1,
        claims: [
          { claimer_name: 'CurrentUser', quantity_claimed: 1 }
        ]
      }];

      // User can claim more
      updateItemClaims(pollData, 'CurrentUser', false);

      const container = document.querySelector('[data-item-id="500"]');
      const input = container.querySelector('.claim-quantity');

      // Assert: Should show ENABLED input
      expect(input).toBeTruthy();
      expect(input.className).toBe('claim-quantity w-20 px-2 py-1 border border-gray-300 rounded');
      expect(input.disabled).toBe(false);
      expect(input.readOnly).toBe(false);
      expect(input.value).toBe('1'); // Shows existing claim
      
      // Container should NOT have opacity (user has claims)
      expect(container.classList.contains('opacity-50')).toBe(false);
    });

    it('should update existing input to disabled when it becomes fully claimed', () => {
      // Setup: Start with enabled input
      document.body.innerHTML = `
        <div class="item-container" data-item-id="600">
          <div class="ml-4">
            <div class="flex items-center space-x-2">
              <label class="text-sm text-gray-600">Claim:</label>
              <input type="number" 
                     class="claim-quantity w-20 px-2 py-1 border border-gray-300 rounded"
                     value="0"
                     data-item-id="600">
            </div>
          </div>
        </div>
      `;

      const container = document.querySelector('[data-item-id="600"]');
      let input = container.querySelector('.claim-quantity');
      
      // Initial state: enabled
      expect(input.disabled).toBe(false);
      expect(container.classList.contains('opacity-50')).toBe(false);

      // Update: Item becomes fully claimed
      const pollData = [{
        item_id: '600',
        available_quantity: 0,
        claims: [
          { claimer_name: 'Alice', quantity_claimed: 3 }
        ]
      }];

      updateItemClaims(pollData, 'Bob', false);

      input = container.querySelector('.claim-quantity');

      // Assert: Should now be disabled with consistent styling
      expect(input).toBeTruthy();
      expect(input.className).toBe(expectedDisabledClasses);
      expect(input.disabled).toBe(true);
      expect(input.readOnly).toBe(true);
      
      // Container should now have opacity
      expect(container.classList.contains('opacity-50')).toBe(true);
    });
  });

  describe('Edge cases', () => {
    it('should handle zero quantity items correctly', () => {
      document.body.innerHTML = `
        <div class="item-container" data-item-id="700">
          <div class="ml-4"></div>
        </div>
      `;

      const pollData = [{
        item_id: '700',
        available_quantity: 0,
        claims: []
      }];

      updateItemClaims(pollData, 'User', false);

      const container = document.querySelector('[data-item-id="700"]');
      const input = container.querySelector('.claim-quantity');

      // Should be disabled since nothing available
      expect(input.disabled).toBe(true);
      expect(container.classList.contains('opacity-50')).toBe(true);
    });

    it('should handle user with exact amount claimed as available', () => {
      document.body.innerHTML = `
        <div class="item-container" data-item-id="800">
          <div class="ml-4"></div>
        </div>
      `;

      const pollData = [{
        item_id: '800',
        available_quantity: 0,
        claims: [
          { claimer_name: 'User', quantity_claimed: 3 }
        ]
      }];

      // User claimed all, none left
      updateItemClaims(pollData, 'User', false);

      const container = document.querySelector('[data-item-id="800"]');
      const input = container.querySelector('.claim-quantity');

      // Should still be enabled since user has claims (can reduce)
      expect(input.disabled).toBe(false);
      expect(input.value).toBe('3');
      // Container should NOT have opacity (user has claims)
      expect(container.classList.contains('opacity-50')).toBe(false);
    });
  });
});