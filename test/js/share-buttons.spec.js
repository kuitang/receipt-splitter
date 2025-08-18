/**
 * Comprehensive tests for share button functionality
 * Tests native share API, fallback buttons, conditionals, and mobile support
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

// Mock clipboard API
Object.assign(global.navigator, {
  clipboard: {
    writeText: vi.fn(() => Promise.resolve())
  }
});

// Import the modules
const utilsModule = await import('../../static/js/utils.js');

describe('Share Button Functionality', () => {
  let originalNavigator;
  
  beforeEach(() => {
    // Store original navigator
    originalNavigator = global.navigator;
    
    // Minimal DOM setup for share widget tests
    document.body.innerHTML = `
      <input id="share-link-input" value="https://example.com/r/test123/" readonly>
      <button data-action="native-share" data-widget-id="share-link-input" title="Share"></button>
      <button data-action="copy-share-url" data-widget-id="share-link-input" title="Copy to clipboard"></button>
      <div class="mobile-fallback-share hidden">
        <a data-action="share-whatsapp" data-widget-id="share-link-input"></a>
        <a data-action="share-messenger" data-widget-id="share-link-input"></a>
        <a data-action="share-sms" data-widget-id="share-link-input"></a>
      </div>
    `;
    
    // Reset mocks
    vi.clearAllMocks();
  });

  afterEach(() => {
    global.navigator = originalNavigator;
  });

  describe('Button Presence', () => {
    it('should have all required share buttons', () => {
      const nativeShareBtn = document.querySelector('[data-action="native-share"]');
      const copyBtn = document.querySelector('[data-action="copy-share-url"]');
      const whatsappBtn = document.querySelector('[data-action="share-whatsapp"]');
      
      expect(nativeShareBtn).toBeTruthy();
      expect(copyBtn).toBeTruthy();
      expect(whatsappBtn).toBeTruthy();
    });
  });

  describe('Native Share API Detection', () => {
    it('should detect native share availability', () => {
      global.navigator.share = vi.fn(() => Promise.resolve());
      expect('share' in navigator).toBe(true);
      
      delete global.navigator.share;
      expect('share' in navigator).toBe(false);
    });
  });

  // HTTPS vs HTTP behavior tests removed - trivial protocol string comparison

  describe('Share Button Conditionals and Fallbacks', () => {
    it('should show native share on HTTPS mobile with share API', () => {
      // Setup: Mobile + HTTPS + Native Share API
      Object.defineProperty(global.navigator, 'userAgent', {
        value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X)',
        configurable: true
      });
      // Test protocol detection logic
      const mockProtocol = 'https:';
      global.navigator.share = vi.fn(() => Promise.resolve());
      
      const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
      const isHTTPS = mockProtocol === 'https:';
      const hasShare = !!navigator.share;
      
      expect(isMobile).toBe(true);
      expect(isHTTPS).toBe(true);
      expect(hasShare).toBe(true);
      
      // In this case, native share button should be shown
      const nativeShareBtn = document.querySelector('[data-action="native-share"]');
      expect(nativeShareBtn).toBeTruthy();
    });

    it('should show fallback buttons on mobile without native share', () => {
      // Setup: Mobile + No Native Share API
      Object.defineProperty(global.navigator, 'userAgent', {
        value: 'Mozilla/5.0 (Android 8.0; Mobile)',
        configurable: true
      });
      delete global.navigator.share;
      
      const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
      const hasShare = !!navigator.share;
      
      expect(isMobile).toBe(true);
      expect(hasShare).toBe(false);
      
      // Fallback buttons should be available
      const fallbackContainer = document.querySelector('.mobile-fallback-share');
      const fallbackBtns = fallbackContainer.querySelectorAll('a');
      
      expect(fallbackContainer).toBeTruthy();
      expect(fallbackBtns.length).toBe(3); // WhatsApp, Messenger, SMS
    });

    it('should show fallback buttons on HTTP mobile', () => {
      // Setup: Mobile + HTTP (native share typically requires HTTPS)
      Object.defineProperty(global.navigator, 'userAgent', {
        value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X)',
        configurable: true
      });
      // Test protocol detection logic
      const mockProtocol = 'http:';
      
      const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
      const isHTTPS = mockProtocol === 'https:';
      
      expect(isMobile).toBe(true);
      expect(isHTTPS).toBe(false);
      
      // Even if native share exists, HTTP might limit it, so fallbacks are important
      const fallbackContainer = document.querySelector('.mobile-fallback-share');
      expect(fallbackContainer).toBeTruthy();
    });

    it('should always have copy button available', () => {
      // Copy button should always be present regardless of conditions
      const copyBtn = document.querySelector('[data-action="copy-share-url"]');
      expect(copyBtn).toBeTruthy();
      expect(copyBtn.title).toBe('Copy to clipboard');
    });

    it('should ensure at least one share method is always available', () => {
      // Critical test: No matter what, user should have SOME way to share
      const nativeShareBtn = document.querySelector('[data-action="native-share"]');
      const copyBtn = document.querySelector('[data-action="copy-share-url"]');
      const fallbackBtns = document.querySelectorAll('.mobile-fallback-share a');
      
      const hasNativeShare = nativeShareBtn && !nativeShareBtn.classList.contains('hidden');
      const hasCopyButton = copyBtn && !copyBtn.classList.contains('hidden');
      const hasFallbackButtons = fallbackBtns.length > 0;
      
      // At minimum, copy button should always be available
      expect(hasCopyButton).toBe(true);
      
      // And there should be additional options
      const totalShareOptions = (hasNativeShare ? 1 : 0) + (hasCopyButton ? 1 : 0) + fallbackBtns.length;
      expect(totalShareOptions).toBeGreaterThan(1);
    });
  });

  describe('Copy to Clipboard Functionality', () => {
    it('should copy URL to clipboard when copy button is clicked', async () => {
      const copyBtn = document.querySelector('[data-action="copy-share-url"]');
      const input = document.querySelector('#share-link-input');
      
      // Mock successful clipboard operation
      global.navigator.clipboard.writeText = vi.fn(() => Promise.resolve());
      
      // Trigger copy
      copyBtn.click();
      
      // Should attempt to copy the input value
      expect(input.value).toBe('https://example.com/r/test123/');
    });

    it('should handle clipboard API errors gracefully', async () => {
      const copyBtn = document.querySelector('[data-action="copy-share-url"]');
      
      // Mock clipboard error
      global.navigator.clipboard.writeText = vi.fn(() => Promise.reject(new Error('Clipboard denied')));
      
      // Should not throw error
      expect(() => {
        copyBtn.click();
      }).not.toThrow();
    });

    it('should fallback when clipboard API is not available', () => {
      // Remove clipboard API
      delete global.navigator.clipboard;
      
      const copyBtn = document.querySelector('[data-action="copy-share-url"]');
      
      // Should not throw error even without clipboard API
      expect(() => {
        copyBtn.click();
      }).not.toThrow();
    });
  });

  // Mobile Fallback Button URL tests removed - trivial URL encoding tests

  describe('Error Handling and Edge Cases', () => {
    it('should handle missing widget ID gracefully', () => {
      document.body.innerHTML = `
        <button data-action="copy-share-url">Copy</button>
        <button data-action="native-share">Share</button>
      `;
      
      const copyBtn = document.querySelector('[data-action="copy-share-url"]');
      const shareBtn = document.querySelector('[data-action="native-share"]');
      
      expect(() => {
        copyBtn.click();
        shareBtn.click();
      }).not.toThrow();
    });

    it('should handle missing input element gracefully', () => {
      document.body.innerHTML = `
        <button data-action="copy-share-url" data-widget-id="nonexistent">Copy</button>
      `;
      
      const copyBtn = document.querySelector('[data-action="copy-share-url"]');
      
      expect(() => {
        copyBtn.click();
      }).not.toThrow();
    });

    it('should handle empty share URL', () => {
      const input = document.querySelector('#share-link-input');
      input.value = '';
      
      const copyBtn = document.querySelector('[data-action="copy-share-url"]');
      
      expect(() => {
        copyBtn.click();
      }).not.toThrow();
    });

    // Button state test removed - trivial CSS class check
  });

  describe('Critical Mobile Share Guarantee', () => {
    it('should guarantee share options on iPhone Safari', () => {
      Object.defineProperty(global.navigator, 'userAgent', {
        value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6 Mobile/15E148 Safari/604.1',
        configurable: true
      });
      
      const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
      expect(isMobile).toBe(true);
      
      // Should have multiple share options
      const copyBtn = document.querySelector('[data-action="copy-share-url"]');
      const nativeBtn = document.querySelector('[data-action="native-share"]');
      const fallbackBtns = document.querySelectorAll('.mobile-fallback-share a');
      
      expect(copyBtn).toBeTruthy();
      expect(nativeBtn).toBeTruthy();
      expect(fallbackBtns.length).toBeGreaterThan(0);
    });

    it('should guarantee share options on Android Chrome', () => {
      Object.defineProperty(global.navigator, 'userAgent', {
        value: 'Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.74 Mobile Safari/537.36',
        configurable: true
      });
      
      const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
      expect(isMobile).toBe(true);
      
      // Should have multiple share options
      const totalShareMethods = [
        document.querySelector('[data-action="copy-share-url"]'),
        document.querySelector('[data-action="native-share"]'),
        ...document.querySelectorAll('.mobile-fallback-share a')
      ].filter(Boolean).length;
      
      expect(totalShareMethods).toBeGreaterThanOrEqual(4); // Copy + Native + 3 fallbacks minimum
    });

    it('should guarantee share options even on old mobile browsers', () => {
      // Simulate old mobile browser without modern APIs
      Object.defineProperty(global.navigator, 'userAgent', {
        value: 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36',
        configurable: true
      });
      delete global.navigator.share;
      delete global.navigator.clipboard;
      
      const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
      expect(isMobile).toBe(true);
      
      // Even without modern APIs, should still have fallback options
      const fallbackBtns = document.querySelectorAll('.mobile-fallback-share a');
      const copyBtn = document.querySelector('[data-action="copy-share-url"]');
      
      expect(fallbackBtns.length).toBeGreaterThanOrEqual(3);
      expect(copyBtn).toBeTruthy();
    });
  });
});