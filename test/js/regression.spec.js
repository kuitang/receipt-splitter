/**
 * CRITICAL: Regression tests for specific bugs that were fixed
 * These tests ensure critical issues don't regress - DO NOT DELETE
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { JSDOM } from 'jsdom';
import { testTemplates, setupTestTemplates } from './generated-templates.js';
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

// Note: Navigation errors in JSDOM are expected but handled with try-catch in the code

// Mock functions
global.alert = vi.fn();
global.confirm = vi.fn(() => true);
global.escapeHtml = vi.fn((text) => String(text).replace(/[&<>"']/g, ''));

// Import template utils (this attaches to window automatically)
await import('../../static/js/template-utils.js');

// Import modules
const viewPageModule = await import('../../static/js/view-page.js');

const {
  initializeViewPage,
  updateItemClaims,
  updateUIFromPollData,
  confirmClaims,
  updateFinalizationStatus,
  updateTotal,
  updateMyTotal,
  _setState
} = viewPageModule;

describe('REGRESSION TESTS - Critical Bug Prevention', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Bug: kuizy Fries Scenario (Protocol Mismatch)', () => {
    it('should allow user to claim additional items when they have existing claims', async () => {
      // The exact original bug: kuizy couldn't claim 2nd Fries
      setBodyHTML(`
        <div id="view-page-data" data-receipt-slug="test-receipt"></div>
        
        <!-- Fries item with kuizy's existing claim pre-populated -->
        <div class="item-container" data-item-id="142">
          <h3>Fries</h3>
          <div class="item-share-amount" data-amount="8.75"></div>
          <div class="ml-4">
            <div class="flex items-center space-x-2">
              <input type="number" class="claim-quantity" value="1" min="0" max="2" data-item-id="142">
            </div>
          </div>
        </div>
        
        <p class="text-sm text-gray-600 mb-1">Your Total (kuizy)</p>
        <p id="my-total">$8.75</p>
        <div id="claiming-validation-warning" class="hidden"></div>
      `);
      
      
      initializeViewPage();
      _setState({ receiptSlug: 'test-receipt' });
      
      // kuizy wants to claim 2 total Fries (increase from 1 to 2)
      const friesInput = document.querySelector('.claim-quantity[data-item-id="142"]');
      friesInput.value = '2';  // Total desired quantity
      
      // Mock successful finalization
      global.authenticatedJsonFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          finalized: true,
          claims_count: 1
        })
      });
      
      await confirmClaims();
      
      // Should send new total claims protocol format
      expect(global.authenticatedJsonFetch).toHaveBeenCalledWith('/claim/test-receipt/', {
        method: 'POST',
        body: JSON.stringify({
          claims: [
            { line_item_id: '142', quantity_numerator: 2, quantity: 2 }  // Total desired quantity (not incremental +1)
          ]
        })
      });
      
      // Should not show error (the original bug was claims being silently ignored)
      expect(global.alert).not.toHaveBeenCalled();
    });
  });

  describe('Bug: Frontend Total Calculation Double-Counting', () => {
    it('should prevent double-counting existing claims (vibes $22.60 vs $11.30 bug)', () => {
      // The exact bug from screenshot: vibes showed $22.60 instead of $11.30
      setBodyHTML(`
        <div class="item-container" data-item-id="180">
          <h3>Salad</h3>
          <div class="item-share-amount" data-amount="11.30"></div>
          <input type="number" class="claim-quantity" value="1" data-item-id="180">
        </div>
        <p id="my-total">$0.00</p>
      `);
      
      
      updateTotal();
      
      // Should show $11.30 (not $22.60 from double-counting)
      const totalElement = document.getElementById('my-total');
      expect(totalElement.textContent).toBe('$11.30');
      expect(totalElement.textContent).not.toBe('$22.60'); // Prevent regression
    });
  });

  describe('Bug: Polling Overwrites User Input State', () => {
    it('should preserve user input when polling updates arrive', () => {
      setBodyHTML(`
        <div class="item-container" data-item-id="142">
          <h3>Fries</h3>
          <div class="ml-4">
            <div class="flex items-center space-x-2">
              <input type="number" class="claim-quantity" value="1" max="2" data-item-id="142">
            </div>
          </div>
        </div>
      `);
      
      
      const input = document.querySelector('.claim-quantity');
      
      // User is actively editing - changes value to 2
      input.value = '2';
      
      // Polling update arrives for same item
      const pollData = [{
        item_id: '142',
        available_quantity: 1,
        claims: [{ claimer_name: 'kuizy', quantity_claimed: 1 }]
      }];
      
      updateItemClaims(pollData, 'kuizy', false);
      
      // User's input should be preserved (not reset to 1)
      expect(input.value).toBe('2');
      expect(input.getAttribute('max')).toBe('2'); // 1 existing + 1 available
    });
    
    it('should preserve local total calculation when server returns 0 before finalization', () => {
      // Setup DOM with claim button visible (not finalized)
      setBodyHTML(`
        <div id="my-total">$25.50</div>
        <button id="claim-button" style="display: block;">Finalize Claims</button>
      `);
      
      
      // Simulate polling with server returning 0 (no finalized claims)
      updateMyTotal(0);
      
      // Assert: Local total should be preserved
      const totalElement = document.getElementById('my-total');
      expect(totalElement.textContent).toBe('$25.50');
      expect(totalElement.textContent).not.toBe('$0.00');
    });
    
    it('should use server total when user has finalized claims', () => {
      // Setup DOM with claim button hidden (finalized)
      setBodyHTML(`
        <div class="wrapper">
          <div id="my-total">$25.50</div>
          <button id="claim-button" style="display: none;">Finalize Claims</button>
          <div class="text-center">
            <p class="text-sm text-blue-600 font-medium">Claims Finalized</p>
          </div>
        </div>
      `);
      
      
      // Move button into wrapper with finalized indicator (can't mock parentElement directly)
      const wrapper = document.querySelector('.wrapper');
      const button = document.getElementById('claim-button');
      wrapper.appendChild(button);
      
      // Simulate polling with server returning actual total
      updateMyTotal(30.75);
      
      // Assert: Should use server total when finalized
      const totalElement = document.getElementById('my-total');
      expect(totalElement.textContent).toBe('$30.75');
    });
    
    it('should use server total when it is non-zero', () => {
      // Setup DOM with claim button visible (not finalized)
      setBodyHTML(`
        <div id="my-total">$0.00</div>
        <button id="claim-button" style="display: block;">Finalize Claims</button>
      `);
      
      
      // Simulate polling with server returning non-zero total
      updateMyTotal(15.25);
      
      // Assert: Should use server's non-zero total
      const totalElement = document.getElementById('my-total');
      expect(totalElement.textContent).toBe('$15.25');
    });
  });

  describe('Bug: "Fully Claimed" Logic and Styling', () => {
    it('should show disabled input when user has no claims and no availability', () => {
      setBodyHTML(`
        <div class="item-container" data-item-id="142">
          <div class="ml-4">
            <div class="flex items-center space-x-2">
              <input class="claim-quantity" data-item-id="142">
            </div>
          </div>
        </div>
        <div class="item-container" data-item-id="143">
          <div class="ml-4">
            <div class="flex items-center space-x-2">
              <input class="claim-quantity" data-item-id="143">
            </div>
          </div>
        </div>
      `);
      
      
      // Case 1: User has existing claims, item has no availability
      // Should show input (not "Fully Claimed") because user has existing claims
      const pollData1 = [{
        item_id: '142',
        available_quantity: 0,
        claims: [{ claimer_name: 'kuizy', quantity_claimed: 1 }]  // User has claims
      }];
      
      updateItemClaims(pollData1, 'kuizy', false);
      
      const item142Container = document.querySelector('[data-item-id="142"]');
      const input142 = item142Container.querySelector('.claim-quantity');
      expect(input142).toBeTruthy(); // Should show input
      expect(input142.disabled).toBe(false); // Should be enabled (user has claims)
      
      // Case 2: User has no claims, item has no availability  
      // Should show disabled input
      const pollData2 = [{
        item_id: '143',
        available_quantity: 0,
        claims: [{ claimer_name: 'someone_else', quantity_claimed: 2 }]  // Others claimed all
      }];
      
      updateItemClaims(pollData2, 'kuizy', false);
      
      const item143Container = document.querySelector('[data-item-id="143"]');
      const input143 = item143Container.querySelector('.claim-quantity');
      expect(input143).toBeTruthy(); // Should show input
      expect(input143.disabled).toBe(true); // Should be disabled
      expect(input143.className).toContain('bg-gray-50'); // Should have grey styling
    });

    it('should use consistent grey styling for disabled items', () => {
      setBodyHTML(`
        <div class="item-container" data-item-id="142">
          <div class="ml-4">
            <div class="flex items-center space-x-2">
              <input class="claim-quantity" data-item-id="142">
            </div>
          </div>
        </div>
      `);
      
      
      const pollData = [{
        item_id: '142',
        available_quantity: 0,
        claims: [{ claimer_name: 'someone_else', quantity_claimed: 1 }]
      }];
      
      updateItemClaims(pollData, 'kuizy', false);
      
      const itemContainer = document.querySelector('[data-item-id="142"]');
      const input = itemContainer.querySelector('.claim-quantity');
      
      // Should show disabled input with grey styling
      expect(input).toBeTruthy();
      expect(input.disabled).toBe(true);
      expect(input.className).toContain('bg-gray-50');
      expect(input.className).toContain('text-gray-600');
      expect(itemContainer.classList.contains('opacity-50')).toBe(true);
    });
  });

  describe('Bug: Confusing UI Text Removed', () => {
    it('should not show confusing "of X" text after polling updates', () => {
      setBodyHTML(`
        <div class="item-container" data-item-id="142">
          <div class="ml-4">
            <div class="flex items-center space-x-2">
              <input type="number" class="claim-quantity" value="1" data-item-id="142">
              <span class="text-sm text-gray-600">of 2</span>
            </div>
          </div>
        </div>
      `);
      
      
      const pollData = [{
        item_id: '142',
        available_quantity: 1,
        claims: [{ claimer_name: 'kuizy', quantity_claimed: 1 }]
      }];
      
      updateItemClaims(pollData, 'kuizy', false);
      
      // "of X" text should be removed by polling updates
      const container = document.querySelector('[data-item-id="142"]');
      expect(container.textContent).not.toContain('of ');
    });
  });

  describe('Bug: Single Modal Confirmation', () => {
    it('should show only one confirmation modal when finalizing', async () => {
      setBodyHTML(`
        <div id="view-page-data" data-receipt-slug="test-receipt"></div>
        <div class="item-container" data-item-id="142">
          <h3>Fries</h3>
          <div class="item-share-amount" data-amount="8.75"></div>
          <input type="number" class="claim-quantity" value="1" min="0" max="2" data-item-id="142">
        </div>
        <p id="my-total">$8.75</p>
        <div id="claiming-validation-warning" class="hidden"></div>
      `);
      
      
      initializeViewPage();
      _setState({ receiptSlug: 'test-receipt' });
      
      global.authenticatedJsonFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true, finalized: true, claims_count: 1 })
      });
      
      await confirmClaims();
      
      // Should have exactly one confirm() call, no alert() calls for success
      expect(global.confirm).toHaveBeenCalledTimes(1);
      expect(global.alert).not.toHaveBeenCalled();
    });
  });

  describe('Bug: Finalization State Management', () => {
    it('should lock UI after finalization via polling', () => {
      setBodyHTML(`
        <div class="sticky bottom-4 border-green-500">
          <p class="text-sm text-gray-600">Your Total (kuizy)</p>
          <p id="my-total" class="text-green-600">$15.50</p>
          <button id="claim-button">Finalize Claims</button>
        </div>
        <div class="item-container" data-item-id="142">
          <div class="ml-4">
            <div class="flex items-center space-x-2">
              <label class="text-sm text-gray-600">Claim:</label>
              <input type="number" class="claim-quantity border-gray-300" value="1" data-item-id="142">
            </div>
          </div>
        </div>
      `);
      
      
      // Simulate finalization via polling
      updateFinalizationStatus(true);
      
      // UI should be locked
      const stickySection = document.querySelector('.sticky.bottom-4');
      expect(stickySection.classList.contains('border-blue-500')).toBe(true);
      expect(stickySection.classList.contains('border-green-500')).toBe(false);
      
      const totalElement = document.getElementById('my-total');
      expect(totalElement.classList.contains('text-blue-600')).toBe(true);
      expect(totalElement.classList.contains('text-green-600')).toBe(false);
      
      const input = document.querySelector('.claim-quantity');
      expect(input.readOnly).toBe(true);
      expect(input.classList.contains('bg-gray-50')).toBe(true);
      
      const label = document.querySelector('label');
      expect(label.textContent).toBe('Claimed:');
      
      expect(document.getElementById('claim-button')).toBeFalsy(); // Button should be replaced
    });
  });

  describe('Bug: Real-time Update State Preservation', () => {
    it('should preserve user input during polling when user is actively editing', () => {
      setBodyHTML(`
        <div class="space-y-2">
          <div class="flex justify-between items-center">
            <span class="text-gray-700">Alice</span>
            <span class="font-medium tabular-nums">$10.00</span>
          </div>
        </div>
        
        <div class="item-container" data-item-id="142">
          <h3>Fries</h3>
          <div class="ml-4">
            <div class="flex items-center space-x-2">
              <label class="text-sm text-gray-600">Claim:</label>
              <input type="number" class="claim-quantity" value="1" max="2" data-item-id="142">
            </div>
          </div>
        </div>
        
        <div class="sticky bottom-4">
          <p class="text-sm text-gray-600">Your Total (kuizy)</p>
          <p id="my-total">$8.75</p>
        </div>
      `);
      
      
      const input = document.querySelector('.claim-quantity');
      
      // User is editing - changes from 1 to 2
      input.value = '2';
      
      // Real-time polling update arrives
      const pollData = {
        success: true,
        viewer_name: 'kuizy',
        is_finalized: false,
        participant_totals: [
          { name: 'Alice', amount: 15.00 },  // Alice made changes
          { name: 'kuizy', amount: 8.75 }
        ],
        total_claimed: 23.75,
        total_unclaimed: 21.25,
        my_total: 8.75,
        items_with_claims: [{
          item_id: '142',
          available_quantity: 1,
          claims: [{ claimer_name: 'kuizy', quantity_claimed: 1 }]
        }]
      };
      
      updateUIFromPollData(pollData);
      
      // User's input should be preserved (not reset to 1)
      expect(input.value).toBe('2');
      
      // Participant totals should update
      const participantsDiv = document.querySelector('.space-y-2');
      expect(participantsDiv.textContent).toContain('Alice');
      expect(participantsDiv.textContent).toContain('$15.00');
    });

    it('should handle complete real-time update cycle with fully claimed items', () => {
      // Test the full polling cycle including "Fully Claimed" transitions
      setBodyHTML(`
        <div class="space-y-2">
          <div class="flex justify-between items-center">
            <span class="text-gray-700">kuizy</span>
            <span class="font-medium tabular-nums">$8.75</span>
          </div>
        </div>
        
        <div class="item-container" data-item-id="141">
          <h3>Burger</h3>
          <div class="ml-4">
            <div class="flex items-center space-x-2">
              <label class="text-sm text-gray-600">Claim:</label>
              <input type="number" class="claim-quantity" value="0" max="1" data-item-id="141">
            </div>
          </div>
        </div>
        
        <div class="item-container" data-item-id="142">
          <h3>Fries</h3>
          <div class="ml-4">
            <div class="flex items-center space-x-2">
              <label class="text-sm text-gray-600">Claim:</label>
              <input type="number" class="claim-quantity" value="1" max="2" data-item-id="142">
            </div>
          </div>
        </div>
      `);
      
      
      // kuizy increases Fries to 2
      const friesInput = document.querySelector('.claim-quantity[data-item-id="142"]');
      friesInput.value = '2';
      
      // Real-time update: Alice claims Burger, making it unavailable to kuizy
      const pollData = {
        success: true,
        viewer_name: 'kuizy',
        is_finalized: false,
        participant_totals: [
          { name: 'Alice', amount: 25.00 },
          { name: 'kuizy', amount: 8.75 }
        ],
        total_claimed: 33.75,
        total_unclaimed: 11.25,
        my_total: 8.75,
        items_with_claims: [
          {
            item_id: '141',
            available_quantity: 0,  // Alice claimed it
            claims: [{ claimer_name: 'Alice', quantity_claimed: 1 }]  // Not kuizy
          },
          {
            item_id: '142',
            available_quantity: 1,  // Still available
            claims: [{ claimer_name: 'kuizy', quantity_claimed: 1 }]
          }
        ]
      };
      
      updateUIFromPollData(pollData);
      
      // kuizy's Fries input should be preserved
      expect(friesInput.value).toBe('2');
      expect(friesInput.getAttribute('max')).toBe('2'); // 1 existing + 1 available
      
      // Burger should become disabled (kuizy has no claims, no availability)
      const burgerContainer = document.querySelector('[data-item-id="141"]');
      const burgerInput = burgerContainer.querySelector('.claim-quantity');
      expect(burgerInput).toBeTruthy();
      expect(burgerInput.disabled).toBe(true);
      expect(burgerContainer.classList.contains('opacity-50')).toBe(true);
      
      // Participant totals should update
      const participantsDiv = document.querySelector('.space-y-2');
      expect(participantsDiv.textContent).toContain('Alice');
      expect(participantsDiv.textContent).toContain('$25.00');
    });
  });
});
