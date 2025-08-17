"""
Test suite for name-based claim calculations.
Tests the fix for the bug where claims were incorrectly calculated by session_id
instead of by claimer_name, causing confusion when users had multiple names.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
import json

from receipts.models import Receipt, LineItem, Claim
from receipts.repositories import ClaimRepository
from receipts.services import ClaimService


class ClaimTotalsByNameRepositoryTests(TestCase):
    """Test repository layer methods for name-based claim queries"""
    
    def setUp(self):
        self.repository = ClaimRepository()
        
        # Create a receipt with items
        self.receipt = Receipt.objects.create(
            uploader_name="Uploader",
            restaurant_name="Test Restaurant",
            date=timezone.now(),
            subtotal=Decimal("100.00"),
            tax=Decimal("10.00"),
            tip=Decimal("20.00"),
            total=Decimal("130.00"),
            is_finalized=True
        )
        
        # Create line items
        self.item1 = LineItem.objects.create(
            receipt=self.receipt,
            name="Pizza",
            quantity=2,
            unit_price=Decimal("25.00"),
            total_price=Decimal("50.00"),
            prorated_tax=Decimal("5.00"),
            prorated_tip=Decimal("10.00")
        )
        
        self.item2 = LineItem.objects.create(
            receipt=self.receipt,
            name="Salad",
            quantity=1,
            unit_price=Decimal("15.00"),
            total_price=Decimal("15.00"),
            prorated_tax=Decimal("1.50"),
            prorated_tip=Decimal("3.00")
        )
        
        # Create claims with SAME session but DIFFERENT names (the bug scenario)
        self.session_id = "test-session-123"
        
        # Claims as "Kui"
        self.claim1 = Claim.objects.create(
            line_item=self.item1,
            claimer_name="Kui",
            quantity_claimed=1,
            session_id=self.session_id,
            grace_period_ends=timezone.now() + timedelta(seconds=30)
        )
        
        # Claims as "Kui 5" (same session, different name)
        self.claim2 = Claim.objects.create(
            line_item=self.item2,
            claimer_name="Kui 5",
            quantity_claimed=1,
            session_id=self.session_id,
            grace_period_ends=timezone.now() + timedelta(seconds=30)
        )
        
        # Claims from different session with same name
        self.claim3 = Claim.objects.create(
            line_item=self.item1,
            claimer_name="Kui",
            quantity_claimed=1,
            session_id="different-session-456",
            grace_period_ends=timezone.now() + timedelta(seconds=30)
        )
    
    def test_get_claims_by_name_filters_correctly(self):
        """Test that get_claims_by_name only returns claims for specified name"""
        kui_claims = list(self.repository.get_claims_by_name(self.receipt.id, "Kui"))
        
        self.assertEqual(len(kui_claims), 2)  # Should get both "Kui" claims
        self.assertIn(self.claim1, kui_claims)
        self.assertIn(self.claim3, kui_claims)
        self.assertNotIn(self.claim2, kui_claims)  # Should NOT include "Kui 5"
    
    def test_get_claims_by_name_different_name(self):
        """Test getting claims for "Kui 5" name"""
        kui5_claims = list(self.repository.get_claims_by_name(self.receipt.id, "Kui 5"))
        
        self.assertEqual(len(kui5_claims), 1)
        self.assertEqual(kui5_claims[0], self.claim2)
    
    def test_get_claims_by_session_includes_all_names(self):
        """Test that session-based query includes all names (old behavior)"""
        session_claims = list(self.repository.get_claims_by_session(
            self.receipt.id, self.session_id
        ))
        
        self.assertEqual(len(session_claims), 2)
        self.assertIn(self.claim1, session_claims)  # "Kui"
        self.assertIn(self.claim2, session_claims)  # "Kui 5"
    
    def test_get_claims_by_name_empty_result(self):
        """Test getting claims for non-existent name"""
        no_claims = list(self.repository.get_claims_by_name(
            self.receipt.id, "NonExistent"
        ))
        
        self.assertEqual(len(no_claims), 0)


class ClaimTotalsByNameServiceTests(TestCase):
    """Test service layer methods for name-based calculations"""
    
    def setUp(self):
        self.service = ClaimService()
        
        # Create test data
        self.receipt = Receipt.objects.create(
            uploader_name="Uploader",
            restaurant_name="Test Restaurant",
            date=timezone.now(),
            subtotal=Decimal("60.00"),
            tax=Decimal("6.00"),
            tip=Decimal("12.00"),
            total=Decimal("78.00"),
            is_finalized=True
        )
        
        # Create items with proper prorations
        self.item1 = LineItem.objects.create(
            receipt=self.receipt,
            name="Burger",
            quantity=1,
            unit_price=Decimal("20.00"),
            total_price=Decimal("20.00"),
            prorated_tax=Decimal("2.00"),
            prorated_tip=Decimal("4.00")
        )
        
        self.item2 = LineItem.objects.create(
            receipt=self.receipt,
            name="Fries",
            quantity=1,
            unit_price=Decimal("10.00"),
            total_price=Decimal("10.00"),
            prorated_tax=Decimal("1.00"),
            prorated_tip=Decimal("2.00")
        )
        
        self.item3 = LineItem.objects.create(
            receipt=self.receipt,
            name="Drink",
            quantity=1,
            unit_price=Decimal("5.00"),
            total_price=Decimal("5.00"),
            prorated_tax=Decimal("0.50"),
            prorated_tip=Decimal("1.00")
        )
        
        self.session_id = "test-session-789"
        
        # Create claims under different names but same session
        Claim.objects.create(
            line_item=self.item1,
            claimer_name="Alice",
            quantity_claimed=1,
            session_id=self.session_id,
            grace_period_ends=timezone.now() + timedelta(seconds=30)
        )
        
        Claim.objects.create(
            line_item=self.item2,
            claimer_name="Alice 2",  # Different name, same session
            quantity_claimed=1,
            session_id=self.session_id,
            grace_period_ends=timezone.now() + timedelta(seconds=30)
        )
        
        Claim.objects.create(
            line_item=self.item3,
            claimer_name="Alice",
            quantity_claimed=1,
            session_id=self.session_id,
            grace_period_ends=timezone.now() + timedelta(seconds=30)
        )
    
    def test_calculate_name_total_single_name(self):
        """Test that calculate_name_total only sums claims for specified name"""
        alice_total = self.service.calculate_name_total(self.receipt.id, "Alice")
        
        # Alice claimed Burger ($20 + $2 tax + $4 tip = $26) 
        # and Drink ($5 + $0.50 tax + $1 tip = $6.50)
        # Total: $32.50
        expected_total = Decimal("32.50")
        self.assertEqual(alice_total, expected_total)
    
    def test_calculate_name_total_different_name(self):
        """Test total for "Alice 2" name"""
        alice2_total = self.service.calculate_name_total(self.receipt.id, "Alice 2")
        
        # Alice 2 only claimed Fries ($10 + $1 tax + $2 tip = $13)
        expected_total = Decimal("13.00")
        self.assertEqual(alice2_total, expected_total)
    
    def test_calculate_session_total_includes_all(self):
        """Test that session total includes all claims regardless of name"""
        session_total = self.service.calculate_session_total(
            self.receipt.id, self.session_id
        )
        
        # Should include all items: $26 + $13 + $6.50 = $45.50
        expected_total = Decimal("45.50")
        self.assertEqual(session_total, expected_total)
    
    def test_name_vs_session_total_difference(self):
        """Demonstrate the key difference between name and session totals"""
        name_total = self.service.calculate_name_total(self.receipt.id, "Alice")
        session_total = self.service.calculate_session_total(
            self.receipt.id, self.session_id
        )
        
        # Name total should be less than session total
        self.assertLess(name_total, session_total)
        self.assertEqual(name_total, Decimal("32.50"))
        self.assertEqual(session_total, Decimal("45.50"))
    
    def test_get_claims_for_name(self):
        """Test getting claims list by name"""
        alice_claims = self.service.get_claims_for_name(self.receipt.id, "Alice")
        
        self.assertEqual(len(alice_claims), 2)
        claimed_items = [claim.line_item.name for claim in alice_claims]
        self.assertIn("Burger", claimed_items)
        self.assertIn("Drink", claimed_items)
        self.assertNotIn("Fries", claimed_items)  # Claimed by "Alice 2"


class ClaimTotalsIntegrationTests(TestCase):
    """Integration tests for the complete flow"""
    
    def setUp(self):
        self.client = Client()
        
        # Create finalized receipt
        self.receipt = Receipt.objects.create(
            uploader_name="Restaurant",
            restaurant_name="The Gin Mill",
            date=timezone.now(),
            subtotal=Decimal("64.00"),
            tax=Decimal("0.00"),
            tip=Decimal("0.00"),
            total=Decimal("64.00"),
            is_finalized=True
        )
        
        # Create items similar to the bug screenshot
        self.item1 = LineItem.objects.create(
            receipt=self.receipt,
            name="PALOMA",
            quantity=1,
            unit_price=Decimal("17.68"),
            total_price=Decimal("17.68"),
            prorated_tax=Decimal("0.00"),
            prorated_tip=Decimal("0.00")
        )
        
        self.item2 = LineItem.objects.create(
            receipt=self.receipt,
            name="HAPPY HOUR BEER",
            quantity=1,
            unit_price=Decimal("5.20"),
            total_price=Decimal("5.20"),
            prorated_tax=Decimal("0.00"),
            prorated_tip=Decimal("0.00")
        )
        
        self.item3 = LineItem.objects.create(
            receipt=self.receipt,
            name="WELL TEQUILA",
            quantity=1,
            unit_price=Decimal("5.20"),
            total_price=Decimal("5.20"),
            prorated_tax=Decimal("0.00"),
            prorated_tip=Decimal("0.00")
        )
    
    def test_bug_scenario_same_session_different_names(self):
        """Test the exact bug scenario: same session, forced to use different name"""
        # Simulate first visit as "Kui"
        session = self.client.session
        session_key = session.session_key or session.save() or session.session_key
        
        # Create claims as "Kui"
        Claim.objects.create(
            line_item=self.item1,
            claimer_name="Kui",
            quantity_claimed=1,
            session_id=session_key,
            grace_period_ends=timezone.now() + timedelta(minutes=1)
        )
        
        # Later, same session but forced to use "Kui 5"
        Claim.objects.create(
            line_item=self.item2,
            claimer_name="Kui 5",
            quantity_claimed=1,
            session_id=session_key,
            grace_period_ends=timezone.now() + timedelta(minutes=1)
        )
        
        Claim.objects.create(
            line_item=self.item3,
            claimer_name="Kui 5",
            quantity_claimed=1,
            session_id=session_key,
            grace_period_ends=timezone.now() + timedelta(minutes=1)
        )
        
        # Test name-based calculations
        service = ClaimService()
        
        # "Kui" should only see PALOMA ($17.68)
        kui_total = service.calculate_name_total(self.receipt.id, "Kui")
        self.assertEqual(kui_total, Decimal("17.68"))
        
        # "Kui 5" should only see HAPPY HOUR BEER + WELL TEQUILA ($10.40)
        kui5_total = service.calculate_name_total(self.receipt.id, "Kui 5")
        self.assertEqual(kui5_total, Decimal("10.40"))
        
        # Session total would incorrectly show all ($28.08) - this was the bug
        session_total = service.calculate_session_total(self.receipt.id, session_key)
        self.assertEqual(session_total, Decimal("28.08"))
        
        # Verify the fix: name-based totals are correct and separate
        self.assertNotEqual(kui5_total, session_total)
    
    def test_participant_totals_grouped_by_name(self):
        """Test that participant totals correctly group by name"""
        session_key = "test-session"
        
        # Create mixed claims
        Claim.objects.create(
            line_item=self.item1,
            claimer_name="John",
            quantity_claimed=1,
            session_id=session_key,
            grace_period_ends=timezone.now() + timedelta(minutes=1)
        )
        
        Claim.objects.create(
            line_item=self.item2,
            claimer_name="John",
            quantity_claimed=1,
            session_id="different-session",
            grace_period_ends=timezone.now() + timedelta(minutes=1)
        )
        
        Claim.objects.create(
            line_item=self.item3,
            claimer_name="Jane",
            quantity_claimed=1,
            session_id=session_key,
            grace_period_ends=timezone.now() + timedelta(minutes=1)
        )
        
        service = ClaimService()
        participant_totals = service.get_participant_totals(self.receipt.id)
        
        # John should have total from both sessions
        self.assertEqual(participant_totals["John"], Decimal("22.88"))
        # Jane should have her total
        self.assertEqual(participant_totals["Jane"], Decimal("5.20"))