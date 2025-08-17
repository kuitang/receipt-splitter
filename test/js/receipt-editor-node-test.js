#!/usr/bin/env node
/**
 * Node.js test runner for Receipt Editor
 * This sets up jsdom and runs the tests in a Node environment
 */

// Set up jsdom before anything else
const { JSDOM } = require('jsdom');
const dom = new JSDOM(`
<!DOCTYPE html>
<html>
<head></head>
<body>
    <div id="balance-warning" class="hidden"></div>
    <div id="balance-error-details"></div>
    <input id="restaurant_name" value="Test Restaurant">
    <input id="subtotal" type="number" value="50.00">
    <input id="tax" type="number" value="5.00">
    <input id="tip" type="number" value="10.00">
    <input id="total" type="number" value="65.00">
    <div id="items-container"></div>
    <button onclick="finalizeReceipt()">Finalize & Share</button>
</body>
</html>
`);

// Set up global variables
global.document = dom.window.document;
global.window = dom.window;
global.HTMLElement = dom.window.HTMLElement;

// Provide escapeHtml function that receipt-editor.js depends on
global.escapeHtml = function(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
};

// Load the receipt editor module
console.log('Loading receipt-editor.js...');
const receiptEditor = require('./receipt-editor.js');

// Make all functions global
for (let key in receiptEditor) {
    global[key] = receiptEditor[key];
}

// Also set window functions
global.window.calculateSubtotal = receiptEditor.calculateSubtotal;
global.window.updateSubtotal = receiptEditor.updateSubtotal;
global.window.updateItemTotal = receiptEditor.updateItemTotal;
global.window.updateProrations = receiptEditor.updateProrations;
global.window.addItem = receiptEditor.addItem;
global.window.removeItem = receiptEditor.removeItem;
global.window.attachItemListeners = receiptEditor.attachItemListeners;
global.window.validateReceipt = receiptEditor.validateReceipt;
global.window.checkAndDisplayBalance = receiptEditor.checkAndDisplayBalance;
global.window.getReceiptData = receiptEditor.getReceiptData;
global.window.receiptIsBalanced = true;

console.log('Running tests...\n');

// Simple test framework
const TestRunner = {
    tests: [],
    passed: 0,
    failed: 0,
    
    describe(name, fn) {
        console.log(`\n📋 ${name}`);
        fn();
    },
    
    it(description, fn) {
        try {
            fn();
            console.log(`  ✅ ${description}`);
            this.passed++;
        } catch (error) {
            console.error(`  ❌ ${description}`);
            console.error(`     ${error.message}`);
            this.failed++;
        }
    },
    
    assertEqual(actual, expected, message) {
        if (actual !== expected) {
            throw new Error(message || `Expected ${expected}, got ${actual}`);
        }
    },
    
    assertClose(actual, expected, tolerance = 0.01, message) {
        if (Math.abs(actual - expected) > tolerance) {
            throw new Error(message || `Expected ${expected} (±${tolerance}), got ${actual}`);
        }
    },
    
    assertTrue(condition, message) {
        if (!condition) {
            throw new Error(message || 'Assertion failed');
        }
    },
    
    summary() {
        console.log('\n' + '='.repeat(50));
        console.log(`Test Results: ${this.passed} passed, ${this.failed} failed`);
        console.log('='.repeat(50));
        return this.failed === 0;
    }
};

// Helper functions
function setupDOM() {
    // Reset the DOM for each test
    document.body.innerHTML = `
        <div id="balance-warning" class="hidden"></div>
        <div id="balance-error-details"></div>
        <input id="restaurant_name" value="Test Restaurant">
        <input id="subtotal" type="number" value="50.00">
        <input id="tax" type="number" value="5.00">
        <input id="tip" type="number" value="10.00">
        <input id="total" type="number" value="65.00">
        <div id="items-container"></div>
        <button onclick="finalizeReceipt()">Finalize & Share</button>
    `;
}

function addMockItem(name, quantity, unitPrice, totalPrice) {
    const container = document.getElementById('items-container');
    const row = document.createElement('div');
    row.className = 'item-row';
    row.innerHTML = `
        <input class="item-name" value="${name}">
        <input class="item-quantity" type="number" value="${quantity}">
        <input class="item-price" type="number" value="${unitPrice}">
        <input class="item-total" type="number" value="${totalPrice}" data-full-value="${totalPrice}">
        <span class="item-proration"></span>
        <button onclick="removeItem(this)">Remove</button>
    `;
    container.appendChild(row);
    return row;
}

// Run tests
console.log('🧪 Running Receipt Editor Unit Tests');
console.log('=' + '='.repeat(49));

TestRunner.describe('Basic Functionality Tests', () => {
    TestRunner.it('should have all functions available', () => {
        TestRunner.assertTrue(typeof calculateSubtotal === 'function');
        TestRunner.assertTrue(typeof updateSubtotal === 'function');
        TestRunner.assertTrue(typeof removeItem === 'function');
        TestRunner.assertTrue(typeof validateReceipt === 'function');
    });
    
    TestRunner.it('should calculate subtotal correctly', () => {
        setupDOM();
        addMockItem('Item1', 2, 10.00, 20.00);
        addMockItem('Item2', 1, 15.00, 15.00);
        
        const subtotal = calculateSubtotal();
        TestRunner.assertClose(subtotal, 35.00);
    });
    
    TestRunner.it('should update subtotal field', () => {
        setupDOM();
        addMockItem('Item1', 1, 25.00, 25.00);
        
        updateSubtotal();
        
        const subtotalField = document.getElementById('subtotal');
        TestRunner.assertEqual(subtotalField.value, '25.00');
    });
});

TestRunner.describe('Item Removal Tests', () => {
    TestRunner.it('should remove item and update subtotal', () => {
        setupDOM();
        const row1 = addMockItem('Keep', 1, 20.00, 20.00);
        const row2 = addMockItem('Remove', 1, 30.00, 30.00);
        
        updateSubtotal();
        TestRunner.assertEqual(document.getElementById('subtotal').value, '50.00');
        
        // Remove the second item
        removeItem(row2.querySelector('button'));
        
        TestRunner.assertEqual(document.getElementById('subtotal').value, '20.00');
        TestRunner.assertEqual(document.querySelectorAll('.item-row').length, 1);
    });
});

TestRunner.describe('Validation Tests', () => {
    TestRunner.it('should detect unbalanced receipt', () => {
        setupDOM();
        addMockItem('Item', 1, 30.00, 30.00);
        
        document.getElementById('subtotal').value = '30.00';
        document.getElementById('tax').value = '3.00';
        document.getElementById('tip').value = '5.00';
        document.getElementById('total').value = '100.00'; // Wrong!
        
        const errors = validateReceipt();
        TestRunner.assertTrue(errors.length > 0);
    });
    
    TestRunner.it('should validate balanced receipt', () => {
        setupDOM();
        addMockItem('Item', 1, 30.00, 30.00);
        
        document.getElementById('subtotal').value = '30.00';
        document.getElementById('tax').value = '3.00';
        document.getElementById('tip').value = '5.00';
        document.getElementById('total').value = '38.00'; // Correct!
        
        const errors = validateReceipt();
        TestRunner.assertEqual(errors.length, 0);
    });
    
    TestRunner.it('should allow negative tax as discount', () => {
        setupDOM();
        addMockItem('Item', 1, 50.00, 50.00);
        
        document.getElementById('subtotal').value = '50.00';
        document.getElementById('tax').value = '-5.00'; // Discount
        document.getElementById('tip').value = '7.50';
        document.getElementById('total').value = '52.50';
        
        const errors = validateReceipt();
        TestRunner.assertEqual(errors.length, 0);
    });
});

TestRunner.describe('UI Behavior Tests', () => {
    TestRunner.it('should show/hide warning based on balance', () => {
        setupDOM();
        addMockItem('Item', 1, 30.00, 30.00);
        
        // Set unbalanced values
        document.getElementById('subtotal').value = '30.00';
        document.getElementById('total').value = '100.00';
        
        checkAndDisplayBalance();
        
        const warningDiv = document.getElementById('balance-warning');
        TestRunner.assertTrue(!warningDiv.classList.contains('hidden'));
        
        // Fix the balance
        document.getElementById('total').value = '30.00';
        document.getElementById('tax').value = '0';
        document.getElementById('tip').value = '0';
        
        checkAndDisplayBalance();
        TestRunner.assertTrue(warningDiv.classList.contains('hidden'));
    });
});

// Display summary
const success = TestRunner.summary();
process.exit(success ? 0 : 1);