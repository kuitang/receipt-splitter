"""
Migration: shared-denominator model + venmo_username

1. Add Receipt.venmo_username
2. Remove LineItem.quantity (deprecated)
3. Remove Claim.quantity_claimed (deprecated)
4. Remove Claim.quantity_denominator (now on LineItem only)
5. Remove Claim.grace_period_ends (legacy)
6. Data migration: scale claims to share parent LineItem's denominator
"""
from django.db import migrations, models
from fractions import Fraction
from math import gcd


def lcm(a, b):
    return abs(a * b) // gcd(a, b)


def scale_claims_to_shared_denominator(apps, schema_editor):
    """
    For each LineItem, compute the LCM of the item's denominator and all
    its claims' denominators. Scale everything to that common denominator,
    then set each claim's numerator accordingly and drop the per-claim
    denominator.
    """
    LineItem = apps.get_model('receipts', 'LineItem')
    Claim = apps.get_model('receipts', 'Claim')

    for item in LineItem.objects.prefetch_related('claims').all():
        # Collect all denominators: item + each claim
        denominators = [item.quantity_denominator]
        for claim in item.claims.all():
            denominators.append(claim.quantity_denominator)

        # Compute LCM of all denominators
        common_den = denominators[0]
        for d in denominators[1:]:
            common_den = lcm(common_den, d)

        # Scale item
        item_scale = common_den // item.quantity_denominator
        item.quantity_numerator *= item_scale
        item.quantity_denominator = common_den
        item.save(update_fields=['quantity_numerator', 'quantity_denominator'])

        # Scale each claim
        for claim in item.claims.all():
            claim_scale = common_den // claim.quantity_denominator
            claim.quantity_numerator *= claim_scale
            claim.save(update_fields=['quantity_numerator'])


class Migration(migrations.Migration):

    dependencies = [
        ("receipts", "0008_fractional_quantities"),
    ]

    operations = [
        # 1. Add venmo_username to Receipt
        migrations.AddField(
            model_name="receipt",
            name="venmo_username",
            field=models.CharField(blank=True, default="", max_length=30),
        ),

        # 2. Data migration: scale claims before removing columns
        migrations.RunPython(
            scale_claims_to_shared_denominator,
            migrations.RunPython.noop,
        ),

        # 3. Remove deprecated fields
        migrations.RemoveField(
            model_name="lineitem",
            name="quantity",
        ),
        migrations.RemoveField(
            model_name="claim",
            name="quantity_claimed",
        ),
        migrations.RemoveField(
            model_name="claim",
            name="quantity_denominator",
        ),
        migrations.RemoveField(
            model_name="claim",
            name="grace_period_ends",
        ),
    ]
