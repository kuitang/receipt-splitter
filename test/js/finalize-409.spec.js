/**
 * Tests for submitClaims handling of a 409 already-finalized response.
 *
 * A retried finalize POST (e.g. after the first response was lost) returns
 * 409 from the server. The handler must treat the finalized state as
 * authoritative: show the message, clear saved claims, and reload the page
 * instead of showing a dead generic error.
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
global.localStorage = window.localStorage;

// Mock functions
global.alert = vi.fn();
global.confirm = vi.fn(() => true);

// Import the modules
await import('../../static/js/utils.js');
const viewPageModule = await import('../../static/js/view-page.js');

const { submitClaims, _setState } = viewPageModule;

describe('submitClaims 409 already-finalized handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    _setState({ receiptSlug: 'testslug' });
    localStorage.clear();
  });

  it('shows the server message, clears saved claims, and does not treat 409 as a generic error', async () => {
    const message = 'Claims have already been finalized and cannot be changed';
    global.authenticatedJsonFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ error: message, already_finalized: true })
    });

    localStorage.setItem('claims_testslug', JSON.stringify({ '1': 2 }));

    await submitClaims([{ line_item_id: '1', quantity_numerator: 2, quantity: 2 }]);

    // The 409 message is shown as-is (not the generic 'Error finalizing claims' alert)
    expect(global.alert).toHaveBeenCalledTimes(1);
    expect(global.alert).toHaveBeenCalledWith(message);

    // Saved claims are cleared — the finalized server state is authoritative
    expect(localStorage.getItem('claims_testslug')).toBeNull();
  });

  it('falls back to a default message when the 409 body has no error text', async () => {
    global.authenticatedJsonFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({})
    });

    await submitClaims([{ line_item_id: '1', quantity_numerator: 1, quantity: 1 }]);

    expect(global.alert).toHaveBeenCalledTimes(1);
    expect(global.alert).toHaveBeenCalledWith('Your claims have already been finalized.');
  });

  it('still shows the generic alert for non-409 errors', async () => {
    global.authenticatedJsonFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ error: 'Something else went wrong' })
    });

    await submitClaims([{ line_item_id: '1', quantity_numerator: 1, quantity: 1 }]);

    expect(global.alert).toHaveBeenCalledTimes(1);
    expect(global.alert.mock.calls[0][0]).toContain('Error finalizing claims: Something else went wrong');
  });
});
