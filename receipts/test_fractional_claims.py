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
        self.item1 = LineItem.objects.create(
            receipt=self.receipt,
            name='Item 1',
            quantity=3,
            quantity_numerator=3,
            quantity_denominator=1,
            unit_price=Decimal('20.00'),
            total_price=Decimal('60.00')
        )
        self.item2 = LineItem.objects.create(
            receipt=self.receipt,
            name='Item 2',
            quantity=1,
            quantity_numerator=1,
            quantity_denominator=1,
            unit_price=Decimal('40.00'),
            total_price=Decimal('40.00')
        )

    def test_finalize_claims_with_fractions(self):
        claims_data = [
            {'line_item_id': self.item1.id, 'quantity_numerator': 1, 'quantity_denominator': 2},
            {'line_item_id': self.item2.id, 'quantity_numerator': 1, 'quantity_denominator': 3},
        ]
        result = self.service.finalize_claims(self.receipt.id, 'Alice', claims_data, 'session1')
        assert result['success']
        assert Claim.objects.filter(line_item=self.item1, claimer_name='Alice').count() == 1
        claim1 = Claim.objects.get(line_item=self.item1, claimer_name='Alice')
        assert claim1.quantity_numerator == 1
        assert claim1.quantity_denominator == 2

        claim2 = Claim.objects.get(line_item=self.item2, claimer_name='Alice')
        assert claim2.quantity_numerator == 1
        assert claim2.quantity_denominator == 3

    def test_subdivide_and_claim(self):
        # Alice claims 1 of Item 1
        self.service.finalize_claims(self.receipt.id, 'Alice', [{'line_item_id': self.item1.id, 'quantity_numerator': 1, 'quantity_denominator': 1}], 'session1')

        # Bob subdivides the remaining 2 of item 1 into 3
        claims_data_bob = [
            {'line_item_id': self.item1.id, 'quantity_numerator': 2, 'quantity_denominator': 3},
        ]
        result_bob = self.service.finalize_claims(self.receipt.id, 'Bob', claims_data_bob, 'session2')
        assert result_bob['success']

        claim_bob = Claim.objects.get(line_item=self.item1, claimer_name='Bob')
        assert claim_bob.quantity_numerator == 2
        assert claim_bob.quantity_denominator == 3

    def test_cannot_claim_more_than_available_fraction(self):
        claims_data = [
            {'line_item_id': self.item1.id, 'quantity_numerator': 7, 'quantity_denominator': 2}, # 3.5, but only 3 available
        ]
        with pytest.raises(ValidationError):
            self.service.finalize_claims(self.receipt.id, 'Alice', claims_data, 'session1')

    def test_mixed_integer_and_fractional_claims(self):
        # Alice claims 1 of Item 1
        self.service.finalize_claims(self.receipt.id, 'Alice', [{'line_item_id': self.item1.id, 'quantity_numerator': 1, 'quantity_denominator': 1}], 'session1')

        # Bob claims 2/3 of the remaining
        self.service.finalize_claims(self.receipt.id, 'Bob', [{'line_item_id': self.item1.id, 'quantity_numerator': 2, 'quantity_denominator': 3}], 'session2')

        # Charlie claims the rest
        self.service.finalize_claims(self.receipt.id, 'Charlie', [{'line_item_id': self.item1.id, 'quantity_numerator': 4, 'quantity_denominator': 3}], 'session3')

        alice_claim = Claim.objects.get(claimer_name='Alice')
        bob_claim = Claim.objects.get(claimer_name='Bob')
        charlie_claim = Claim.objects.get(claimer_name='Charlie')

        total_claimed = Fraction(alice_claim.quantity_numerator, alice_claim.quantity_denominator) + \
                        Fraction(bob_claim.quantity_numerator, bob_claim.quantity_denominator) + \
                        Fraction(charlie_claim.quantity_numerator, charlie_claim.quantity_denominator)

        assert total_claimed == Fraction(3,1)
