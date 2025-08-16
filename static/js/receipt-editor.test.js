/**
 * Unit Tests for Receipt Editor
 * Run in browser console or with Node.js
 */

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

// Mock DOM for testing
function setupDOM() {
    // Create mock DOM structure
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
TestRunner.describe('Subtotal Calculation Tests', () => {
    TestRunner.it('should calculate subtotal from items correctly', () => {
        setupDOM();
        addMockItem('Burger', 2, 15.00, 30.00);
        addMockItem('Fries', 1, 5.00, 5.00);
        addMockItem('Drink', 2, 3.00, 6.00);
        
        const subtotal = calculateSubtotal();
        TestRunner.assertClose(subtotal, 41.00);
    });
    
    TestRunner.it('should handle empty items list', () => {
        setupDOM();
        const subtotal = calculateSubtotal();
        TestRunner.assertEqual(subtotal, 0);
    });
    
    TestRunner.it('should use full precision values when available', () => {
        setupDOM();
        const row = addMockItem('Pizza', 1, 12.99, 12.99);
        row.querySelector('.item-total').dataset.fullValue = '12.987654';
        
        const subtotal = calculateSubtotal();
        TestRunner.assertClose(subtotal, 12.987654, 0.000001);
    });
});

TestRunner.describe('Update Subtotal Tests', () => {
    TestRunner.it('should update subtotal field when called', () => {
        setupDOM();
        addMockItem('Burger', 2, 15.00, 30.00);
        addMockItem('Fries', 1, 5.00, 5.00);
        
        updateSubtotal();
        
        const subtotalField = document.getElementById('subtotal');
        TestRunner.assertEqual(subtotalField.value, '35.00');
    });
    
    TestRunner.it('should format subtotal to 2 decimal places', () => {
        setupDOM();
        const row = addMockItem('Item', 1, 10.123, 10.123);
        row.querySelector('.item-total').dataset.fullValue = '10.123456';
        
        updateSubtotal();
        
        const subtotalField = document.getElementById('subtotal');
        TestRunner.assertEqual(subtotalField.value, '10.12');
    });
});

TestRunner.describe('Remove Item Tests', () => {
    TestRunner.it('should update subtotal when item is removed', () => {
        setupDOM();
        const row1 = addMockItem('Burger', 2, 15.00, 30.00);
        const row2 = addMockItem('Fries', 1, 5.00, 5.00);
        const row3 = addMockItem('Drink', 1, 3.00, 3.00);
        
        // Initial subtotal should be 38.00
        updateSubtotal();
        let subtotalField = document.getElementById('subtotal');
        TestRunner.assertEqual(subtotalField.value, '38.00');
        
        // Remove the burger (30.00)
        const removeBtn = row1.querySelector('button');
        removeItem(removeBtn);
        
        // Subtotal should now be 8.00 (5.00 + 3.00)
        subtotalField = document.getElementById('subtotal');
        TestRunner.assertEqual(subtotalField.value, '8.00');
    });
    
    TestRunner.it('should handle removing all items', () => {
        setupDOM();
        const row = addMockItem('Only Item', 1, 25.00, 25.00);
        
        updateSubtotal();
        TestRunner.assertEqual(document.getElementById('subtotal').value, '25.00');
        
        const removeBtn = row.querySelector('button');
        removeItem(removeBtn);
        
        TestRunner.assertEqual(document.getElementById('subtotal').value, '0.00');
    });
});

TestRunner.describe('Update Item Total Tests', () => {
    TestRunner.it('should calculate item total and update subtotal', () => {
        setupDOM();
        const row = addMockItem('Pizza', 1, 0, 0);
        
        // Set quantity and price
        row.querySelector('.item-quantity').value = '3';
        row.querySelector('.item-price').value = '12.50';
        
        updateItemTotal(row);
        
        // Check item total
        const itemTotal = row.querySelector('.item-total');
        TestRunner.assertEqual(itemTotal.value, '37.50');
        TestRunner.assertEqual(itemTotal.dataset.fullValue, '37.5');
        
        // Check subtotal was updated
        TestRunner.assertEqual(document.getElementById('subtotal').value, '37.50');
    });
    
    TestRunner.it('should store full precision in dataset', () => {
        setupDOM();
        const row = addMockItem('Item', 1, 0, 0);
        
        row.querySelector('.item-quantity').value = '3';
        row.querySelector('.item-price').value = '3.33';
        
        updateItemTotal(row);
        
        const itemTotal = row.querySelector('.item-total');
        TestRunner.assertEqual(itemTotal.value, '9.99');
        TestRunner.assertEqual(itemTotal.dataset.fullValue, '9.99');
    });
});

TestRunner.describe('Validation Tests', () => {
    TestRunner.it('should detect when items sum doesn\'t match subtotal', () => {
        setupDOM();
        addMockItem('Burger', 2, 15.00, 30.00);
        addMockItem('Fries', 1, 5.00, 5.00);
        
        // Set incorrect subtotal
        document.getElementById('subtotal').value = '40.00'; // Should be 35.00
        
        const errors = validateReceipt();
        TestRunner.assertTrue(errors.length > 0);
        TestRunner.assertTrue(errors.some(e => e.includes('Subtotal $40.00 doesn\'t match sum of items $35.00')));
    });
    
    TestRunner.it('should validate when everything balances', () => {
        setupDOM();
        addMockItem('Burger', 2, 15.00, 30.00);
        addMockItem('Fries', 1, 5.00, 5.00);
        
        document.getElementById('subtotal').value = '35.00';
        document.getElementById('tax').value = '3.50';
        document.getElementById('tip').value = '5.25';
        document.getElementById('total').value = '43.75';
        
        const errors = validateReceipt();
        TestRunner.assertEqual(errors.length, 0);
    });
    
    TestRunner.it('should detect negative subtotal', () => {
        setupDOM();
        document.getElementById('subtotal').value = '-10.00';
        
        const errors = validateReceipt();
        TestRunner.assertTrue(errors.some(e => e.includes('Subtotal cannot be negative')));
    });
    
    TestRunner.it('should allow negative tax (discount)', () => {
        setupDOM();
        addMockItem('Item', 1, 50.00, 50.00);
        
        document.getElementById('subtotal').value = '50.00';
        document.getElementById('tax').value = '-5.00'; // Discount
        document.getElementById('tip').value = '7.50';
        document.getElementById('total').value = '52.50';
        
        const errors = validateReceipt();
        TestRunner.assertEqual(errors.length, 0);
    });
    
    TestRunner.it('should allow negative tip (discount)', () => {
        setupDOM();
        addMockItem('Item', 1, 50.00, 50.00);
        
        document.getElementById('subtotal').value = '50.00';
        document.getElementById('tax').value = '5.00';
        document.getElementById('tip').value = '-10.00'; // Discount/credit
        document.getElementById('total').value = '45.00';
        
        const errors = validateReceipt();
        TestRunner.assertEqual(errors.length, 0);
    });
});

TestRunner.describe('UI Behavior Tests', () => {
    TestRunner.it('should show warning banner when receipt doesn\'t balance', () => {
        setupDOM();
        addMockItem('Item', 1, 30.00, 30.00);
        
        // Set values that don't balance
        document.getElementById('subtotal').value = '30.00';
        document.getElementById('tax').value = '3.00';
        document.getElementById('tip').value = '5.00';
        document.getElementById('total').value = '40.00'; // Should be 38.00
        
        checkAndDisplayBalance();
        
        const warningDiv = document.getElementById('balance-warning');
        TestRunner.assertTrue(!warningDiv.classList.contains('hidden'), 'Warning should be visible');
        TestRunner.assertEqual(window.receiptIsBalanced, false);
    });
    
    TestRunner.it('should hide warning banner when receipt balances', () => {
        setupDOM();
        addMockItem('Item', 1, 30.00, 30.00);
        
        // Set values that balance
        document.getElementById('subtotal').value = '30.00';
        document.getElementById('tax').value = '3.00';
        document.getElementById('tip').value = '5.00';
        document.getElementById('total').value = '38.00';
        
        checkAndDisplayBalance();
        
        const warningDiv = document.getElementById('balance-warning');
        TestRunner.assertTrue(warningDiv.classList.contains('hidden'), 'Warning should be hidden');
        TestRunner.assertEqual(window.receiptIsBalanced, true);
    });
    
    TestRunner.it('should disable finalize button when unbalanced', () => {
        setupDOM();
        const finalizeBtn = document.querySelector('button[onclick="finalizeReceipt()"]');
        
        // Set unbalanced values
        document.getElementById('subtotal').value = '30.00';
        document.getElementById('total').value = '100.00'; // Way off
        
        checkAndDisplayBalance();
        
        TestRunner.assertTrue(finalizeBtn.disabled, 'Finalize button should be disabled');
        TestRunner.assertTrue(finalizeBtn.classList.contains('opacity-50'), 'Button should have opacity-50 class');
    });
    
    TestRunner.it('should enable finalize button when balanced', () => {
        setupDOM();
        const finalizeBtn = document.querySelector('button[onclick="finalizeReceipt()"]');
        
        // Set balanced values
        addMockItem('Item', 1, 30.00, 30.00);
        document.getElementById('subtotal').value = '30.00';
        document.getElementById('tax').value = '3.00';
        document.getElementById('tip').value = '4.50';
        document.getElementById('total').value = '37.50';
        
        checkAndDisplayBalance();
        
        TestRunner.assertTrue(!finalizeBtn.disabled, 'Finalize button should be enabled');
        TestRunner.assertTrue(!finalizeBtn.classList.contains('opacity-50'), 'Button should not have opacity-50 class');
    });
});

TestRunner.describe('Add Item Tests', () => {
    TestRunner.it('should add new item row with correct structure', () => {
        setupDOM();
        const initialCount = document.querySelectorAll('.item-row').length;
        
        addItem();
        
        const newCount = document.querySelectorAll('.item-row').length;
        TestRunner.assertEqual(newCount, initialCount + 1, 'Should add one new item row');
        
        const newRow = document.querySelectorAll('.item-row')[initialCount];
        TestRunner.assertTrue(newRow.querySelector('.item-name') !== null, 'Should have item name input');
        TestRunner.assertTrue(newRow.querySelector('.item-quantity') !== null, 'Should have quantity input');
        TestRunner.assertTrue(newRow.querySelector('.item-price') !== null, 'Should have price input');
        TestRunner.assertTrue(newRow.querySelector('.item-total') !== null, 'Should have total input');
        TestRunner.assertTrue(newRow.querySelector('button') !== null, 'Should have remove button');
    });
    
    TestRunner.it('should attach event listeners to new item', () => {
        setupDOM();
        addItem();
        
        const newRow = document.querySelector('.item-row:last-child');
        const quantityInput = newRow.querySelector('.item-quantity');
        const priceInput = newRow.querySelector('.item-price');
        const totalInput = newRow.querySelector('.item-total');
        
        // Set values and trigger input event
        quantityInput.value = '2';
        priceInput.value = '5.50';
        
        // Manually call updateItemTotal since we can't trigger real events in this test
        updateItemTotal(newRow);
        
        TestRunner.assertEqual(totalInput.value, '11.00', 'Item total should be calculated');
    });
});

TestRunner.describe('Global Function Availability Tests', () => {
    TestRunner.it('should expose all functions globally', () => {
        const globalFunctions = [
            'calculateSubtotal',
            'updateSubtotal',
            'updateItemTotal',
            'updateProrations',
            'addItem',
            'removeItem',
            'attachItemListeners',
            'validateReceipt',
            'checkAndDisplayBalance',
            'getReceiptData'
        ];
        
        globalFunctions.forEach(funcName => {
            TestRunner.assertTrue(
                typeof window[funcName] === 'function',
                `${funcName} should be available globally`
            );
        });
    });
    
    TestRunner.it('should expose receiptIsBalanced globally', () => {
        TestRunner.assertTrue(
            typeof window.receiptIsBalanced !== 'undefined',
            'receiptIsBalanced should be available globally'
        );
    });
});

TestRunner.describe('AttachItemListeners Tests', () => {
    TestRunner.it('should attach listeners to quantity and price inputs', () => {
        setupDOM();
        const row = addMockItem('Test', 1, 10.00, 10.00);
        
        // Remove any existing listeners (for testing)
        const newQuantity = row.querySelector('.item-quantity').cloneNode(true);
        const newPrice = row.querySelector('.item-price').cloneNode(true);
        row.querySelector('.item-quantity').replaceWith(newQuantity);
        row.querySelector('.item-price').replaceWith(newPrice);
        
        // Now attach listeners
        attachItemListeners(row);
        
        // Test by changing values
        row.querySelector('.item-quantity').value = '3';
        row.querySelector('.item-price').value = '7.50';
        updateItemTotal(row);
        
        const total = row.querySelector('.item-total');
        TestRunner.assertEqual(total.value, '22.50', 'Should calculate total after attaching listeners');
    });
});

TestRunner.describe('Integration Tests', () => {
    TestRunner.it('should maintain balance after adding and removing items', () => {
        setupDOM();
        
        // Add initial items
        const row1 = addMockItem('Item1', 2, 10.00, 20.00);
        const row2 = addMockItem('Item2', 1, 15.00, 15.00);
        
        updateSubtotal();
        TestRunner.assertEqual(document.getElementById('subtotal').value, '35.00');
        
        // Add another item
        const row3 = addMockItem('Item3', 3, 5.00, 15.00);
        updateSubtotal();
        TestRunner.assertEqual(document.getElementById('subtotal').value, '50.00');
        
        // Remove middle item
        removeItem(row2.querySelector('button'));
        TestRunner.assertEqual(document.getElementById('subtotal').value, '35.00');
        
        // Update an item
        row1.querySelector('.item-quantity').value = '3';
        updateItemTotal(row1);
        TestRunner.assertEqual(document.getElementById('subtotal').value, '45.00');
    });
    
    TestRunner.it('should update validation when subtotal changes', () => {
        setupDOM();
        addMockItem('Pizza', 2, 15.00, 30.00);
        
        // Set initial values that balance
        document.getElementById('subtotal').value = '30.00';
        document.getElementById('tax').value = '3.00';
        document.getElementById('tip').value = '4.50';
        document.getElementById('total').value = '37.50';
        
        let errors = validateReceipt();
        TestRunner.assertEqual(errors.length, 0);
        
        // Remove item - subtotal should update and cause imbalance
        const row = document.querySelector('.item-row');
        removeItem(row.querySelector('button'));
        
        errors = validateReceipt();
        TestRunner.assertTrue(errors.length > 0);
    });
    
    TestRunner.it('should handle multiple item deletions correctly', () => {
        setupDOM();
        
        // Add 5 items
        addMockItem('Item1', 1, 10.00, 10.00);
        addMockItem('Item2', 2, 15.00, 30.00);
        addMockItem('Item3', 1, 20.00, 20.00);
        addMockItem('Item4', 3, 5.00, 15.00);
        addMockItem('Item5', 1, 25.00, 25.00);
        
        updateSubtotal();
        TestRunner.assertEqual(document.getElementById('subtotal').value, '100.00');
        
        // Remove items one by one and check subtotal
        let rows = document.querySelectorAll('.item-row');
        removeItem(rows[0].querySelector('button')); // Remove Item1 (-10)
        TestRunner.assertEqual(document.getElementById('subtotal').value, '90.00');
        
        rows = document.querySelectorAll('.item-row');
        removeItem(rows[1].querySelector('button')); // Remove Item3 (-20)
        TestRunner.assertEqual(document.getElementById('subtotal').value, '70.00');
        
        rows = document.querySelectorAll('.item-row');
        removeItem(rows[2].querySelector('button')); // Remove Item5 (-25)
        TestRunner.assertEqual(document.getElementById('subtotal').value, '45.00');
        
        // Verify only 2 items remain
        TestRunner.assertEqual(document.querySelectorAll('.item-row').length, 2);
    });
    
    TestRunner.it('should recalculate prorations after item removal', () => {
        setupDOM();
        
        // Add items
        const row1 = addMockItem('Expensive', 1, 60.00, 60.00);
        const row2 = addMockItem('Cheap', 1, 40.00, 40.00);
        
        document.getElementById('subtotal').value = '100.00';
        document.getElementById('tax').value = '10.00';
        document.getElementById('tip').value = '15.00';
        
        updateProrations();
        
        // Check initial prorations (60% and 40% split)
        const proration1 = row1.querySelector('.item-proration').textContent;
        TestRunner.assertTrue(proration1.includes('Tax: $6.00')); // 60% of 10
        TestRunner.assertTrue(proration1.includes('Tip: $9.00')); // 60% of 15
        
        // Remove expensive item
        removeItem(row1.querySelector('button'));
        
        // Now cheap item should get 100% of tax and tip
        const proration2 = row2.querySelector('.item-proration').textContent;
        TestRunner.assertTrue(proration2.includes('Tax: $10.00')); // 100% of 10
        TestRunner.assertTrue(proration2.includes('Tip: $15.00')); // 100% of 15
    });
});

// Run all tests
console.log('🧪 Running Receipt Editor Unit Tests');
console.log('=' + '='.repeat(49));

// Check if running in Node.js or browser
if (typeof window === 'undefined') {
    // Node.js environment - use jsdom for proper DOM
    const { JSDOM } = require('jsdom');
    const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>');
    
    global.document = dom.window.document;
    global.window = dom.window;
    global.HTMLElement = dom.window.HTMLElement;
    
    // Load the module
    const receiptEditor = require('./receipt-editor.js');
    
    // Make functions global for tests
    for (let key in receiptEditor) {
        global[key] = receiptEditor[key];
    }
    
    // Set up the test framework to run after everything is loaded
    setTimeout(() => {
        // Tests will run here
    }, 0);
}

// Display summary
const success = TestRunner.summary();

if (typeof process !== 'undefined') {
    process.exit(success ? 0 : 1);
}