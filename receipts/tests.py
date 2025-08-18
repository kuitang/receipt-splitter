from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timedelta
import json

from .models import Receipt, LineItem, Claim, ActiveViewer


class ReceiptModelTests(TestCase):
    def setUp(self):
        self.receipt = Receipt.objects.create(
            uploader_name="Test User",
            restaurant_name="Test Restaurant",
            date=timezone.now(),
            subtotal=Decimal("100.00"),
            tax=Decimal("10.00"),
            tip=Decimal("15.00"),
            total=Decimal("125.00")
        )
    
    def test_receipt_creation(self):
        self.assertEqual(self.receipt.uploader_name, "Test User")
        self.assertEqual(self.receipt.restaurant_name, "Test Restaurant")
        self.assertEqual(self.receipt.total, Decimal("125.00"))
        self.assertIsNotNone(self.receipt.id)
        self.assertIsNotNone(self.receipt.expires_at)
    
    def test_receipt_expiration(self):
        expected_expiration = self.receipt.created_at + timedelta(days=30)
        self.assertAlmostEqual(
            self.receipt.expires_at.timestamp(),
            expected_expiration.timestamp(),
            delta=1
        )
    
    def test_receipt_url(self):
        url = self.receipt.get_absolute_url()
        self.assertEqual(url, f'/r/{self.receipt.slug}/')


class LineItemModelTests(TestCase):
    def setUp(self):
        self.receipt = Receipt.objects.create(
            uploader_name="Test User",
            restaurant_name="Test Restaurant",
            date=timezone.now(),
            subtotal=Decimal("100.00"),
            tax=Decimal("10.00"),
            tip=Decimal("15.00"),
            total=Decimal("125.00")
        )
        
        self.item = LineItem.objects.create(
            receipt=self.receipt,
            name="Burger",
            quantity=2,
            unit_price=Decimal("10.00"),
            total_price=Decimal("20.00")
        )
    
    def test_line_item_creation(self):
        self.assertEqual(self.item.name, "Burger")
        self.assertEqual(self.item.quantity, 2)
        self.assertEqual(self.item.unit_price, Decimal("10.00"))
        self.assertEqual(self.item.total_price, Decimal("20.00"))
    
    def test_calculate_prorations(self):
        self.item.calculate_prorations()
        self.item.save()
        
        proportion = Decimal("20.00") / Decimal("100.00")
        expected_tax = Decimal("10.00") * proportion
        expected_tip = Decimal("15.00") * proportion
        
        self.assertEqual(self.item.prorated_tax, expected_tax)
        self.assertEqual(self.item.prorated_tip, expected_tip)
    
    def test_get_total_share(self):
        self.item.calculate_prorations()
        self.item.save()
        
        total_share = self.item.get_total_share()
        expected = Decimal("20.00") + self.item.prorated_tax + self.item.prorated_tip
        self.assertEqual(total_share, expected)
    
    def test_get_available_quantity(self):
        self.assertEqual(self.item.get_available_quantity(), 2)
        
        Claim.objects.create(
            line_item=self.item,
            claimer_name="Claimer 1",
            quantity_claimed=1,
            session_id="session1",
            grace_period_ends=timezone.now() + timedelta(seconds=30)
        )
        
        self.assertEqual(self.item.get_available_quantity(), 1)


class ClaimModelTests(TestCase):
    def setUp(self):
        self.receipt = Receipt.objects.create(
            uploader_name="Test User",
            restaurant_name="Test Restaurant",
            date=timezone.now(),
            subtotal=Decimal("100.00"),
            tax=Decimal("10.00"),
            tip=Decimal("15.00"),
            total=Decimal("125.00")
        )
        
        self.item = LineItem.objects.create(
            receipt=self.receipt,
            name="Burger",
            quantity=2,
            unit_price=Decimal("10.00"),
            total_price=Decimal("20.00")
        )
        self.item.calculate_prorations()
        self.item.save()
        
        self.claim = Claim.objects.create(
            line_item=self.item,
            claimer_name="Test Claimer",
            quantity_claimed=1,
            session_id="test_session"
        )
    
    def test_claim_creation(self):
        self.assertEqual(self.claim.claimer_name, "Test Claimer")
        self.assertEqual(self.claim.quantity_claimed, 1)
        self.assertIsNotNone(self.claim.grace_period_ends)
    
    def test_grace_period(self):
        self.assertTrue(self.claim.is_within_grace_period())
        
        self.claim.grace_period_ends = timezone.now() - timedelta(seconds=1)
        self.claim.save()
        
        self.assertFalse(self.claim.is_within_grace_period())
    
    def test_get_share_amount(self):
        unit_share = self.item.get_total_share() / self.item.quantity
        expected_share = unit_share * self.claim.quantity_claimed
        
        self.assertEqual(self.claim.get_share_amount(), expected_share)


class ViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.receipt = Receipt.objects.create(
            uploader_name="Test User",
            restaurant_name="Test Restaurant",
            date=timezone.now(),
            subtotal=Decimal("100.00"),
            tax=Decimal("10.00"),
            tip=Decimal("15.00"),
            total=Decimal("125.00"),
            is_finalized=True
        )
        
        self.item = LineItem.objects.create(
            receipt=self.receipt,
            name="Burger",
            quantity=2,
            unit_price=Decimal("10.00"),
            total_price=Decimal("20.00")
        )
        self.item.calculate_prorations()
        self.item.save()
    
    def test_index_view(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Communist Style")
        self.assertContains(response, "Upload Receipt")
    
    def test_view_receipt(self):
        # First, submit a name to view the receipt
        url = reverse('view_receipt', kwargs={'receipt_slug': self.receipt.slug})
        response = self.client.post(url, {'viewer_name': 'Test Viewer'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.receipt.restaurant_name)
        
        # Check that proration values are displayed correctly
        self.assertContains(response, 'Tax: $2.00')  # 20% of 10.00 tax
        self.assertContains(response, 'Tip: $3.00')  # 20% of 15.00 tip
        
        # Check that the per-item share is calculated and displayed
        # Total share is 20.00 + 2.00 + 3.00 = 25.00 for all 2 items
        # Per item: 25.00 / 2 = 12.50
        self.assertContains(response, 'data-amount="12.50"')
        self.assertContains(response, '$12.50</span>')
    
    def test_view_nonexistent_receipt(self):
        url = reverse('view_receipt', kwargs={'receipt_slug': 'nonexistent-slug'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
    
    def test_edit_receipt_unauthorized(self):
        url = reverse('edit_receipt', kwargs={'receipt_slug': self.receipt.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
    
    def test_view_receipt_with_multiple_items(self):
        # Add another item with different price
        item2 = LineItem.objects.create(
            receipt=self.receipt,
            name="Fries",
            quantity=1,
            unit_price=Decimal("5.00"),
            total_price=Decimal("5.00")
        )
        item2.calculate_prorations()
        item2.save()
        
        # Submit a name to view the receipt
        url = reverse('view_receipt', kwargs={'receipt_slug': self.receipt.slug})
        response = self.client.post(url, {'viewer_name': 'Test Viewer'})
        self.assertEqual(response.status_code, 200)
        
        # Check both items are displayed
        self.assertContains(response, "Burger")
        self.assertContains(response, "Fries")
        
        # The receipt subtotal is 100.00, but we only have items worth 25.00 (20+5)
        # So prorations are based on relative item values
        # Burger: 20.00 out of 25.00 total items = 80%
        # Fries: 5.00 out of 25.00 total items = 20%
        # But prorations use receipt subtotal (100.00) not actual items total
        # Burger gets: 20/100 = 20% of tax and tip
        # Fries gets: 5/100 = 5% of tax and tip
        self.assertContains(response, 'Tax: $0.50')  # 5% of 10.00
        self.assertContains(response, 'Tip: $0.75')  # 5% of 15.00
        
    def test_claim_item(self):
        session = self.client.session
        # Set up session with correct structure: session['receipts'][receipt_id]['viewer_name']
        if 'receipts' not in session:
            session['receipts'] = {}
        session['receipts'][str(self.receipt.id)] = {'viewer_name': 'Test Viewer'}
        session.save()
        
        url = reverse('claim_item', kwargs={'receipt_slug': self.receipt.slug})
        data = {
            'line_item_id': self.item.id,
            'quantity': 1
        }
        
        response = self.client.post(
            url,
            json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        claims = Claim.objects.filter(line_item=self.item)
        self.assertEqual(claims.count(), 1)
        self.assertEqual(claims.first().quantity_claimed, 1)

    def test_claim_item_on_unfinalized_receipt(self):
        self.receipt.is_finalized = False
        self.receipt.save()

        # Simulate the uploader making the claim
        session = self.client.session
        if 'receipts' not in session:
            session['receipts'] = {}
        session['receipts'][str(self.receipt.id)] = {
            'is_uploader': True,
            'viewer_name': self.receipt.uploader_name
        }
        session.save()

        url = reverse('claim_item', kwargs={'receipt_slug': self.receipt.slug})
        data = {
            'line_item_id': self.item.id,
            'quantity': 1
        }

        response = self.client.post(
            url,
            json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn('error', response_data)
        self.assertEqual(response_data['error'], 'Receipt must be finalized first')
        self.assertEqual(Claim.objects.count(), 0)

    def test_receipt_share_calculation_display(self):
        """Test that share amounts are correctly calculated and displayed in HTML"""
        # Create a receipt with simple numbers for easy verification
        receipt = Receipt.objects.create(
            uploader_name="Calculator Test",
            restaurant_name="Math Restaurant",
            date=timezone.now(),
            subtotal=Decimal("50.00"),
            tax=Decimal("5.00"),
            tip=Decimal("10.00"),
            total=Decimal("65.00"),
            is_finalized=True
        )
        
        # Item worth 40% of subtotal (20/50)
        item1 = LineItem.objects.create(
            receipt=receipt,
            name="Main Dish",
            quantity=2,
            unit_price=Decimal("10.00"),
            total_price=Decimal("20.00")
        )
        item1.calculate_prorations()
        item1.save()
        
        # Item worth 60% of subtotal (30/50)
        item2 = LineItem.objects.create(
            receipt=receipt,
            name="Appetizer",
            quantity=3,
            unit_price=Decimal("10.00"),
            total_price=Decimal("30.00")
        )
        item2.calculate_prorations()
        item2.save()
        
        # Submit a name to view the receipt
        url = reverse('view_receipt', kwargs={'receipt_slug': receipt.slug})
        response = self.client.post(url, {'viewer_name': 'Test Viewer'})
        
        # Item 1: 20.00 + (40% of 5.00 tax) + (40% of 10.00 tip) = 20 + 2 + 4 = 26.00 total
        # Per item: 26.00 / 2 = 13.00
        self.assertContains(response, 'data-amount="13.00"')
        self.assertContains(response, '$13.00</span>')
        
        # Item 2: 30.00 + (60% of 5.00 tax) + (60% of 10.00 tip) = 30 + 3 + 6 = 39.00 total
        # Per item: 39.00 / 3 = 13.00
        self.assertContains(response, 'data-amount="13.00"')
        self.assertContains(response, '$13.00</span>')
    
    def test_participant_totals_display(self):
        """Test that participant totals and unclaimed amounts are displayed correctly"""
        # Create some claims
        claim1 = Claim.objects.create(
            line_item=self.item,
            claimer_name="Alice",
            quantity_claimed=1,
            session_id="session_alice"
        )
        
        # Add another item
        item2 = LineItem.objects.create(
            receipt=self.receipt,
            name="Salad",
            quantity=1,
            unit_price=Decimal("15.00"),
            total_price=Decimal("15.00")
        )
        item2.calculate_prorations()
        item2.save()
        
        claim2 = Claim.objects.create(
            line_item=item2,
            claimer_name="Bob",
            quantity_claimed=1,
            session_id="session_bob"
        )
        
        # View the receipt
        url = reverse('view_receipt', kwargs={'receipt_slug': self.receipt.slug})
        response = self.client.post(url, {'viewer_name': 'Charlie'})
        
        # Check that participants are shown
        self.assertContains(response, "Alice")
        self.assertContains(response, "Bob")
        
        # Check that "Not Claimed" is shown
        self.assertContains(response, "Not Claimed")
        
        # Check the vertical totals display
        self.assertContains(response, "Subtotal")
        self.assertContains(response, "+ Tax")
        self.assertContains(response, "+ Tip")

    @patch('receipts.views.receipt_service.update_receipt')
    def test_update_receipt_unexpected_exception(self, mock_update_receipt):
        """Test that an unexpected exception in update_receipt returns a 500 and is logged."""
        mock_update_receipt.side_effect = Exception("Something went wrong")

        # Set up session for edit permission
        session = self.client.session
        if 'receipts' not in session:
            session['receipts'] = {}
        session['receipts'][str(self.receipt.id)] = {
            'is_uploader': True
        }
        session.save()

        self.receipt.is_finalized = False
        self.receipt.save()

        url = reverse('update_receipt', kwargs={'receipt_slug': self.receipt.slug})
        data = {'restaurant_name': 'New Name'}

        with self.assertLogs('receipts.views', level='ERROR') as cm:
            response = self.client.post(
                url,
                json.dumps(data),
                content_type='application/json'
            )
            self.assertIn("Exception in update_receipt", cm.output[0])

        self.assertEqual(response.status_code, 500)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], 'An unexpected error occurred.')

    @patch('receipts.views.receipt_service.create_receipt')
    def test_upload_receipt_unexpected_exception(self, mock_create_receipt):
        """Test that an unexpected exception in upload_receipt returns a 500 and is logged."""
        mock_create_receipt.side_effect = Exception("Something went wrong")

        url = reverse('upload_receipt')
        data = {'uploader_name': 'Test Uploader'}

        # A simple fake image file
        from django.core.files.uploadedfile import SimpleUploadedFile
        image = SimpleUploadedFile("test.jpg", b"file_content", content_type="image/jpeg")
        data['receipt_image'] = image

        with self.assertLogs('receipts.views', level='ERROR') as cm:
            response = self.client.post(url, data)
            self.assertIn("Error uploading receipt", cm.output[0])

        self.assertEqual(response.status_code, 500)

    @patch('receipts.views.receipt_service.finalize_receipt')
    def test_finalize_receipt_unexpected_exception(self, mock_finalize_receipt):
        """Test that an unexpected exception in finalize_receipt returns a 500 and is logged."""
        mock_finalize_receipt.side_effect = Exception("Something went wrong")

        session = self.client.session
        if 'receipts' not in session:
            session['receipts'] = {}
        session['receipts'][str(self.receipt.id)] = {'is_uploader': True}
        session.save()

        self.receipt.is_finalized = False
        self.receipt.save()

        url = reverse('finalize_receipt', kwargs={'receipt_slug': self.receipt.slug})

        with self.assertLogs('receipts.views', level='ERROR') as cm:
            response = self.client.post(url)
            self.assertIn("Exception in finalize_receipt", cm.output[0])

        self.assertEqual(response.status_code, 500)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], 'An unexpected error occurred.')

    @patch('receipts.views.claim_service.finalize_claims')
    def test_claim_item_unexpected_exception(self, mock_finalize_claims):
        """Test that an unexpected exception in claim_item returns a 500 and is logged."""
        mock_finalize_claims.side_effect = Exception("Something went wrong")

        session = self.client.session
        if 'receipts' not in session:
            session['receipts'] = {}
        session['receipts'][str(self.receipt.id)] = {'viewer_name': 'Test Viewer'}
        session.save()

        url = reverse('claim_item', kwargs={'receipt_slug': self.receipt.slug})
        data = {'claims': [{'line_item_id': self.item.id, 'quantity': 1}]}

        with self.assertLogs('receipts.views', level='ERROR') as cm:
            response = self.client.post(url, json.dumps(data), content_type='application/json')
            self.assertIn("Exception in claim_item", cm.output[0])

        self.assertEqual(response.status_code, 500)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], 'An unexpected error occurred.')

    @patch('receipts.views.receipt_service.get_receipt_for_viewing_by_slug')
    def test_get_claim_status_unexpected_exception(self, mock_get_receipt):
        """Test that an unexpected exception in get_claim_status returns a 500 and is logged."""
        mock_get_receipt.side_effect = Exception("Something went wrong")

        url = reverse('get_claim_status', kwargs={'receipt_slug': self.receipt.slug})

        with self.assertLogs('receipts.views', level='ERROR') as cm:
            response = self.client.get(url)
            self.assertIn("Exception in get_claim_status", cm.output[0])

        self.assertEqual(response.status_code, 500)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], 'An unexpected error occurred.')
