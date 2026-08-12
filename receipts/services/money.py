"""
Exact money splitting for claims.

Per-claim shares are computed exactly with Fraction and rounded to whole
cents only once, at the receipt-level aggregation boundary, using
largest-remainder cent allocation. This guarantees:
- participant totals + unclaimed == receipt.total exactly
- no participant drifts more than a cent from their exact share
- a fully-claimed receipt (by quantity) has exactly 0 unclaimed

Rounding per claim/portion and summing (the old approach) diverges from the
receipt total by sub-cent residue because prorated tax/tip are quantized to
6 decimal places per item.
"""
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
from math import floor
from typing import Dict, List, Tuple

CENT = Decimal('0.01')

# Dict key used internally for the unclaimed remainder during allocation
_UNCLAIMED = object()


def compute_receipt_split(receipt) -> Dict:
    """Compute exact-to-the-cent claim totals for a receipt.

    Works entirely from prefetched receipt.items / item.claims (no queries).

    Returns a dict with:
    - participant_totals: {claimer_name: Decimal} in whole cents
    - total_claimed / total_unclaimed: Decimals summing exactly to receipt.total
    - is_fully_claimed: quantity-based flag (every numerator unit of every
      item is claimed) — the true "everything is claimed" semantic, immune
      to rounding residue
    """
    exact_totals: Dict[str, Fraction] = {}
    is_fully_claimed = True
    has_items = False

    for item in receipt.items.all():
        has_items = True
        item_share = Fraction(item.get_total_share())
        claimed_num = 0
        for claim in item.claims.all():
            claimed_num += claim.quantity_numerator
            if item.quantity_numerator > 0:
                share = Fraction(claim.quantity_numerator, item.quantity_numerator) * item_share
                exact_totals[claim.claimer_name] = exact_totals.get(claim.claimer_name, Fraction(0)) + share
        if claimed_num < item.quantity_numerator:
            is_fully_claimed = False

    if not has_items or not exact_totals:
        is_fully_claimed = False

    if not exact_totals:
        return {
            'participant_totals': {},
            'total_claimed': Decimal('0.00'),
            'total_unclaimed': receipt.total.quantize(CENT),
            'is_fully_claimed': False,
        }

    # The unclaimed remainder competes for cents like a participant, so
    # everything always sums exactly to the receipt total. A fully-claimed
    # receipt leaves only sub-cent residue here, which allocates to 0 cents.
    entries = list(exact_totals.items())
    unclaimed_exact = Fraction(receipt.total) - sum(exact_totals.values())
    entries.append((_UNCLAIMED, unclaimed_exact))

    allocated = allocate_cents(entries, receipt.total)
    total_unclaimed = allocated.pop(_UNCLAIMED, Decimal('0.00'))
    total_claimed = receipt.total.quantize(CENT) - total_unclaimed

    return {
        'participant_totals': allocated,
        'total_claimed': total_claimed,
        'total_unclaimed': total_unclaimed,
        'is_fully_claimed': is_fully_claimed,
    }


def allocate_cents(entries: List[Tuple[object, Fraction]], total: Decimal) -> Dict[object, Decimal]:
    """Allocate `total` in whole cents across exact Fraction amounts.

    Largest-remainder method: floor everything to cents, then hand out the
    remaining cents to the largest fractional remainders. The result always
    sums exactly to `total` (rounded to the cent).
    """
    total_cents = int((total * 100).to_integral_value(rounding=ROUND_HALF_UP))

    allocations = []  # [key, cents, remainder]
    for key, amount in entries:
        cents = amount * 100
        base = floor(cents)
        allocations.append([key, base, cents - base])

    leftover = total_cents - sum(a[1] for a in allocations)

    # Distribute leftover cents, largest fractional remainder first
    # (stable: ties broken by original entry order)
    by_remainder = sorted(range(len(allocations)), key=lambda i: (-allocations[i][2], i))
    i = 0
    while leftover > 0:
        allocations[by_remainder[i % len(allocations)]][1] += 1
        leftover -= 1
        i += 1
    # Defensive: floors can only undershoot, but never leave anyone short
    # more than a cent if this ever runs.
    while leftover < 0:
        allocations[by_remainder[len(allocations) - 1 - (i % len(allocations))]][1] -= 1
        leftover += 1
        i += 1

    return {key: (Decimal(cents) / 100).quantize(CENT) for key, cents, _ in allocations}
