/**
 * Shared test utilities for JavaScript unit tests
 */

import { vi } from 'vitest';
import { JSDOM } from 'jsdom';

// DOM Setup
export function createTestDOM() {
  const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
    url: 'http://localhost',
    pretendToBeVisual: true,
    resources: 'usable'
  });
  Object.assign(global, { window: dom.window, document: dom.window.document, navigator: dom.window.navigator });
  return dom;
}

// Mock Setup
export function setupMocks() {
  const mocks = {
    alert: vi.fn(),
    confirm: vi.fn(() => true),
    QRCode: { toCanvas: vi.fn() },
    escapeHtml: vi.fn(text => String(text).replace(/[&<>"']/g, m => 
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]))),
    authenticatedFetch: vi.fn(),
    authenticatedJsonFetch: vi.fn(),
    copyShareUrl: vi.fn(),
    getCookie: vi.fn(),
    getCsrfToken: vi.fn(),
    fetch: vi.fn()
  };
  Object.assign(global, mocks);
  return mocks;
}

export async function setupUtilsGlobals() {
  const utils = await import('../../static/js/utils.js');
  Object.assign(global, utils);
  return utils;
}

// DOM Templates
export function createEditPageDOM(opts = {}) {
  const o = { receiptSlug: 'test-receipt', receiptId: '123', isProcessing: false,
    restaurantName: 'Test Restaurant', subtotal: '0', tax: '0', tip: '0', total: '0', ...opts };
  return `
    <div id="edit-page-data" data-receipt-slug="${o.receiptSlug}" 
         data-receipt-id="${o.receiptId}" data-is-processing="${o.isProcessing}"></div>
    <div id="balance-warning" class="hidden"></div>
    <div id="balance-error-details"></div>
    <input id="restaurant_name" value="${o.restaurantName}">
    <input id="subtotal" type="number" value="${o.subtotal}">
    <input id="tax" type="number" value="${o.tax}">
    <input id="tip" type="number" value="${o.tip}">
    <input id="total" type="number" value="${o.total}">
    <div id="items-container"></div>
    <button data-action="finalize">Finalize & Share</button>`;
}

export function createViewPageDOM(opts = {}) {
  const o = { receiptSlug: 'test-receipt', receiptId: '123', items: [], 
    myTotal: '0.00', existingTotal: '0.00', includePollingElements: false, ...opts };
  
  const polling = o.includePollingElements ? `
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
    </div>` : '';

  return `
    <div id="view-page-data" data-receipt-slug="${o.receiptSlug}" data-receipt-id="${o.receiptId}"></div>
    ${polling}
    <div class="items-container">
      ${o.items.map(createItemContainer).join('\n')}
    </div>
    <div id="claiming-warning" class="hidden">
      <div id="claiming-error-details"></div>
    </div>
    <p id="my-total" data-existing-total="${o.existingTotal}">$${o.myTotal}</p>
    <button id="claim-button" data-action="confirm-claims" disabled>Finalize Claims</button>`;
}

export function createItemContainer(opts = {}) {
  const o = { itemId: '', name: '', shareAmount: '', quantity: 0, min: 0, max: 2, 
    fullyClaimed: false, claims: [], ...opts };
  
  const claimSection = o.fullyClaimed 
    ? '<span class="text-orange-600 font-semibold">Fully Claimed</span>'
    : `<div class="flex items-center space-x-2">
        <input type="number" class="claim-quantity" data-item-id="${o.itemId}" 
               min="${o.min}" max="${o.max}" value="${o.quantity}">
      </div>`;
  
  const claimsDisplay = o.claims.length ? `
    <div class="mt-3 pt-3 border-t">
      <p class="text-sm text-gray-600 mb-1">Claimed by:</p>
      <div class="flex flex-wrap gap-2">
        ${o.claims.map(c => 
          `<span class="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">${c.name} (${c.qty})</span>`
        ).join('\n')}
      </div>
    </div>` : '';

  return `
    <div class="item-container" data-item-id="${o.itemId}">
      <h3>${o.name}</h3>
      <div class="item-share-amount" data-amount="${o.shareAmount}"></div>
      <div class="ml-4">${claimSection}</div>
      ${claimsDisplay}
    </div>`;
}

export function createItemRow(opts = {}) {
  const o = { name: '', quantity: 1, price: 0, total: 0, ...opts };
  const row = document.createElement('div');
  row.className = 'item-row';
  
  const inputs = [
    ['input', 'item-name', o.name],
    ['input', 'item-quantity', o.quantity, 'number'],
    ['input', 'item-price', o.price, 'number'],
    ['input', 'item-total', o.total, 'number', { 'data-full-value': o.total }],
    ['div', 'item-proration'],
    ['button', null, 'Remove', null, { 'data-action': 'remove-item' }]
  ];
  
  inputs.forEach(([tag, cls, val, type, attrs]) => {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (type) el.type = type;
    if (val !== undefined) el[tag === 'input' ? 'value' : 'textContent'] = val;
    if (attrs) Object.entries(attrs).forEach(([k, v]) => {
      if (k.startsWith('data-')) {
        el.dataset[k.slice(5).replace(/-(.)/g, (_, c) => c.toUpperCase())] = v;
      } else {
        el.setAttribute(k, v);
      }
    });
    row.appendChild(el);
  });
  
  return row;
}

// Test Data
export const createTestItem = (o = {}) => ({ 
  name: 'Test Item', quantity: 1, unit_price: 10, total_price: 10, ...o 
});

export const createTestClaim = (o = {}) => ({ 
  line_item_id: '1', quantity: 1, claimer_name: 'Test User', ...o 
});

export const createPollData = (o = {}) => ({
  success: true, viewer_name: 'TestUser', is_finalized: false,
  participant_totals: [], total_claimed: 0, total_unclaimed: 0,
  my_total: 0, items_with_claims: [], ...o
});

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

export const FUZZ_INPUTS = [
  'NaN', 'Infinity', '-Infinity', '1.2.3.4', '1,234,567.89',
  '1e308', '1e-308', '0x1234', '0o777', '0b1010', '💰💰💰',
  '\\x00', '"><script>', '../../../etc/passwd', 'Robert"); DROP TABLE items;--'
];

// Assertions
const checkClasses = (el, classes, should) => classes.forEach(cls => {
  if (el.classList.contains(cls) !== should) 
    throw new Error(`Element ${should ? 'missing' : 'should not have'} class "${cls}"`);
});

export const assertHasClasses = (el, classes) => checkClasses(el, classes, true);
export const assertNotHasClasses = (el, classes) => checkClasses(el, classes, false);

export function assertValidationError(input, hasError = true) {
  checkClasses(input, ['border-red-500', 'bg-red-50'], hasError);
}

export function assertVisible(el, shouldBeVisible = true) {
  const hidden = el.classList.contains('hidden');
  if (shouldBeVisible === hidden) 
    throw new Error(`Element should be ${shouldBeVisible ? 'visible' : 'hidden'}`);
}

// DOM Helpers
export const getItemRows = () => document.querySelectorAll('.item-row');
export const getClaimInputs = () => document.querySelectorAll('.claim-quantity');

export function setClaim(itemId, value) {
  const input = document.querySelector(`.claim-quantity[data-item-id="${itemId}"]`);
  if (input) input.value = value;
  return input;
}

export function addItemToContainer(itemData = {}) {
  const container = document.getElementById('items-container');
  if (!container) return null;
  const row = createItemRow(itemData);
  container.appendChild(row);
  return row;
}

// Mock Responses
export const mockSuccessResponse = (data = {}) => ({
  ok: true,
  json: () => Promise.resolve({ success: true, ...data })
});

export const mockErrorResponse = (error = 'Error occurred', status = 400) => ({
  ok: false,
  status,
  json: () => Promise.resolve({ error })
});

export function mockAuthFetch(responseOrFn) {
  global.authenticatedJsonFetch = vi.fn(
    typeof responseOrFn === 'function' ? responseOrFn : () => Promise.resolve(responseOrFn)
  );
  return global.authenticatedJsonFetch;
}

// Test Patterns
export async function testValidationFlow(opts) {
  const { setInvalidValue, validateFn, expectedError, setValidValue, element } = opts;
  
  setInvalidValue();
  if (validateFn() !== false) throw new Error('Validation should have failed');
  
  if (element) assertValidationError(element, true);
  if (expectedError) {
    const errorEl = document.getElementById('claiming-error-details');
    if (!errorEl.innerHTML.includes(expectedError)) 
      throw new Error(`Expected error message not found: ${expectedError}`);
  }
  
  if (setValidValue) {
    setValidValue();
    if (validateFn() !== true) throw new Error('Validation should pass after fix');
    if (element) assertValidationError(element, false);
  }
}

export function testButtonState(opts) {
  const { button, shouldBeDisabled, setupState, updateStateFn } = opts;
  if (setupState) setupState();
  if (updateStateFn) updateStateFn();
  if (button.disabled !== shouldBeDisabled) 
    throw new Error(`Button should be ${shouldBeDisabled ? 'disabled' : 'enabled'}`);
}

export function waitFor(conditionFn, timeout = 1000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const check = () => {
      if (conditionFn()) resolve();
      else if (Date.now() - start > timeout) reject(new Error('Timeout'));
      else setTimeout(check, 10);
    };
    check();
  });
}

// Cleanup
export function resetTestEnvironment() {
  vi.clearAllMocks();
  document.body.innerHTML = '';
}

export const removeAllListeners = el => {
  const newEl = el.cloneNode(true);
  el.parentNode.replaceChild(newEl, el);
  return newEl;
};