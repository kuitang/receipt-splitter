"""
Regression tests for cache invalidation ordering around transactions.

finalize_claims/subdivide_item run inside an atomic transaction. If the
receipt_view:*/participant_totals:* cache keys are deleted INSIDE the
transaction, a concurrent status poll can re-cache pre-commit data between
the delete and the commit, hiding the new data for the full cache TTL
(30-60 minutes). Invalidation must therefore run via transaction.on_commit,
i.e. only once the new data is visible to other connections.
"""
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from decimal import Decimal

from receipts.models import Receipt, LineItem, Claim
from receipts.services import ClaimService


class CacheInvalidationRaceTests(TestCase):
    """finalize_claims/subdivide_item must invalidate caches post-commit"""

    def setUp(self):
        self.service = ClaimService()
        cache.clear()

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
        self.receipt_id = str(self.receipt.id)
        self.view_key = f"receipt_view:{self.receipt_id}"
        self.totals_key = f"participant_totals:{self.receipt_id}"

    def tearDown(self):
        cache.clear()

    def _finalize_alice(self):
        return self.service.finalize_claims(
            self.receipt_id,
            "Alice",
            [{'line_item_id': str(self.item.id), 'quantity_numerator': 1}],
            "session-alice"
        )

    def test_finalize_claims_invalidates_cache_only_after_commit(self):
        """Simulate the race: a poll re-caches stale data after the writes but
        before commit; the post-commit invalidation must purge it."""
        stale_view = {'stale': True}
        stale_totals = {}  # pre-finalize state: nobody has claimed

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            result = self._finalize_alice()
            self.assertTrue(result['success'])

            # Racing status poll between the (old, in-transaction) delete and
            # the commit: it sees pre-commit data and re-primes the cache
            cache.set(self.view_key, stale_view, 1800)
            cache.set(self.totals_key, stale_totals, 3600)

            # Still inside the transaction: invalidation must NOT have run yet,
            # otherwise the poll's stale data would already be purged pre-commit
            self.assertEqual(cache.get(self.view_key), stale_view)
            self.assertEqual(cache.get(self.totals_key), stale_totals)

        self.assertTrue(callbacks, "finalize_claims must register an on_commit callback")

        # After commit: the stale re-cache is purged
        self.assertIsNone(cache.get(self.view_key))
        self.assertIsNone(cache.get(self.totals_key))

        # And a fresh status computation sees the new participant
        totals = self.service.get_participant_totals(self.receipt_id)
        self.assertIn("Alice", totals)
        self.assertEqual(totals["Alice"], Decimal("32.50"))

    def test_finalize_claims_returns_fresh_totals_despite_stale_cache(self):
        """The totals returned by finalize_claims must bypass a stale cache
        entry (invalidation no longer happens before the in-transaction read)."""
        cache.set(self.totals_key, {}, 3600)  # stale: no participants

        with self.captureOnCommitCallbacks(execute=True):
            result = self._finalize_alice()

        self.assertEqual(result['my_total'], 32.50)
        self.assertIn("Alice", result['participant_totals'])

    def test_subdivide_item_invalidates_cache_only_after_commit(self):
        stale_view = {'stale': True}

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            result = self.service.subdivide_item(str(self.item.id), 4)
            self.assertTrue(result['success'])

            # Racing poll re-caches pre-commit data
            cache.set(self.view_key, stale_view, 1800)
            cache.set(self.totals_key, {}, 3600)
            self.assertEqual(cache.get(self.view_key), stale_view)

        self.assertTrue(callbacks, "subdivide_item must register an on_commit callback")
        self.assertIsNone(cache.get(self.view_key))
        self.assertIsNone(cache.get(self.totals_key))
