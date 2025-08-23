import { vi } from 'vitest';
import { JSDOM } from 'jsdom';
import { setupTestTemplates } from './generated-templates.js';

export function setupTestEnvironment() {
    const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
        url: 'http://localhost',
        pretendToBeVisual: true,
        resources: 'usable'
    });

    global.window = dom.window;
    global.document = window.document;
    global.navigator = window.navigator;

    global.alert = vi.fn();
    global.confirm = vi.fn(() => true);
    global.fetch = vi.fn(() => 
        Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ success: true })
        })
    );
    global.authenticatedJsonFetch = vi.fn();
    global.escapeHtml = vi.fn((text) => String(text).replace(/[&<>"']/g, ''));

    return dom;
}

export async function setupTemplateUtils() {
    await import('../../static/js/template-utils.js');
}

export function setBodyHTML(html) {
    document.body.innerHTML = html;
    setupTestTemplates(document);
}

export function createBeforeEach(additionalSetup = null) {
    return () => {
        vi.clearAllMocks();
        document.body.innerHTML = '';
        setupTestTemplates(document);
        if (additionalSetup) {
            additionalSetup();
        }
    };
}

export async function setupUtils() {
    const utilsModule = await import('../../static/js/utils.js');
    
    global.escapeHtml = utilsModule.escapeHtml;
    global.authenticatedFetch = utilsModule.authenticatedFetch;
    global.authenticatedJsonFetch = utilsModule.authenticatedJsonFetch;
    global.copyShareUrl = utilsModule.copyShareUrl;
    global.getCookie = utilsModule.getCookie;
    global.getCsrfToken = utilsModule.getCsrfToken;
    
    return utilsModule;
}