from django.test import TestCase, Client
from django.urls import reverse
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
        self.assertEqual(url, f'/r/{self.receipt.id}/')


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
        url = reverse('view_receipt', kwargs={'receipt_id': self.receipt.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.receipt.restaurant_name)
    
    def test_view_nonexistent_receipt(self):
        from uuid import uuid4
        url = reverse('view_receipt', kwargs={'receipt_id': uuid4()})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
    
    def test_edit_receipt_unauthorized(self):
        url = reverse('edit_receipt', kwargs={'receipt_id': self.receipt.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
    
    def test_claim_item(self):
        session = self.client.session
        session[f'viewer_name_{self.receipt.id}'] = "Test Viewer"
        session.save()
        
        url = reverse('claim_item', kwargs={'receipt_id': self.receipt.id})
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