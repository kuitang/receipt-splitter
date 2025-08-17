// Global test setup for Vitest
import { expect, afterEach } from 'vitest';

// Extends Vitest's expect matchers
expect.extend({
  toBeWithinTolerance(received, expected, tolerance = 0.01) {
    const pass = Math.abs(received - expected) <= tolerance;
    return {
      pass,
      message: () => 
        pass
          ? `Expected ${received} not to be within ${tolerance} of ${expected}`
          : `Expected ${received} to be within ${tolerance} of ${expected}`
    };
  }
});

// Clean up after each test
afterEach(() => {
  document.body.innerHTML = '';
  document.head.innerHTML = '';
});

// Mock global objects that might not exist in jsdom
global.QRCode = {
  toCanvas: vi.fn()
};

// Add any other global test utilities here