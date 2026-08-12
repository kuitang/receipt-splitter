"""
Regression tests for claim finalization visibility and retries.

Receipt state used to be cached per-process (receipt_view:*/
participant_totals:* keys in LocMemCache). With multiple machines the
invalidation could run on a different process than the one holding the
cached entry, so a status poll served a stale view for minutes after a
finalize succeeded. The cache is gone — these tests pin down that a
finalize is immediately visible to a subsequent status call, and that
retrying a finalize returns a clean 409 instead of a 500.
"""
import json
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from receipts.models import Receipt, LineItem, Claim


class FinalizeVisibilityTests(TestCase):
    """A finalize must be immediately visible to a subsequent status call"""

    def setUp(self):
        self.receipt = Receipt.objects.create(
            uploader_name="Uploader",
            restaurant_name="Test Restaurant",
            date=timezone.now(),
            subtotal=Decimal("50.00"),
            tax=Decimal("5.00"),
            tip=Decimal("10.00"),
            total=Decimal("65.00"),
            is_finalized=True
        )
        self.item = LineItem.objects.create(
            receipt=self.receipt,
            name="Pizza",
            quantity_numerator=2,
            unit_price=Decimal("25.00"),
            total_price=Decimal("50.00"),
            prorated_tax=Decimal("5.00"),
            prorated_tip=Decimal("10.00")
        )
        self.claim_url = reverse('claim_item', kwargs={'receipt_slug': self.receipt.slug})
        self.status_url = reverse('get_claim_status', kwargs={'receipt_slug': self.receipt.slug})

    def _set_viewer_name(self, client, name):
        session = client.session
        if 'receipts' not in session:
            session['receipts'] = {}
        session['receipts'][str(self.receipt.id)] = {'viewer_name': name}
        session.save()

    def _finalize_alice(self, client):
        self._set_viewer_name(client, 'Alice')
        data = {'claims': [{'line_item_id': str(self.item.id), 'quantity_numerator': 1}]}
        return client.post(self.claim_url, json.dumps(data), content_type='application/json')

    def test_finalize_immediately_visible_to_status_call(self):
        response = self._finalize_alice(self.client)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.content)['success'])

        # A different session (e.g. the uploader's polling page) must see the
        # new claim on its very next status poll — no stale cached view
        other_client = Client()
        status_response = other_client.get(self.status_url)
        self.assertEqual(status_response.status_code, 200)
        status = json.loads(status_response.content)

        participant_names = [p['name'] for p in status['participant_totals']]
        self.assertIn('Alice', participant_names)
        alice_total = next(
            p['amount'] for p in status['participant_totals'] if p['name'] == 'Alice'
        )
        self.assertEqual(alice_total, 32.50)
        self.assertEqual(status['total_claimed'], 32.50)

        item_status = status['items_with_claims'][0]
        self.assertEqual(item_status['available_quantity'], 1)
        self.assertEqual(item_status['claims'][0]['claimer_name'], 'Alice')

    def test_second_finalize_attempt_returns_409(self):
        first = self._finalize_alice(self.client)
        self.assertEqual(first.status_code, 200)

        # Retrying the finalize (e.g. after the first response was lost) must
        # return a clean 409 with a message, not a 500
        second = self._finalize_alice(self.client)
        self.assertEqual(second.status_code, 409)
        error = json.loads(second.content)
        self.assertIn('already been finalized', error['error'])
        self.assertTrue(error['already_finalized'])

        # The original claim is untouched
        claims = Claim.objects.filter(line_item=self.item)
        self.assertEqual(claims.count(), 1)
        self.assertEqual(claims.first().claimer_name, 'Alice')
