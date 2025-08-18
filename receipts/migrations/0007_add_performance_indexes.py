# Generated manually for database performance optimization
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('receipts', '0006_claim_finalized_at_claim_is_finalized_and_more'),
    ]

    operations = [
        # Add indexes for Claim model (SQLite compatible)
        migrations.RunSQL(
            sql="CREATE INDEX idx_claim_session_id ON receipts_claim(session_id);",
            reverse_sql="DROP INDEX idx_claim_session_id;"
        ),
        migrations.RunSQL(
            sql="CREATE INDEX idx_claim_claimer_name ON receipts_claim(claimer_name);",
            reverse_sql="DROP INDEX idx_claim_claimer_name;"
        ),
        migrations.RunSQL(
            sql="CREATE INDEX idx_claim_receipt_session ON receipts_claim(line_item_id, session_id);",
            reverse_sql="DROP INDEX idx_claim_receipt_session;"
        ),
        # Add index for ActiveViewer model
        migrations.RunSQL(
            sql="CREATE INDEX idx_activeviewer_session_id ON receipts_activeviewer(session_id);",
            reverse_sql="DROP INDEX idx_activeviewer_session_id;"
        ),
        # Add composite index for frequent claim queries
        migrations.RunSQL(
            sql="CREATE INDEX idx_claim_receipt_claimer ON receipts_claim(line_item_id, claimer_name);",
            reverse_sql="DROP INDEX idx_claim_receipt_claimer;"
        ),
    ]