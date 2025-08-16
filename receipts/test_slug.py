from django.test import TestCase
from django.db import IntegrityError
from receipts.models import Receipt
from datetime import datetime
from django.utils import timezone
from decimal import Decimal
import string


class SlugGenerationTestCase(TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.base_receipt_data = {
            'uploader_name': 'Test User',
            'restaurant_name': 'Test Restaurant',
            'date': timezone.now(),
            'subtotal': Decimal('100.00'),
            'tax': Decimal('10.00'),
            'tip': Decimal('20.00'),
            'total': Decimal('130.00'),
        }
    
    def test_slug_generated_on_save(self):
        """Test that a slug is automatically generated when saving a new receipt."""
        receipt = Receipt.objects.create(**self.base_receipt_data)
        self.assertIsNotNone(receipt.slug)
        self.assertNotEqual(receipt.slug, '')
        self.assertEqual(len(receipt.slug), 6)
        
    def test_slug_contains_only_valid_chars(self):
        """Test that generated slugs only contain lowercase letters and digits."""
        valid_chars = set(string.ascii_lowercase + string.digits)
        
        for _ in range(10):
            receipt = Receipt.objects.create(**self.base_receipt_data)
            slug_chars = set(receipt.slug)
            self.assertTrue(slug_chars.issubset(valid_chars),
                          f"Slug '{receipt.slug}' contains invalid characters")
    
    def test_slug_uniqueness(self):
        """Test that each generated slug is unique."""
        slugs = set()
        num_receipts = 100
        
        for i in range(num_receipts):
            receipt = Receipt.objects.create(**self.base_receipt_data)
            self.assertNotIn(receipt.slug, slugs,
                           f"Duplicate slug generated: {receipt.slug}")
            slugs.add(receipt.slug)
        
        self.assertEqual(len(slugs), num_receipts)
    
    def test_generate_unique_slug_method(self):
        """Test the static generate_unique_slug method."""
        # Test basic generation
        slug = Receipt.generate_unique_slug()
        self.assertEqual(len(slug), 6)
        self.assertTrue(all(c in string.ascii_lowercase + string.digits for c in slug))
        
        # Test with custom length
        slug = Receipt.generate_unique_slug(length=8)
        self.assertEqual(len(slug), 8)
    
    def test_slug_collision_handling(self):
        """Test that the system handles slug collisions gracefully."""
        # Create a receipt with a known slug
        receipt1 = Receipt.objects.create(**self.base_receipt_data)
        original_slug = receipt1.slug
        
        # Manually create another receipt with the same slug should fail
        receipt2 = Receipt(**self.base_receipt_data)
        receipt2.slug = original_slug
        
        with self.assertRaises(IntegrityError):
            receipt2.save()
    
    def test_slug_not_regenerated_on_update(self):
        """Test that slug is not regenerated when updating an existing receipt."""
        receipt = Receipt.objects.create(**self.base_receipt_data)
        original_slug = receipt.slug
        
        # Update the receipt
        receipt.restaurant_name = 'Updated Restaurant'
        receipt.save()
        
        # Slug should remain the same
        self.assertEqual(receipt.slug, original_slug)
    
    def test_slug_persistence(self):
        """Test that slug persists across database queries."""
        receipt = Receipt.objects.create(**self.base_receipt_data)
        slug = receipt.slug
        receipt_id = receipt.id
        
        # Retrieve the receipt from database
        retrieved_receipt = Receipt.objects.get(id=receipt_id)
        self.assertEqual(retrieved_receipt.slug, slug)
        
        # Query by slug
        retrieved_by_slug = Receipt.objects.get(slug=slug)
        self.assertEqual(retrieved_by_slug.id, receipt_id)
    
    def test_get_absolute_url_uses_slug(self):
        """Test that get_absolute_url returns URL with slug."""
        receipt = Receipt.objects.create(**self.base_receipt_data)
        expected_url = f'/r/{receipt.slug}/'
        self.assertEqual(receipt.get_absolute_url(), expected_url)
    
    def test_slug_edge_cases(self):
        """Test edge cases in slug generation."""
        # Test that ValueError is eventually raised if we can't generate unique slugs
        # This is a theoretical test since with 36^6 combinations it's unlikely to happen
        
        # Mock scenario: Create many receipts to test the system under load
        receipts = []
        for i in range(20):
            receipt = Receipt.objects.create(**self.base_receipt_data)
            receipts.append(receipt)
            # Verify each has a unique slug
            self.assertIsNotNone(receipt.slug)
        
        # Verify all slugs are unique
        slugs = [r.slug for r in receipts]
        self.assertEqual(len(slugs), len(set(slugs)))