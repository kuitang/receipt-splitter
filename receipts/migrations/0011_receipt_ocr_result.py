from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('receipts', '0010_add_viewer_venmo'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReceiptOCRResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('restaurant_name', models.CharField(max_length=100)),
                ('date', models.DateTimeField(blank=True, null=True)),
                ('subtotal', models.DecimalField(decimal_places=6, default=0, max_digits=12)),
                ('tax', models.DecimalField(decimal_places=6, default=0, max_digits=12)),
                ('tip', models.DecimalField(decimal_places=6, default=0, max_digits=12)),
                ('total', models.DecimalField(decimal_places=6, default=0, max_digits=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('receipt', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ocr_result',
                    to='receipts.receipt',
                )),
            ],
            options={
                'db_table': 'receipts_receipt_ocr_result',
            },
        ),
        migrations.CreateModel(
            name='ReceiptOCRLineItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('quantity_numerator', models.PositiveIntegerField(default=1)),
                ('quantity_denominator', models.PositiveIntegerField(default=1)),
                ('unit_price', models.DecimalField(decimal_places=6, max_digits=12)),
                ('total_price', models.DecimalField(decimal_places=6, max_digits=12)),
                ('prorated_tax', models.DecimalField(decimal_places=6, default=0, max_digits=12)),
                ('prorated_tip', models.DecimalField(decimal_places=6, default=0, max_digits=12)),
                ('ocr_result', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ocr_items',
                    to='receipts.receiptocrresult',
                )),
            ],
            options={
                'db_table': 'receipts_receipt_ocr_line_item',
            },
        ),
    ]
