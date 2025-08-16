#!/usr/bin/env python3
"""
Integration tests for design system consistency across views
Tests that all pages follow the design patterns defined in DESIGN.md
"""

import os
import sys
import time
from pathlib import Path
from decimal import Decimal
from datetime import datetime
import re

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'receipt_splitter.settings')
import django
django.setup()

from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from receipts.models import Receipt, LineItem, Claim
from django.utils import timezone


class DesignConsistencyTest:
    """Test design consistency across all views"""
    
    def __init__(self):
        self.client = Client()
        self.test_receipt = None
        self.errors = []
        self.warnings = []
        
    def setup_test_data(self):
        """Create test receipt with known data"""
        print("\n📝 Setting up test data...")
        
        # Clean up old test data
        Receipt.objects.filter(uploader_name='Design Test User').delete()
        
        # Create a complete receipt
        self.test_receipt = Receipt.objects.create(
            uploader_name='Design Test User',
            restaurant_name='Test Restaurant',
            date=timezone.now(),
            subtotal=Decimal('100.00'),
            tax=Decimal('10.00'),
            tip=Decimal('20.00'),
            total=Decimal('130.00'),
            is_finalized=True,
            processing_status='completed'
        )
        
        # Add line items
        LineItem.objects.create(
            receipt=self.test_receipt,
            name='Burger',
            quantity=2,
            unit_price=Decimal('25.00'),
            total_price=Decimal('50.00')
        )
        
        LineItem.objects.create(
            receipt=self.test_receipt,
            name='Fries',
            quantity=2,
            unit_price=Decimal('10.00'),
            total_price=Decimal('20.00')
        )
        
        LineItem.objects.create(
            receipt=self.test_receipt,
            name='Soda',
            quantity=3,
            unit_price=Decimal('10.00'),
            total_price=Decimal('30.00')
        )
        
        print(f"   ✅ Created receipt with slug: {self.test_receipt.slug}")
        
    def check_css_classes(self, content, view_name):
        """Check that standardized CSS classes are used"""
        print(f"\n🎨 Checking CSS classes in {view_name}...")
        
        # Define expected patterns from DESIGN.md
        patterns = {
            'Page Title': r'class="[^"]*page-title[^"]*"',
            'Section Header': r'class="[^"]*section-header[^"]*"',
            'Cards': r'class="[^"]*card[^"]*"',
            'Buttons': r'class="[^"]*btn[^"]*"',
            'Inputs': r'class="[^"]*input-standard[^"]*"',
        }
        
        for name, pattern in patterns.items():
            if re.search(pattern, content):
                print(f"   ✅ Found {name} classes")
            else:
                # Some patterns may not be on all pages
                if name in ['Page Title', 'Cards']:
                    self.warnings.append(f"{view_name}: No {name} classes found")
                    print(f"   ⚠️  No {name} classes found")
        
    def check_typography_consistency(self, content, view_name):
        """Check typography scale consistency"""
        print(f"\n📝 Checking typography in {view_name}...")
        
        # Check for consistent text sizes
        text_sizes = {
            'text-3xl': 'Page titles',
            'text-2xl': 'Section headers',
            'text-xl': 'Subsection headers',
            'text-lg': 'Large text',
            'text-base': 'Body text',
            'text-sm': 'Secondary text',
            'text-xs': 'Tertiary text'
        }
        
        found_sizes = []
        for size, usage in text_sizes.items():
            if size in content:
                found_sizes.append(size)
        
        if found_sizes:
            print(f"   ✅ Found text sizes: {', '.join(found_sizes)}")
        else:
            self.errors.append(f"{view_name}: No standard text sizes found")
            print(f"   ❌ No standard text sizes found")
    
    def check_color_consistency(self, content, view_name):
        """Check color palette consistency"""
        print(f"\n🎨 Checking colors in {view_name}...")
        
        # Standard colors from DESIGN.md
        standard_colors = {
            'blue-600': 'Primary',
            'green-600': 'Success',
            'red-600': 'Danger',
            'gray-900': 'Text primary',
            'gray-700': 'Text secondary',
            'gray-600': 'Text tertiary',
            'gray-50': 'Background'
        }
        
        found_colors = []
        for color, usage in standard_colors.items():
            if color in content:
                found_colors.append(f"{color} ({usage})")
        
        if found_colors:
            print(f"   ✅ Found standard colors: {len(found_colors)} types")
        
    def check_spacing_consistency(self, content, view_name):
        """Check spacing patterns"""
        print(f"\n📏 Checking spacing in {view_name}...")
        
        # Standard spacing patterns
        spacing_patterns = ['space-y-6', 'space-y-3', 'space-y-1', 'gap-4', 'gap-2']
        
        found_spacing = []
        for pattern in spacing_patterns:
            if pattern in content:
                found_spacing.append(pattern)
        
        if found_spacing:
            print(f"   ✅ Found spacing patterns: {', '.join(found_spacing)}")
    
    def check_responsive_design(self, content, view_name):
        """Check responsive design patterns"""
        print(f"\n📱 Checking responsive design in {view_name}...")
        
        responsive_patterns = ['md:', 'sm:', 'lg:', 'flex', 'grid']
        
        found = 0
        for pattern in responsive_patterns:
            if pattern in content:
                found += 1
        
        if found >= 3:
            print(f"   ✅ Found {found} responsive patterns")
        else:
            self.warnings.append(f"{view_name}: Limited responsive patterns ({found})")
            print(f"   ⚠️  Limited responsive patterns ({found})")
    
    def check_accessibility(self, content, view_name):
        """Check accessibility features"""
        print(f"\n♿ Checking accessibility in {view_name}...")
        
        # Check for accessibility attributes
        a11y_patterns = {
            'aria-': 'ARIA attributes',
            'role=': 'Role attributes',
            'alt=': 'Alt text',
            'focus:': 'Focus styles',
            'sr-only': 'Screen reader text'
        }
        
        found = []
        for pattern, name in a11y_patterns.items():
            if pattern in content:
                found.append(name)
        
        if found:
            print(f"   ✅ Found: {', '.join(found)}")
        else:
            self.warnings.append(f"{view_name}: Limited accessibility features")
            print(f"   ⚠️  Limited accessibility features")
    
    def check_decimal_consistency(self, content, view_name):
        """Check that all monetary values show 2 decimal places"""
        print(f"\n💰 Checking decimal formatting in {view_name}...")
        
        # Look for monetary values with wrong decimal places
        # Pattern: $XXX.XXXXXX (more than 2 decimal places)
        bad_decimals = re.findall(r'\$\d+\.\d{3,}', content)
        
        if bad_decimals:
            self.errors.append(f"{view_name}: Found values with >2 decimals: {bad_decimals[:3]}")
            print(f"   ❌ Found values with >2 decimals: {len(bad_decimals)} instances")
        else:
            print(f"   ✅ All monetary values use 2 decimal places")
    
    def test_view_receipt(self):
        """Test the view receipt page"""
        print("\n" + "=" * 70)
        print("TESTING VIEW RECEIPT PAGE (/r)")
        print("=" * 70)
        
        response = self.client.get(f'/r/{self.test_receipt.slug}/')
        
        if response.status_code != 200:
            self.errors.append(f"View page returned {response.status_code}")
            return
        
        content = response.content.decode('utf-8')
        
        self.check_css_classes(content, 'View Receipt')
        self.check_typography_consistency(content, 'View Receipt')
        self.check_color_consistency(content, 'View Receipt')
        self.check_spacing_consistency(content, 'View Receipt')
        self.check_responsive_design(content, 'View Receipt')
        self.check_accessibility(content, 'View Receipt')
        self.check_decimal_consistency(content, 'View Receipt')
    
    def test_edit_receipt(self):
        """Test the edit receipt page"""
        print("\n" + "=" * 70)
        print("TESTING EDIT RECEIPT PAGE (/edit)")
        print("=" * 70)
        
        # Create an editable receipt
        edit_receipt = Receipt.objects.create(
            uploader_name='Edit Test User',
            restaurant_name='Edit Restaurant',
            date=timezone.now(),
            subtotal=Decimal('50.00'),
            tax=Decimal('5.00'),
            tip=Decimal('10.00'),
            total=Decimal('65.00'),
            processing_status='completed'
        )
        
        # Store in session
        session = self.client.session
        session['receipt_id'] = str(edit_receipt.id)
        session.save()
        
        response = self.client.get(f'/edit/{edit_receipt.slug}/')
        
        if response.status_code != 200:
            self.errors.append(f"Edit page returned {response.status_code}")
            return
        
        content = response.content.decode('utf-8')
        
        self.check_css_classes(content, 'Edit Receipt')
        self.check_typography_consistency(content, 'Edit Receipt')
        self.check_color_consistency(content, 'Edit Receipt')
        self.check_spacing_consistency(content, 'Edit Receipt')
        self.check_responsive_design(content, 'Edit Receipt')
        self.check_accessibility(content, 'Edit Receipt')
        self.check_decimal_consistency(content, 'Edit Receipt')
    
    def test_index_page(self):
        """Test the index/upload page"""
        print("\n" + "=" * 70)
        print("TESTING INDEX PAGE (/)")
        print("=" * 70)
        
        response = self.client.get('/')
        
        if response.status_code != 200:
            self.errors.append(f"Index page returned {response.status_code}")
            return
        
        content = response.content.decode('utf-8')
        
        self.check_css_classes(content, 'Index')
        self.check_typography_consistency(content, 'Index')
        self.check_color_consistency(content, 'Index')
        self.check_spacing_consistency(content, 'Index')
        self.check_responsive_design(content, 'Index')
        self.check_accessibility(content, 'Index')
    
    def test_javascript_consistency(self):
        """Test that shared JavaScript utilities are available"""
        print("\n" + "=" * 70)
        print("TESTING JAVASCRIPT UTILITIES")
        print("=" * 70)
        
        # Check that utils.js is served
        response = self.client.get('/static/js/utils.js')
        
        if response.status_code == 200:
            print("   ✅ utils.js is accessible")
        else:
            self.errors.append(f"utils.js returned {response.status_code}")
            print(f"   ❌ utils.js returned {response.status_code}")
        
        # Check that styles.css is served
        response = self.client.get('/static/css/styles.css')
        
        if response.status_code == 200:
            print("   ✅ styles.css is accessible")
        else:
            self.errors.append(f"styles.css returned {response.status_code}")
            print(f"   ❌ styles.css returned {response.status_code}")
    
    def test_print_styles(self):
        """Test that print styles are included"""
        print("\n" + "=" * 70)
        print("TESTING PRINT STYLES")
        print("=" * 70)
        
        response = self.client.get('/static/css/styles.css')
        
        if response.status_code == 200:
            content = response.content.decode('utf-8')
            if '@media print' in content:
                print("   ✅ Print styles are defined")
            else:
                self.warnings.append("No print styles found")
                print("   ⚠️  No print styles found")
    
    def run_all_tests(self):
        """Run all consistency tests"""
        print("\n" + "🎨" * 35)
        print("DESIGN SYSTEM CONSISTENCY TESTS")
        print("🎨" * 35)
        
        self.setup_test_data()
        
        # Run individual tests
        self.test_view_receipt()
        self.test_edit_receipt()
        self.test_index_page()
        self.test_javascript_consistency()
        self.test_print_styles()
        
        # Print summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"   - {error}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   - {warning}")
        
        if not self.errors:
            print("\n✅ All design consistency tests passed!")
            return True
        else:
            print(f"\n❌ {len(self.errors)} errors found")
            return False


def main():
    """Main test runner"""
    test = DesignConsistencyTest()
    success = test.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()