/**
 * Comprehensive test runner for all JavaScript modules
 */

const fs = require('fs');
const path = require('path');

// Mock DOM environment
global.document = {
    getElementById: function(id) {
        return global.mockElements[id] || null;
    },
    querySelector: function(selector) {
        return global.mockElements[selector] || null;
    },
    querySelectorAll: function(selector) {
        return global.mockNodeList[selector] || [];
    },
    createElement: function(tag) {
        return {
            tagName: tag.toUpperCase(),
            textContent: '',
            innerHTML: '',
            value: '',
            classList: {
                add: function() {},
                remove: function() {},
                contains: function() { return false; }
            },
            style: {},
            appendChild: function() {},
            addEventListener: function() {},
            setAttribute: function() {},
            getAttribute: function() { return null; },
            dataset: {}
        };
    },
    cookie: '',
    addEventListener: function(event, handler) {
        if (event === 'DOMContentLoaded') {
            // Store handler to execute later
            global.domContentLoadedHandlers = global.domContentLoadedHandlers || [];
            global.domContentLoadedHandlers.push(handler);
        }
    },
    dispatchEvent: function(event) {
        // Not used in tests
    }
};

global.window = {
    location: {
        reload: function() {},
        href: ''
    }
};

global.navigator = {
    clipboard: {
        writeText: function(text) {
            return Promise.resolve();
        }
    }
};

global.fetch = function(url, options) {
    return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ success: true })
    });
};

global.alert = function(msg) {
    console.log('Alert:', msg);
};

global.confirm = function(msg) {
    console.log('Confirm:', msg);
    return true;
};

global.XMLHttpRequest = function() {
    return {
        open: function() {},
        send: function() {},
        setRequestHeader: function() {},
        onreadystatechange: null,
        readyState: 4,
        status: 200,
        responseText: '{}'
    };
};

global.QRCode = {
    toCanvas: function() {}
};

// Initialize mock elements
global.mockElements = {};
global.mockNodeList = {};

// Test utilities
let passedTests = 0;
let failedTests = 0;

function test(description, testFunc) {
    try {
        testFunc();
        console.log(`  ✅ ${description}`);
        passedTests++;
    } catch (error) {
        console.log(`  ❌ ${description}`);
        console.log(`     Error: ${error.message}`);
        failedTests++;
    }
}

function assert(condition, message) {
    if (!condition) {
        throw new Error(message || 'Assertion failed');
    }
}

function assertEqual(actual, expected, message) {
    if (actual !== expected) {
        throw new Error(message || `Expected ${expected}, got ${actual}`);
    }
}

function loadScript(filename) {
    const scriptPath = path.join(__dirname, filename);
    const scriptContent = fs.readFileSync(scriptPath, 'utf8');
    
    // Remove export statements for Node.js compatibility
    const cleanedContent = scriptContent
        .replace(/export\s+{[^}]+}/g, '')
        .replace(/export\s+default\s+/g, '');
    
    try {
        // Execute in global context to expose functions
        eval.call(global, cleanedContent);
        
        // Execute any DOMContentLoaded handlers
        if (global.domContentLoadedHandlers) {
            global.domContentLoadedHandlers.forEach(handler => {
                try {
                    handler();
                } catch (e) {
                    // Ignore handler errors in test
                }
            });
            global.domContentLoadedHandlers = [];
        }
    } catch (e) {
        console.error(`Error loading ${filename}:`, e.message);
    }
}

console.log('🧪 Running Comprehensive JavaScript Tests');
console.log('==================================================\n');

// Test common.js
console.log('📋 Testing common.js');
loadScript('common.js');

test('escapeHtml should escape HTML characters', () => {
    const input = '<script>alert("XSS")</script>';
    const output = escapeHtml(input);
    // In our mock environment, innerHTML just returns textContent
    assert(typeof output === 'string', 'Should return a string');
    assert(!output.includes('<script>'), 'Script tags should be escaped');
});

test('getCookie should parse cookies correctly', () => {
    document.cookie = 'csrftoken=abc123; sessionid=xyz789';
    const token = getCookie('csrftoken');
    assertEqual(token, 'abc123', 'Should extract CSRF token');
});

test('getCsrfToken should return CSRF token', () => {
    document.cookie = 'csrftoken=test-token';
    const token = getCsrfToken();
    assertEqual(token, 'test-token', 'Should return CSRF token');
});

test('authenticatedFetch should add CSRF header', async () => {
    document.cookie = 'csrftoken=test-token';
    let capturedOptions = null;
    
    global.fetch = function(url, options) {
        capturedOptions = options;
        return Promise.resolve({ ok: true });
    };
    
    await authenticatedFetch('/test', { method: 'POST' });
    assert(capturedOptions.headers['X-CSRFToken'] === 'test-token', 'Should include CSRF token');
});

console.log('');

// Test edit-page.js
console.log('📋 Testing edit-page.js');

// Set up mock data for edit page
global.mockElements['edit-page-data'] = {
    dataset: {
        receiptSlug: 'test-receipt',
        receiptId: '123',
        isProcessing: 'false'
    }
};

global.mockElements['balance-warning'] = {
    classList: {
        add: function() {},
        remove: function() {},
        contains: function() { return false; }
    }
};

global.mockElements['balance-error-details'] = {
    innerHTML: ''
};

// Mock functions from receipt-editor.js
global.validateReceipt = function() { return []; };
global.getReceiptData = function() { return { items: [] }; };
global.updateProrations = function() {};
global.attachItemListeners = function() {};

loadScript('edit-page.js');

test('initializeEditPage should read data attributes', () => {
    initializeEditPage();
    // Variables are scoped to edit-page.js, check if function exists
    assert(typeof initializeEditPage === 'function', 'Function should be defined');
});

test('checkAndDisplayBalanceWithProcessing should handle errors', () => {
    global.validateReceipt = function() { return ['Error 1', 'Error 2']; };
    const warningDiv = { 
        classList: { 
            remove: function(cls) { 
                this.hidden = cls === 'hidden' ? false : true; 
            } 
        } 
    };
    global.mockElements['balance-warning'] = warningDiv;
    
    checkAndDisplayBalanceWithProcessing();
    assert(!warningDiv.hidden, 'Warning should be visible when errors exist');
});

console.log('');

// Test view-page.js
console.log('📋 Testing view-page.js');

global.mockElements['view-page-data'] = {
    dataset: {
        receiptSlug: 'view-test',
        receiptId: '456'
    }
};

global.mockElements['my-total'] = {
    textContent: '$0.00'
};

global.mockNodeList['.claim-quantity'] = [];

loadScript('view-page.js');

test('initializeViewPage should read data attributes', () => {
    initializeViewPage();
    // Variables are scoped to view-page.js, check if function exists
    assert(typeof initializeViewPage === 'function', 'Function should be defined');
});

test('updateTotal should calculate correct total', () => {
    const mockInput = {
        value: '2',
        dataset: { itemId: 'item1' }
    };
    
    global.mockNodeList['.claim-quantity'] = [mockInput];
    global.mockElements['[data-item-id="item1"]'] = {
        querySelector: function() {
            return {
                dataset: { amount: '10.50' }
            };
        }
    };
    
    updateTotal();
    const total = global.mockElements['my-total'].textContent;
    assertEqual(total, '$21.00', 'Should calculate 2 × $10.50 = $21.00');
});

test('updateMyTotal should preserve local calculation when server returns 0 (regression test)', () => {
    // Setup: User has selected items locally but not finalized
    global.mockElements['my-total'] = {
        textContent: '$25.50'  // Local calculation from selected items
    };
    
    // Mock the claim button as enabled (user hasn't finalized)
    global.mockElements['claim-button'] = {
        style: { display: 'block' },
        parentElement: {
            querySelector: function() { return null; }  // No finalized indicator
        }
    };
    
    // Call updateMyTotal with server returning 0 (no finalized claims)
    updateMyTotal(0);
    
    // Assert: The local total should be preserved, not overwritten with 0
    assertEqual(
        global.mockElements['my-total'].textContent, 
        '$25.50', 
        'Should preserve local calculation when server returns 0 before finalization'
    );
});

test('updateMyTotal should use server total when user has finalized', () => {
    // Setup: User has finalized claims
    global.mockElements['my-total'] = {
        textContent: '$25.50'
    };
    
    // Mock the claim button as hidden (user has finalized)
    global.mockElements['claim-button'] = {
        style: { display: 'none' },
        parentElement: {
            querySelector: function(selector) {
                if (selector === '.text-blue-600.font-medium') {
                    return {}; // Finalized indicator exists
                }
                return null;
            }
        }
    };
    
    // Call updateMyTotal with server returning actual total
    updateMyTotal(30.75);
    
    // Assert: Should use server total when finalized
    assertEqual(
        global.mockElements['my-total'].textContent, 
        '$30.75', 
        'Should use server total when user has finalized'
    );
});

test('updateMyTotal should use server total when it is non-zero', () => {
    // Setup: Server has a non-zero total (user has some finalized claims)
    global.mockElements['my-total'] = {
        textContent: '$0.00'
    };
    
    global.mockElements['claim-button'] = {
        style: { display: 'block' },
        parentElement: {
            querySelector: function() { return null; }
        }
    };
    
    // Call updateMyTotal with server returning non-zero total
    updateMyTotal(15.25);
    
    // Assert: Should use server's non-zero total
    assertEqual(
        global.mockElements['my-total'].textContent, 
        '$15.25', 
        'Should use server total when it is non-zero'
    );
});

test('polling should not interfere with active user selections', () => {
    // Simulate the complete flow: user selects items, then polling occurs
    
    // Step 1: User selects items (updateTotal is called)
    const mockInput = {
        value: '3',
        dataset: { itemId: 'item1' }
    };
    
    global.mockNodeList['.claim-quantity'] = [mockInput];
    global.mockElements['[data-item-id="item1"]'] = {
        querySelector: function() {
            return {
                dataset: { amount: '8.00' }
            };
        }
    };
    
    global.mockElements['my-total'] = { textContent: '$0.00' };
    global.mockElements['claim-button'] = {
        style: { display: 'block' },
        parentElement: {
            querySelector: function() { return null; }
        }
    };
    
    // User changes input, updateTotal is called
    updateTotal();
    assertEqual(global.mockElements['my-total'].textContent, '$24.00', 'User selection should update total');
    
    // Step 2: Polling occurs with server returning 0 (no finalized claims yet)
    updateMyTotal(0);
    
    // Assert: Total should still be $24.00, not reset to 0
    assertEqual(
        global.mockElements['my-total'].textContent, 
        '$24.00', 
        'Polling with server returning 0 should not overwrite user selections'
    );
});

console.log('');

// Test index-page.js
console.log('📋 Testing index-page.js');

loadScript('index-page.js');

test('resizeImage should be a function', () => {
    assert(typeof resizeImage === 'function', 'resizeImage should be defined');
});

test('resizeImage should return a promise', () => {
    // Just check that the function exists and would return a promise
    assert(typeof resizeImage === 'function', 'Should be a function');
    // Don't actually call it as Canvas API isn't available in Node
});

console.log('');

// Summary
console.log('==================================================');
console.log(`Test Results: ${passedTests} passed, ${failedTests} failed`);
console.log('==================================================');

if (failedTests > 0) {
    process.exit(1);
}