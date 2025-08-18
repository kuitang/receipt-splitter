/**
 * Shared test utilities and helpers for all JavaScript unit tests
 * Reduces duplication and provides consistent test patterns
 */

import { vi } from 'vitest';
import { JSDOM } from 'jsdom';

// =============================================================================
// DOM ENVIRONMENT SETUP
// =============================================================================

/**
 * Creates and configures a JSDOM environment for testing
 * @returns {JSDOM} Configured JSDOM instance
 */
export function createTestDOM() {
  const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
    url: 'http://localhost',
    pretendToBeVisual: true,
    resources: 'usable'
  });

  global.window = dom.window;
  global.document = window.document;
  global.navigator = window.navigator;

  return dom;
}

/**
 * Sets up common mock functions used across tests
 */
export function setupMocks() {
  global.alert = vi.fn();
  global.confirm = vi.fn(() => true);
  global.QRCode = { toCanvas: vi.fn() };
  
  global.escapeHtml = vi.fn((text) => {
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  });

  global.authenticatedFetch = vi.fn();
  global.authenticatedJsonFetch = vi.fn();
  global.copyShareUrl = vi.fn();
  global.getCookie = vi.fn();
  global.getCsrfToken = vi.fn();
  
  return {
    alert: global.alert,
    confirm: global.confirm,
    escapeHtml: global.escapeHtml,
    authenticatedFetch: global.authenticatedFetch,
    authenticatedJsonFetch: global.authenticatedJsonFetch
  };
}

/**
 * Sets up global utility functions from utils.js
 */
export async function setupUtilsGlobals() {
  const utilsModule = await import('../../static/js/utils.js');
  
  global.escapeHtml = utilsModule.escapeHtml;
  global.authenticatedFetch = utilsModule.authenticatedFetch;
  global.authenticatedJsonFetch = utilsModule.authenticatedJsonFetch;
  global.copyShareUrl = utilsModule.copyShareUrl;
  global.getCookie = utilsModule.getCookie;
  global.getCsrfToken = utilsModule.getCsrfToken;
  
  return utilsModule;
}

// =============================================================================
// DOM TEMPLATE BUILDERS
// =============================================================================

/**
 * Creates the edit page DOM structure
 */
export function createEditPageDOM(options = {}) {
  const {
    receiptSlug = 'test-receipt',
    receiptId = '123',
    isProcessing = false,
    restaurantName = 'Test Restaurant',
    subtotal = '0',
    tax = '0',
    tip = '0',
    total = '0'
  } = options;

  return `
    <div id="edit-page-data" 
         data-receipt-slug="${receiptSlug}" 
         data-receipt-id="${receiptId}"
         data-is-processing="${isProcessing}">
    </div>
    <div id="balance-warning" class="hidden"></div>
    <div id="balance-error-details"></div>
    <input id="restaurant_name" value="${restaurantName}">
    <input id="subtotal" type="number" value="${subtotal}">
    <input id="tax" type="number" value="${tax}">
    <input id="tip" type="number" value="${tip}">
    <input id="total" type="number" value="${total}">
    <div id="items-container"></div>
    <button data-action="finalize">Finalize & Share</button>
  `;
}

/**
 * Creates the view page DOM structure
 */
export function createViewPageDOM(options = {}) {
  const {
    receiptSlug = 'test-receipt',
    receiptId = '123',
    items = [],
    myTotal = '0.00',
    existingTotal = '0.00',
    includePollingElements = false
  } = options;

  let itemsHTML = items.map(item => createItemContainer(item)).join('\n');
  
  let pollingHTML = '';
  if (includePollingElements) {
    pollingHTML = `
      <div class="space-y-2">
        <div class="flex justify-between items-center">
          <span class="text-gray-700">Alice</span>
          <span class="font-medium tabular-nums">$15.50</span>
        </div>
        <div class="flex justify-between items-center text-orange-600 font-medium">
          <span>Not Claimed</span>
          <span class="tabular-nums">$10.25</span>
        </div>
        <p class="text-gray-400 italic">No items claimed yet</p>
      </div>
    `;
  }

  return `
    <div id="view-page-data" 
         data-receipt-slug="${receiptSlug}" 
         data-receipt-id="${receiptId}">
    </div>
    
    ${pollingHTML}
    
    <div class="items-container">
      ${itemsHTML}
    </div>
    
    <div id="claiming-warning" class="hidden">
      <div id="claiming-error-details"></div>
    </div>
    
    <p id="my-total" data-existing-total="${existingTotal}">$${myTotal}</p>
    <button id="claim-button" data-action="confirm-claims" disabled>Finalize Claims</button>
  `;
}

/**
 * Creates an item container for view page
 */
export function createItemContainer(options = {}) {
  const {
    itemId,
    name,
    shareAmount,
    quantity = 0,
    min = 0,
    max = 2,
    fullyClaimed = false,
    claims = []
  } = options;

  let claimSection = '';
  if (fullyClaimed) {
    claimSection = '<span class="text-orange-600 font-semibold">Fully Claimed</span>';
  } else {
    claimSection = `
      <div class="flex items-center space-x-2">
        <input type="number" class="claim-quantity" 
               data-item-id="${itemId}" min="${min}" max="${max}" value="${quantity}">
      </div>
    `;
  }

  let claimsDisplay = '';
  if (claims.length > 0) {
    const claimTags = claims.map(c => 
      `<span class="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">${c.name} (${c.qty})</span>`
    ).join('\n');
    
    claimsDisplay = `
      <div class="mt-3 pt-3 border-t">
        <p class="text-sm text-gray-600 mb-1">Claimed by:</p>
        <div class="flex flex-wrap gap-2">
          ${claimTags}
        </div>
      </div>
    `;
  }

  return `
    <div class="item-container" data-item-id="${itemId}">
      <h3>${name}</h3>
      <div class="item-share-amount" data-amount="${shareAmount}"></div>
      <div class="ml-4">
        ${claimSection}
      </div>
      ${claimsDisplay}
    </div>
  `;
}

/**
 * Creates an item row for edit page
 */
export function createItemRow(options = {}) {
  const {
    name = '',
    quantity = 1,
    price = 0,
    total = 0
  } = options;

  const itemRow = document.createElement('div');
  itemRow.className = 'item-row';
  
  // Create inputs individually to avoid HTML parsing issues with special characters
  const nameInput = document.createElement('input');
  nameInput.className = 'item-name';
  nameInput.value = name;
  
  const qtyInput = document.createElement('input');
  qtyInput.className = 'item-quantity';
  qtyInput.type = 'number';
  qtyInput.value = quantity;
  
  const priceInput = document.createElement('input');
  priceInput.className = 'item-price';
  priceInput.type = 'number';
  priceInput.value = price;
  
  const totalInput = document.createElement('input');
  totalInput.className = 'item-total';
  totalInput.type = 'number';
  totalInput.value = total;
  totalInput.dataset.fullValue = total;
  
  const proration = document.createElement('div');
  proration.className = 'item-proration';
  
  const removeBtn = document.createElement('button');
  removeBtn.setAttribute('data-action', 'remove-item');
  removeBtn.textContent = 'Remove';
  
  itemRow.appendChild(nameInput);
  itemRow.appendChild(qtyInput);
  itemRow.appendChild(priceInput);
  itemRow.appendChild(totalInput);
  itemRow.appendChild(proration);
  itemRow.appendChild(removeBtn);
  
  return itemRow;
}

// =============================================================================
// TEST DATA FACTORIES
// =============================================================================

/**
 * Creates test item data
 */
export function createTestItem(overrides = {}) {
  return {
    name: 'Test Item',
    quantity: 1,
    unit_price: 10.00,
    total_price: 10.00,
    ...overrides
  };
}

/**
 * Creates test claim data
 */
export function createTestClaim(overrides = {}) {
  return {
    line_item_id: '1',
    quantity: 1,
    claimer_name: 'Test User',
    ...overrides
  };
}

/**
 * Creates test poll data
 */
export function createPollData(overrides = {}) {
  return {
    success: true,
    viewer_name: 'TestUser',
    is_finalized: false,
    participant_totals: [],
    total_claimed: 0,
    total_unclaimed: 0,
    my_total: 0,
    items_with_claims: [],
    ...overrides
  };
}

/**
 * List of XSS attack vectors for security testing
 */
export const XSS_PAYLOADS = [
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
  '<input autofocus onfocus=alert(1)>'
];

/**
 * List of malformed inputs for fuzzing tests
 */
export const FUZZ_INPUTS = [
  'NaN',
  'Infinity',
  '-Infinity',
  '1.2.3.4',
  '1,234,567.89',
  '1e308',
  '1e-308',
  '0x1234',
  '0o777',
  '0b1010',
  '💰💰💰',
  '\\x00',
  '"><script>',
  '../../../etc/passwd',
  'Robert"); DROP TABLE items;--'
];

// =============================================================================
// ASSERTION HELPERS
// =============================================================================

/**
 * Asserts that an element has specific CSS classes
 */
export function assertHasClasses(element, classes) {
  classes.forEach(cls => {
    if (!element.classList.contains(cls)) {
      throw new Error(`Element missing class "${cls}"`);
    }
  });
}

/**
 * Asserts that an element does not have specific CSS classes
 */
export function assertNotHasClasses(element, classes) {
  classes.forEach(cls => {
    if (element.classList.contains(cls)) {
      throw new Error(`Element should not have class "${cls}"`);
    }
  });
}

/**
 * Asserts validation error state on an input
 */
export function assertValidationError(input, hasError = true) {
  if (hasError) {
    assertHasClasses(input, ['border-red-500', 'bg-red-50']);
  } else {
    assertNotHasClasses(input, ['border-red-500', 'bg-red-50']);
  }
}

/**
 * Asserts the visibility of an element based on 'hidden' class
 */
export function assertVisible(element, shouldBeVisible = true) {
  const isHidden = element.classList.contains('hidden');
  if (shouldBeVisible && isHidden) {
    throw new Error('Element should be visible but has "hidden" class');
  }
  if (!shouldBeVisible && !isHidden) {
    throw new Error('Element should be hidden but lacks "hidden" class');
  }
}

/**
 * Gets all item rows from edit page
 */
export function getItemRows() {
  return document.querySelectorAll('.item-row');
}

/**
 * Gets all claim inputs from view page
 */
export function getClaimInputs() {
  return document.querySelectorAll('.claim-quantity');
}

/**
 * Sets claim input value and returns the input
 */
export function setClaim(itemId, value) {
  const input = document.querySelector(`.claim-quantity[data-item-id="${itemId}"]`);
  if (input) {
    input.value = value;
  }
  return input;
}

/**
 * Adds an item row to edit page container
 */
export function addItemToContainer(itemData = {}) {
  const container = document.getElementById('items-container');
  if (container) {
    const row = createItemRow(itemData);
    container.appendChild(row);
    return row;
  }
  return null;
}

// =============================================================================
// MOCK RESPONSE BUILDERS
// =============================================================================

/**
 * Creates a mock successful API response
 */
export function mockSuccessResponse(data = {}) {
  return {
    ok: true,
    json: () => Promise.resolve({ success: true, ...data })
  };
}

/**
 * Creates a mock error API response
 */
export function mockErrorResponse(error = 'Error occurred', status = 400) {
  return {
    ok: false,
    status,
    json: () => Promise.resolve({ error })
  };
}

/**
 * Sets up a mock for authenticatedJsonFetch
 */
export function mockAuthFetch(responseOrFunction) {
  if (typeof responseOrFunction === 'function') {
    global.authenticatedJsonFetch = vi.fn(responseOrFunction);
  } else {
    global.authenticatedJsonFetch = vi.fn().mockResolvedValue(responseOrFunction);
  }
  return global.authenticatedJsonFetch;
}

// =============================================================================
// COMMON TEST PATTERNS
// =============================================================================

/**
 * Tests input validation flow
 */
export async function testValidationFlow(options) {
  const {
    setInvalidValue,
    validateFn,
    expectedError,
    setValidValue,
    element = null
  } = options;

  // Set invalid value
  setInvalidValue();
  const isValid = validateFn();
  
  // Check validation failed
  if (isValid !== false) {
    throw new Error('Validation should have failed');
  }

  // Check error display
  if (element) {
    assertValidationError(element, true);
  }

  if (expectedError) {
    const errorDetails = document.getElementById('claiming-error-details');
    if (!errorDetails.innerHTML.includes(expectedError)) {
      throw new Error(`Expected error message not found: ${expectedError}`);
    }
  }

  // Fix the value
  if (setValidValue) {
    setValidValue();
    const isValidNow = validateFn();
    
    if (isValidNow !== true) {
      throw new Error('Validation should pass after fix');
    }

    if (element) {
      assertValidationError(element, false);
    }
  }
}

/**
 * Tests button state management
 */
export function testButtonState(options) {
  const {
    button,
    shouldBeDisabled,
    setupState,
    updateStateFn
  } = options;

  if (setupState) setupState();
  if (updateStateFn) updateStateFn();

  if (button.disabled !== shouldBeDisabled) {
    throw new Error(`Button should be ${shouldBeDisabled ? 'disabled' : 'enabled'}`);
  }
}

/**
 * Waits for async operations with timeout
 */
export function waitFor(conditionFn, timeout = 1000) {
  return new Promise((resolve, reject) => {
    const startTime = Date.now();
    
    const check = () => {
      if (conditionFn()) {
        resolve();
      } else if (Date.now() - startTime > timeout) {
        reject(new Error('Timeout waiting for condition'));
      } else {
        setTimeout(check, 10);
      }
    };
    
    check();
  });
}

// =============================================================================
// CLEANUP UTILITIES
// =============================================================================

/**
 * Resets all mocks and clears DOM
 */
export function resetTestEnvironment() {
  vi.clearAllMocks();
  document.body.innerHTML = '';
}

/**
 * Removes all event listeners from an element and its children
 */
export function removeAllListeners(element) {
  const newElement = element.cloneNode(true);
  element.parentNode.replaceChild(newElement, element);
  return newElement;
}