/**
 * Tests for Venmo username validation on the upload (index) page.
 * Covers: validateVenmo() validation + error messages,
 * initializeVenmoInput() blur validation, and form submission blocking/normalization.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { JSDOM } from 'jsdom';

const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
  url: 'http://localhost',
  pretendToBeVisual: true,
  resources: 'usable'
});

global.window = dom.window;
global.document = window.document;
global.navigator = window.navigator;
global.alert = vi.fn();
global.URL.createObjectURL = vi.fn(() => 'blob:mock');

const { validateVenmo, initializeVenmoInput } = await import('../../static/js/index-page.js');

/** Build the upload form HTML with venmo input and error element. */
function setUpForm() {
  document.body.innerHTML = `
    <form id="upload-form" action="/upload/" method="post">
      <input type="text" name="venmo_username" id="venmo_username" maxlength="31">
      <p id="venmo-error" class="hidden"></p>
      <button type="submit">Upload</button>
    </form>
  `;
  return {
    input: document.getElementById('venmo_username'),
    error: document.getElementById('venmo-error'),
    form: document.getElementById('upload-form'),
  };
}

describe('Venmo Username Validation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('validateVenmo()', () => {
    it('should accept empty input (optional field)', () => {
      const { input, error } = setUpForm();
      input.value = '';
      expect(validateVenmo(input, error)).toBe(true);
      expect(error.classList.contains('hidden')).toBe(true);
    });

    it('should accept bare @ (user skipped)', () => {
      const { input, error } = setUpForm();
      input.value = '@';
      expect(validateVenmo(input, error)).toBe(true);
      expect(error.classList.contains('hidden')).toBe(true);
    });

    it('should accept valid username with @ prefix', () => {
      const { input, error } = setUpForm();
      input.value = '@john-doe_123';
      expect(validateVenmo(input, error)).toBe(true);
      expect(error.classList.contains('hidden')).toBe(true);
      expect(input.classList.contains('border-red-500')).toBe(false);
    });

    it('should accept valid username without @ prefix', () => {
      const { input, error } = setUpForm();
      input.value = 'valid-user';
      expect(validateVenmo(input, error)).toBe(true);
    });

    it('should accept exactly 5 character username', () => {
      const { input, error } = setUpForm();
      input.value = 'abcde';
      expect(validateVenmo(input, error)).toBe(true);
    });

    it('should accept exactly 30 character username', () => {
      const { input, error } = setUpForm();
      input.value = 'a'.repeat(30);
      expect(validateVenmo(input, error)).toBe(true);
    });

    it('should reject username shorter than 5 characters', () => {
      const { input, error } = setUpForm();
      input.value = 'ab';
      expect(validateVenmo(input, error)).toBe(false);
      expect(error.classList.contains('hidden')).toBe(false);
      expect(error.textContent).toContain('at least 5 characters');
      expect(input.classList.contains('border-red-500')).toBe(true);
      expect(input.classList.contains('bg-red-50')).toBe(true);
    });

    it('should reject @-prefixed username shorter than 5 characters', () => {
      const { input, error } = setUpForm();
      input.value = '@ab';
      expect(validateVenmo(input, error)).toBe(false);
      expect(error.textContent).toContain('at least 5 characters');
    });

    it('should reject username longer than 30 characters', () => {
      const { input, error } = setUpForm();
      input.value = 'a'.repeat(31);
      expect(validateVenmo(input, error)).toBe(false);
      expect(error.textContent).toContain('30 characters or less');
    });

    it('should reject username with spaces', () => {
      const { input, error } = setUpForm();
      input.value = 'hello world';
      expect(validateVenmo(input, error)).toBe(false);
      expect(error.textContent).toContain('letters, numbers, hyphens, and underscores');
    });

    it('should reject username with dots', () => {
      const { input, error } = setUpForm();
      input.value = 'john.doe.test';
      expect(validateVenmo(input, error)).toBe(false);
      expect(error.textContent).toContain('letters, numbers, hyphens, and underscores');
    });

    it('should reject username with special characters', () => {
      const { input, error } = setUpForm();
      input.value = 'user!@#$%';
      expect(validateVenmo(input, error)).toBe(false);
    });

    it('should clear error styling when corrected', () => {
      const { input, error } = setUpForm();

      // First invalid
      input.value = 'ab';
      validateVenmo(input, error);
      expect(input.classList.contains('border-red-500')).toBe(true);
      expect(input.classList.contains('bg-red-50')).toBe(true);
      expect(error.classList.contains('hidden')).toBe(false);

      // Then valid
      input.value = 'abcdef';
      validateVenmo(input, error);
      expect(input.classList.contains('border-red-500')).toBe(false);
      expect(input.classList.contains('bg-red-50')).toBe(false);
      expect(error.classList.contains('hidden')).toBe(true);
    });
  });

  describe('initializeVenmoInput()', () => {
    it('should validate on blur and show error for invalid input', () => {
      const { input, error } = setUpForm();
      initializeVenmoInput();

      input.value = 'ab';
      input.dispatchEvent(new Event('blur'));

      expect(error.classList.contains('hidden')).toBe(false);
      expect(error.textContent).toContain('at least 5 characters');
    });

    it('should clear error on blur when input becomes valid', () => {
      const { input, error } = setUpForm();
      initializeVenmoInput();

      // Invalid
      input.value = 'ab';
      input.dispatchEvent(new Event('blur'));
      expect(error.classList.contains('hidden')).toBe(false);

      // Fixed
      input.value = 'abcdef';
      input.dispatchEvent(new Event('blur'));
      expect(error.classList.contains('hidden')).toBe(true);
    });

    it('should strip @ and normalize on submit', () => {
      const { input, form } = setUpForm();
      initializeVenmoInput();

      input.value = '@myvenmo';
      const submitEvent = new Event('submit', { cancelable: true });
      form.dispatchEvent(submitEvent);

      expect(input.value).toBe('myvenmo');
      expect(submitEvent.defaultPrevented).toBe(false);
    });

    it('should clear bare @ to empty on submit', () => {
      const { input, form } = setUpForm();
      initializeVenmoInput();

      input.value = '@';
      const submitEvent = new Event('submit', { cancelable: true });
      form.dispatchEvent(submitEvent);

      expect(input.value).toBe('');
      expect(submitEvent.defaultPrevented).toBe(false);
    });

    it('should allow submit with no @ and valid username', () => {
      const { input, form } = setUpForm();
      initializeVenmoInput();

      input.value = 'valid-user';
      const submitEvent = new Event('submit', { cancelable: true });
      form.dispatchEvent(submitEvent);

      expect(input.value).toBe('valid-user');
      expect(submitEvent.defaultPrevented).toBe(false);
    });

    it('should block submit when username is invalid', () => {
      const { input, form } = setUpForm();
      initializeVenmoInput();

      input.value = 'ab';
      const submitEvent = new Event('submit', { cancelable: true });
      form.dispatchEvent(submitEvent);

      expect(submitEvent.defaultPrevented).toBe(true);
    });

    it('should allow submit when field is empty', () => {
      const { input, form } = setUpForm();
      initializeVenmoInput();

      input.value = '';
      const submitEvent = new Event('submit', { cancelable: true });
      form.dispatchEvent(submitEvent);

      expect(submitEvent.defaultPrevented).toBe(false);
    });
  });
});
