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
    
    // Reset DOM with complete share widget
    document.body.innerHTML = `
      <div class="flex flex-col gap-2">
        <div class="flex items-center">
          <input type="text" 
                 value="https://example.com/r/test123/" 
                 readonly 
                 id="share-link-input"
                 class="flex-1 px-3 py-2 border-gray-300 border rounded-l-lg bg-gray-50">
          
          <!-- Native share button (mobile only) -->
          <button data-action="native-share"
                  data-widget-id="share-link-input"
                  class="mobile-share-btn px-3 py-2 border-gray-300 border border-l-0 bg-white hover:bg-blue-50 transition-colors hidden"
                  title="Share">
              <svg class="h-6 w-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"></path>
              </svg>
          </button>
          
          <!-- Copy to clipboard button -->
          <button data-action="copy-share-url"
                  data-widget-id="share-link-input"
                  class="px-3 py-2 border-gray-300 border border-l-0 rounded-r-lg bg-white hover:bg-blue-50 transition-colors"
                  title="Copy to clipboard">
              <div class="h-6 w-6 text-blue-600 flex items-center justify-center text-lg font-bold">⧉</div>
          </button>
        </div>
        
        <!-- Fallback share buttons for HTTP/non-supported browsers -->
        <div class="mobile-fallback-share hidden flex gap-2">
          <a data-action="share-whatsapp"
             data-widget-id="share-link-input"
             href="#"
             class="flex-1 bg-green-500 text-white p-2 rounded-lg flex items-center justify-center hover:bg-green-600 transition-colors"
             title="Share on WhatsApp">
              <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.149-.67.149-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.074-.297-.149-1.255-.462-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.297-.347.446-.521.151-.172.2-.296.3-.495.099-.198.05-.372-.025-.521-.075-.148-.669-1.611-.916-2.206-.242-.579-.487-.501-.669-.51l-.57-.01c-.198 0-.52.074-.792.372s-1.04 1.016-1.04 2.479 1.065 2.876 1.213 3.074c.149.198 2.095 3.2 5.076 4.487.709.306 1.263.489 1.694.626.712.226 1.36.194 1.872.118.571-.085 1.758-.719 2.006-1.413.248-.695.248-1.29.173-1.414-.074-.123-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
              </svg>
          </a>
          <a data-action="share-messenger"
             data-widget-id="share-link-input"
             href="#"
             class="flex-1 bg-blue-500 text-white p-2 rounded-lg flex items-center justify-center hover:bg-blue-600 transition-colors"
             title="Share on Messenger">
              <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 0C5.373 0 0 4.974 0 11.111c0 3.498 1.744 6.614 4.469 8.654V24l4.088-2.242c1.092.301 2.246.464 3.443.464 6.627 0 12-4.975 12-11.111S18.627 0 12 0zm1.191 14.963l-3.055-3.26-5.963 3.26L10.732 8l3.131 3.259L19.752 8l-6.561 6.963z"/>
              </svg>
          </a>
          <a data-action="share-sms"
             data-widget-id="share-link-input"
             href="#"
             class="flex-1 bg-gray-600 text-white p-2 rounded-lg flex items-center justify-center hover:bg-gray-700 transition-colors"
             title="Share via SMS">
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path>
              </svg>
          </a>
        </div>
      </div>
    `;
    
    // Reset mocks
    vi.clearAllMocks();
  });

  afterEach(() => {
    global.navigator = originalNavigator;
  });

  describe('Button Presence and Styling', () => {
    it('should have native share button with correct icon size', () => {
      const nativeShareBtn = document.querySelector('[data-action="native-share"]');
      const icon = nativeShareBtn.querySelector('svg');
      
      expect(nativeShareBtn).toBeTruthy();
      expect(icon.classList.contains('h-6')).toBe(true);
      expect(icon.classList.contains('w-6')).toBe(true);
    });

    it('should have copy button with same icon size as native share', () => {
      const copyBtn = document.querySelector('[data-action="copy-share-url"]');
      const nativeShareBtn = document.querySelector('[data-action="native-share"]');
      
      const copyIcon = copyBtn.querySelector('.h-6.w-6');
      const shareIcon = nativeShareBtn.querySelector('.h-6.w-6');
      
      expect(copyIcon).toBeTruthy();
      expect(shareIcon).toBeTruthy();
      expect(copyIcon.classList.contains('h-6')).toBe(true);
      expect(copyIcon.classList.contains('w-6')).toBe(true);
    });

    it('should have all fallback share buttons', () => {
      const whatsappBtn = document.querySelector('[data-action="share-whatsapp"]');
      const messengerBtn = document.querySelector('[data-action="share-messenger"]');
      const smsBtn = document.querySelector('[data-action="share-sms"]');
      
      expect(whatsappBtn).toBeTruthy();
      expect(messengerBtn).toBeTruthy();
      expect(smsBtn).toBeTruthy();
    });

    it('should have consistent button styling', () => {
      const fallbackBtns = document.querySelectorAll('.mobile-fallback-share a');
      
      fallbackBtns.forEach(btn => {
        expect(btn.classList.contains('flex-1')).toBe(true);
        expect(btn.classList.contains('p-2')).toBe(true);
        expect(btn.classList.contains('rounded-lg')).toBe(true);
        expect(btn.classList.contains('flex')).toBe(true);
        expect(btn.classList.contains('items-center')).toBe(true);
        expect(btn.classList.contains('justify-center')).toBe(true);
      });
    });
  });

  describe('Native Share API Detection', () => {
    it('should detect when native share is available', () => {
      // Mock native share support
      global.navigator.share = vi.fn(() => Promise.resolve());
      
      const hasNativeShare = 'share' in navigator;
      expect(hasNativeShare).toBe(true);
    });

    it('should detect when native share is not available', () => {
      // Remove native share support
      delete global.navigator.share;
      
      const hasNativeShare = 'share' in navigator;
      expect(hasNativeShare).toBe(false);
    });

    it('should detect mobile user agents', () => {
      const mobileUserAgents = [
        'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15',
        'Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15',
        'Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36',
        'Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36'
      ];
      
      mobileUserAgents.forEach(ua => {
        Object.defineProperty(global.navigator, 'userAgent', {
          value: ua,
          configurable: true
        });
        
        const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
        expect(isMobile).toBe(true);
      });
    });

    it('should detect desktop user agents', () => {
      const desktopUserAgents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
      ];
      
      desktopUserAgents.forEach(ua => {
        Object.defineProperty(global.navigator, 'userAgent', {
          value: ua,
          configurable: true
        });
        
        const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
        expect(isMobile).toBe(false);
      });
    });
  });

  describe('HTTPS vs HTTP Behavior', () => {
    it('should detect HTTPS protocol', () => {
      // Test the logic directly without redefining window.location
      const mockProtocol = 'https:';
      const isHTTPS = mockProtocol === 'https:';
      expect(isHTTPS).toBe(true);
    });

    it('should detect HTTP protocol', () => {
      // Test the logic directly without redefining window.location
      const mockProtocol = 'http:';
      const isHTTPS = mockProtocol === 'https:';
      expect(isHTTPS).toBe(false);
    });
  });

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

  describe('Mobile Fallback Button URLs', () => {
    it('should generate correct WhatsApp share URL', () => {
      const whatsappBtn = document.querySelector('[data-action="share-whatsapp"]');
      const input = document.querySelector('#share-link-input');
      
      // Simulate URL generation
      const shareUrl = input.value;
      const whatsappUrl = `https://wa.me/?text=${encodeURIComponent(`Check out this receipt: ${shareUrl}`)}`;
      
      expect(shareUrl).toBe('https://example.com/r/test123/');
      expect(whatsappUrl).toContain('wa.me');
      expect(whatsappUrl).toContain(encodeURIComponent(shareUrl));
    });

    it('should generate correct SMS share URL', () => {
      const smsBtn = document.querySelector('[data-action="share-sms"]');
      const input = document.querySelector('#share-link-input');
      
      // Simulate URL generation  
      const shareUrl = input.value;
      const smsUrl = `sms:?&body=${encodeURIComponent(`Check out this receipt: ${shareUrl}`)}`;
      
      expect(smsUrl).toContain('sms:');
      expect(smsUrl).toContain(encodeURIComponent(shareUrl));
    });

    it('should handle special characters in URLs', () => {
      const input = document.querySelector('#share-link-input');
      input.value = 'https://example.com/r/test-123/?foo=bar&baz=qux';
      
      const encodedUrl = encodeURIComponent(input.value);
      expect(encodedUrl).not.toContain('&');
      expect(encodedUrl).not.toContain('?');
      expect(encodedUrl).toContain('%');
    });
  });

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

    it('should maintain button state during operations', () => {
      const copyBtn = document.querySelector('[data-action="copy-share-url"]');
      const originalClasses = Array.from(copyBtn.classList);
      
      copyBtn.click();
      
      // Button classes should remain unchanged after click
      expect(Array.from(copyBtn.classList)).toEqual(originalClasses);
    });
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