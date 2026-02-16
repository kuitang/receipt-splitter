import pytest
from decimal import Decimal
from fractions import Fraction
from django.core.exceptions import ValidationError
from receipts.models import Receipt, LineItem, Claim
from receipts.services.claim_service import ClaimService, ReceiptNotFinalizedError, InsufficientQuantityError

@pytest.mark.django_db
class TestFractionalClaims:
    def setup_method(self):
        self.service = ClaimService()
        self.receipt = Receipt.objects.create(
            restaurant_name='Testaurant',
            subtotal=Decimal('100.00'),
            tax=Decimal('10.00'),
            tip=Decimal('20.00'),
            total=Decimal('130.00'),
            is_finalized=True,
            date= '2025-01-01T00:00:00Z'
        )
        # Item 1: 3 whole items, represented as 6/2 to allow half-item claims
        self.item1 = LineItem.objects.create(
            receipt=self.receipt,
            name='Item 1',
            quantity_numerator=6,
            quantity_denominator=2,
            unit_price=Decimal('20.00'),
            total_price=Decimal('60.00')
        )
        # Item 2: 1 whole item, represented as 3/3 to allow third-item claims
        self.item2 = LineItem.objects.create(
            receipt=self.receipt,
            name='Item 2',
            quantity_numerator=3,
            quantity_denominator=3,
            unit_price=Decimal('40.00'),
            total_price=Decimal('40.00')
        )

    def test_finalize_claims_with_fractions(self):
        """Test claiming fractional amounts using the shared denominator model.

        Item 1 has quantity_numerator=6, quantity_denominator=2 (i.e., 3 whole items).
        Claiming 1 numerator unit = 1/2 of a whole item.

        Item 2 has quantity_numerator=3, quantity_denominator=3 (i.e., 1 whole item).
        Claiming 1 numerator unit = 1/3 of a whole item.
        """
        claims_data = [
            {'line_item_id': self.item1.id, 'quantity_numerator': 1},
            {'line_item_id': self.item2.id, 'quantity_numerator': 1},
        ]
        result = self.service.finalize_claims(self.receipt.id, 'Alice', claims_data, 'session1')
        assert result['success']
        assert Claim.objects.filter(line_item=self.item1, claimer_name='Alice').count() == 1
        claim1 = Claim.objects.get(line_item=self.item1, claimer_name='Alice')
        assert claim1.quantity_numerator == 1
        # Denominator comes from parent item
        assert claim1.quantity_denominator == 2

        claim2 = Claim.objects.get(line_item=self.item2, claimer_name='Alice')
        assert claim2.quantity_numerator == 1
        assert claim2.quantity_denominator == 3

    def test_subdivide_and_claim(self):
        """Test that multiple users can claim portions of an item.

        Item 1 has quantity_numerator=6, quantity_denominator=2 (3 whole items).
        Alice claims 2 numerator units (= 1 whole item).
        Bob claims 2 numerator units (= 1 whole item).
        """
        # Alice claims 2 numerator units (1 whole item)
        self.service.finalize_claims(self.receipt.id, 'Alice', [{'line_item_id': self.item1.id, 'quantity_numerator': 2}], 'session1')

        # Bob claims 2 numerator units (1 whole item), 2 remain
        claims_data_bob = [
            {'line_item_id': self.item1.id, 'quantity_numerator': 2},
        ]
        result_bob = self.service.finalize_claims(self.receipt.id, 'Bob', claims_data_bob, 'session2')
        assert result_bob['success']

        claim_bob = Claim.objects.get(line_item=self.item1, claimer_name='Bob')
        assert claim_bob.quantity_numerator == 2
        assert claim_bob.quantity_denominator == 2  # from parent item

    def test_cannot_claim_more_than_available_fraction(self):
        """Test that claiming more numerator units than available fails."""
        claims_data = [
            {'line_item_id': self.item1.id, 'quantity_numerator': 7},  # only 6 available
        ]
        with pytest.raises(ValidationError):
            self.service.finalize_claims(self.receipt.id, 'Alice', claims_data, 'session1')

    def test_mixed_integer_and_fractional_claims(self):
        """Test multiple users claiming different amounts that sum to the total.

        Item 1 has quantity_numerator=6, quantity_denominator=2 (3 whole items).
        Alice claims 2 (1 whole item), Bob claims 1 (half item), Charlie claims 3 (1.5 items).
        Total: 2 + 1 + 3 = 6 numerator units = all claimed.
        """
        # Alice claims 2 numerator units (1 whole item)
        self.service.finalize_claims(self.receipt.id, 'Alice', [{'line_item_id': self.item1.id, 'quantity_numerator': 2}], 'session1')

        # Bob claims 1 numerator unit (half item)
        self.service.finalize_claims(self.receipt.id, 'Bob', [{'line_item_id': self.item1.id, 'quantity_numerator': 1}], 'session2')

        # Charlie claims the remaining 3 numerator units (1.5 items)
        self.service.finalize_claims(self.receipt.id, 'Charlie', [{'line_item_id': self.item1.id, 'quantity_numerator': 3}], 'session3')

        alice_claim = Claim.objects.get(claimer_name='Alice')
        bob_claim = Claim.objects.get(claimer_name='Bob')
        charlie_claim = Claim.objects.get(claimer_name='Charlie')

        # All claims share the same denominator (from the parent item)
        assert alice_claim.quantity_denominator == 2
        assert bob_claim.quantity_denominator == 2
        assert charlie_claim.quantity_denominator == 2

        # Total claimed numerator units should equal item's quantity_numerator
        total_claimed_num = alice_claim.quantity_numerator + bob_claim.quantity_numerator + charlie_claim.quantity_numerator
        assert total_claimed_num == self.item1.quantity_numerator

        # As fractions of whole items: 2/2 + 1/2 + 3/2 = 6/2 = 3 whole items
        total_claimed = Fraction(alice_claim.quantity_numerator, alice_claim.quantity_denominator) + \
                        Fraction(bob_claim.quantity_numerator, bob_claim.quantity_denominator) + \
                        Fraction(charlie_claim.quantity_numerator, charlie_claim.quantity_denominator)

        assert total_claimed == Fraction(3, 1)

    def test_subdivide_no_claims_allows_any_target(self):
        """With 0 claims, any target_parts should be valid.

        Item 1 has quantity_numerator=2, quantity_denominator=1 (2 whole items).
        With no claims, subdividing into 3 parts should work (not require multiples of 2).
        """
        # Create a simple 2-quantity item with no claims
        item = LineItem.objects.create(
            receipt=self.receipt,
            name='Shareable Plate',
            quantity_numerator=2,
            quantity_denominator=1,
            unit_price=Decimal('15.00'),
            total_price=Decimal('30.00'),
        )
        result = self.service.subdivide_item(str(item.id), 3)
        assert result['success']
        item.refresh_from_db()
        assert item.quantity_numerator == 3

    def test_subdivide_with_claims_requires_compatible_target(self):
        """With existing claims, target must preserve claim integrity.

        Item has 4 parts, Alice claimed 2. min_parts=2 (GCD of 4,2 is 2, 4/2=2).
        Target must be a multiple of 2.
        """
        item = LineItem.objects.create(
            receipt=self.receipt,
            name='Pizza',
            quantity_numerator=4,
            quantity_denominator=1,
            unit_price=Decimal('10.00'),
            total_price=Decimal('40.00'),
        )
        Claim.objects.create(
            line_item=item, claimer_name='Alice',
            quantity_numerator=2, session_id='s1',
        )
        # 3 is not a multiple of min_parts=2
        with pytest.raises(ValueError):
            self.service.subdivide_item(str(item.id), 3)
        # 4 is a multiple of 2
        result = self.service.subdivide_item(str(item.id), 4)
        assert result['success']
