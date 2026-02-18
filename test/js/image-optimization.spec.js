/**
 * Tests for client-side image optimization in index-page.js.
 * Covers: resizeImage() WebP-first with JPEG fallback, HEIC handling,
 * imageSmoothingQuality, URL.revokeObjectURL cleanup, file extension matching,
 * and graceful degradation in the change handler.
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

// Track revokeObjectURL calls
const revokeObjectURLSpy = vi.fn();
global.URL.createObjectURL = vi.fn(() => 'blob:mock');
global.URL.revokeObjectURL = revokeObjectURLSpy;

// JSDOM doesn't have DataTransfer — provide a minimal mock
if (typeof global.DataTransfer === 'undefined') {
  global.DataTransfer = class DataTransfer {
    constructor() {
      this._files = [];
      this.items = {
        add: (file) => { this._files.push(file); },
      };
    }
    get files() {
      return this._files;
    }
  };
}

const { resizeImage, initializeFileUpload } = await import('../../static/js/index-page.js');

/** Helper: create a minimal mock File */
function mockFile(name, type, size = 1024) {
  const content = new Uint8Array(size);
  return new File([content], name, { type });
}

/**
 * Helper: stub canvas/image APIs to simulate browser behavior.
 * @param {string} toBlobType - MIME type the canvas.toBlob stub returns
 */
function stubCanvasAPIs(toBlobType = 'image/webp') {
  const drawImageSpy = vi.fn();
  let capturedSmoothingQuality = null;

  // Stub canvas getContext
  const origCreateElement = document.createElement.bind(document);
  vi.spyOn(document, 'createElement').mockImplementation((tag) => {
    if (tag === 'canvas') {
      const canvas = origCreateElement('canvas');
      const fakeCtx = {
        drawImage: drawImageSpy,
        set imageSmoothingQuality(val) { capturedSmoothingQuality = val; },
        get imageSmoothingQuality() { return capturedSmoothingQuality; },
      };
      vi.spyOn(canvas, 'getContext').mockReturnValue(fakeCtx);
      vi.spyOn(canvas, 'toBlob').mockImplementation((callback, type) => {
        // First call is for WebP, second (if any) for JPEG
        const blobType = type || toBlobType;
        // If requested type is webp but we simulate Safari (no WebP support),
        // return PNG to trigger the fallback
        let resultType = blobType;
        if (toBlobType === 'image/png' && blobType === 'image/webp') {
          resultType = 'image/png';
        } else {
          resultType = blobType;
        }
        callback(new Blob(['fake'], { type: resultType }));
      });
      return canvas;
    }
    return origCreateElement(tag);
  });

  // Stub Image to auto-fire onload
  const origImage = global.Image;
  global.Image = class MockImage {
    constructor() {
      this.width = 3000;
      this.height = 2000;
      setTimeout(() => this.onload && this.onload(), 0);
    }
    set src(val) { this._src = val; }
    get src() { return this._src || ''; }
  };

  return {
    drawImageSpy,
    getSmoothingQuality: () => capturedSmoothingQuality,
    restore() {
      document.createElement.mockRestore?.();
      global.Image = origImage;
    }
  };
}

describe('Image Optimization', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('resizeImage()', () => {
    it('should produce WebP output when browser supports WebP encoding', async () => {
      const stubs = stubCanvasAPIs('image/webp');
      try {
        const file = mockFile('photo.jpg', 'image/jpeg');
        const blob = await resizeImage(file);
        expect(blob.type).toBe('image/webp');
      } finally {
        stubs.restore();
      }
    });

    it('should fall back to JPEG when browser returns non-WebP (Safari)', async () => {
      const stubs = stubCanvasAPIs('image/png'); // Simulate Safari returning PNG
      try {
        const file = mockFile('photo.jpg', 'image/jpeg');
        const blob = await resizeImage(file);
        expect(blob.type).toBe('image/jpeg');
      } finally {
        stubs.restore();
      }
    });

    it('should set imageSmoothingQuality to high', async () => {
      const stubs = stubCanvasAPIs('image/webp');
      try {
        const file = mockFile('photo.jpg', 'image/jpeg');
        await resizeImage(file);
        expect(stubs.getSmoothingQuality()).toBe('high');
      } finally {
        stubs.restore();
      }
    });

    it('should call URL.revokeObjectURL to prevent memory leaks', async () => {
      const stubs = stubCanvasAPIs('image/webp');
      try {
        const file = mockFile('photo.jpg', 'image/jpeg');
        await resizeImage(file);
        expect(revokeObjectURLSpy).toHaveBeenCalled();
      } finally {
        stubs.restore();
      }
    });

    it('should call drawImage with correct dimensions for landscape', async () => {
      const stubs = stubCanvasAPIs('image/webp');
      // MockImage defaults: 3000x2000 (landscape), maxDimension=2048
      // Expected: width=2048, height=(2000*2048)/3000 = 1365.33
      try {
        const file = mockFile('photo.jpg', 'image/jpeg');
        await resizeImage(file);
        expect(stubs.drawImageSpy).toHaveBeenCalled();
        const [, , , w, h] = stubs.drawImageSpy.mock.calls[0];
        expect(w).toBe(2048);
        expect(h).toBeCloseTo(1365.33, 0);
      } finally {
        stubs.restore();
      }
    });

    it('should call URL.createObjectURL with the file', async () => {
      const stubs = stubCanvasAPIs('image/webp');
      try {
        const file = mockFile('photo.jpg', 'image/jpeg');
        await resizeImage(file);
        expect(URL.createObjectURL).toHaveBeenCalledWith(file);
      } finally {
        stubs.restore();
      }
    });
  });

  describe('initializeFileUpload() change handler', () => {
    function setUpFileInput() {
      document.body.innerHTML = `
        <div>
          <input type="file" id="receipt_image" accept="image/*">
        </div>
      `;
      initializeFileUpload();
      return document.getElementById('receipt_image');
    }

    it('should NOT skip HEIC files (all formats go through resizeImage)', async () => {
      const stubs = stubCanvasAPIs('image/webp');
      try {
        const input = setUpFileInput();
        const heicFile = mockFile('photo.heic', 'image/heic', 5000);

        // Simulate file selection
        const dt = new DataTransfer();
        dt.items.add(heicFile);
        Object.defineProperty(input, 'files', { value: dt.files, writable: true });
        input.dispatchEvent(new Event('change'));

        // Wait for async processing
        await new Promise(resolve => setTimeout(resolve, 50));

        // drawImage should have been called (file was not skipped)
        expect(stubs.drawImageSpy).toHaveBeenCalled();
      } finally {
        stubs.restore();
      }
    });

    it('should NOT skip HEIF files', async () => {
      const stubs = stubCanvasAPIs('image/webp');
      try {
        const input = setUpFileInput();
        const heifFile = mockFile('photo.heif', 'image/heif', 5000);

        const dt = new DataTransfer();
        dt.items.add(heifFile);
        Object.defineProperty(input, 'files', { value: dt.files, writable: true });
        input.dispatchEvent(new Event('change'));

        await new Promise(resolve => setTimeout(resolve, 50));
        expect(stubs.drawImageSpy).toHaveBeenCalled();
      } finally {
        stubs.restore();
      }
    });

    it('should use .webp extension when output is WebP', async () => {
      const stubs = stubCanvasAPIs('image/webp');
      try {
        const input = setUpFileInput();
        const file = mockFile('receipt.png', 'image/png', 2000);

        const dt = new DataTransfer();
        dt.items.add(file);
        Object.defineProperty(input, 'files', { value: dt.files, writable: true });
        input.dispatchEvent(new Event('change'));

        await new Promise(resolve => setTimeout(resolve, 50));

        // After handler runs, file input should have the resized file
        const resultFile = input.files[0];
        expect(resultFile.name).toMatch(/\.webp$/);
        expect(resultFile.type).toBe('image/webp');
      } finally {
        stubs.restore();
      }
    });

    it('should use .jpg extension when output is JPEG (Safari fallback)', async () => {
      const stubs = stubCanvasAPIs('image/png'); // Simulate Safari
      try {
        const input = setUpFileInput();
        const file = mockFile('receipt.png', 'image/png', 2000);

        const dt = new DataTransfer();
        dt.items.add(file);
        Object.defineProperty(input, 'files', { value: dt.files, writable: true });
        input.dispatchEvent(new Event('change'));

        await new Promise(resolve => setTimeout(resolve, 50));

        const resultFile = input.files[0];
        expect(resultFile.name).toMatch(/\.jpg$/);
        expect(resultFile.type).toBe('image/jpeg');
      } finally {
        stubs.restore();
      }
    });

    it('should keep original file on resize failure (graceful degradation)', async () => {
      // Stub Image to fire onerror instead of onload
      const origImage = global.Image;
      const origCreateElement = document.createElement.bind(document);
      vi.spyOn(document, 'createElement').mockImplementation((tag) => {
        if (tag === 'canvas') {
          const canvas = origCreateElement('canvas');
          vi.spyOn(canvas, 'getContext').mockReturnValue({
            drawImage: vi.fn(),
            imageSmoothingQuality: 'high',
          });
          return canvas;
        }
        return origCreateElement(tag);
      });
      // Make resizeImage's Image fail (no onload fires, promise hangs)
      // Instead, we need the entire resizeImage to reject.
      // The simplest approach: make createObjectURL throw
      const origCreateObjectURL = URL.createObjectURL;
      URL.createObjectURL = vi.fn(() => { throw new Error('mock failure'); });

      try {
        const input = setUpFileInput();
        const file = mockFile('receipt.jpg', 'image/jpeg', 2000);

        const dt = new DataTransfer();
        dt.items.add(file);
        Object.defineProperty(input, 'files', { value: dt.files, writable: true });

        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
        input.dispatchEvent(new Event('change'));

        await new Promise(resolve => setTimeout(resolve, 50));

        // Original file should remain (graceful degradation)
        expect(input.files[0].name).toBe('receipt.jpg');
        expect(warnSpy).toHaveBeenCalled();

        warnSpy.mockRestore();
      } finally {
        URL.createObjectURL = origCreateObjectURL;
        document.createElement.mockRestore?.();
        global.Image = origImage;
      }
    });

    it('should remove processing message after successful resize', async () => {
      const stubs = stubCanvasAPIs('image/webp');
      try {
        const input = setUpFileInput();
        const file = mockFile('receipt.jpg', 'image/jpeg', 2000);

        const dt = new DataTransfer();
        dt.items.add(file);
        Object.defineProperty(input, 'files', { value: dt.files, writable: true });
        input.dispatchEvent(new Event('change'));

        await new Promise(resolve => setTimeout(resolve, 50));

        // Processing message should be removed
        const processingMsg = input.parentElement.querySelector('.text-blue-600');
        expect(processingMsg).toBeNull();
      } finally {
        stubs.restore();
      }
    });
  });
});
