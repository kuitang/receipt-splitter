"""Data migration: unescape legacy double-escaped text fields.

Before commit 6737179, InputValidator stored bleach-escaped text (e.g.
'&amp;', '&#x27;') in the database. The fix (strip_html_tags) now stores raw
text and relies on Django template autoescaping on output. This migration
applies html.unescape() exactly once to rows written before the fix.

Only fields that passed through InputValidator.validate_name /
validate_receipt_data (i.e. bleach.clean) are affected:
- Receipt.uploader_name, Receipt.restaurant_name
- LineItem.name
- Claim.claimer_name
- ActiveViewer.viewer_name

OCR snapshot models (ReceiptOCRResult, ReceiptOCRLineItem) are written
directly from OCR output without bleach and are intentionally untouched.

Pure-Python over querysets (DB-agnostic: SQLite in prod, Postgres in review
apps). Only rows whose value actually changes are rewritten.
"""

import html

from django.db import migrations

# (model_name, [field, ...]) pairs whose values passed through bleach.clean
AFFECTED_FIELDS = [
    ('Receipt', ['uploader_name', 'restaurant_name']),
    ('LineItem', ['name']),
    ('Claim', ['claimer_name']),
    ('ActiveViewer', ['viewer_name']),
]


def unescape_legacy_entities(apps, schema_editor):
    for model_name, fields in AFFECTED_FIELDS:
        model = apps.get_model('receipts', model_name)
        # Every HTML entity contains '&'; skip rows that can't be affected.
        for obj in model.objects.all().iterator():
            changed_fields = []
            for field in fields:
                value = getattr(obj, field)
                if value and '&' in value:
                    unescaped = html.unescape(value)
                    if unescaped != value:
                        setattr(obj, field, unescaped)
                        changed_fields.append(field)
            if changed_fields:
                obj.save(update_fields=changed_fields)


class Migration(migrations.Migration):

    dependencies = [
        ('receipts', '0011_receipt_ocr_result'),
    ]

    operations = [
        migrations.RunPython(
            unescape_legacy_entities,
            migrations.RunPython.noop,
        ),
    ]
