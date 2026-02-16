from django.db import models
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from fractions import Fraction
import uuid
import random
import string


class Receipt(models.Model):
    PROCESSING_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.CharField(max_length=10, unique=True, blank=True)
    uploader_name = models.CharField(max_length=50)
    restaurant_name = models.CharField(max_length=100)
    date = models.DateTimeField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=6)
    tax = models.DecimalField(max_digits=12, decimal_places=6)
    tip = models.DecimalField(max_digits=12, decimal_places=6)
    total = models.DecimalField(max_digits=12, decimal_places=6)
    image_url = models.URLField(blank=True, null=True)
    # Image removed - now stored in memory cache
    venmo_username = models.CharField(max_length=30, blank=True, default='')
    is_finalized = models.BooleanField(default=False)
    processing_status = models.CharField(max_length=20, choices=PROCESSING_STATUS_CHOICES, default='pending')
    processing_error = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    @staticmethod
    def generate_unique_slug(length=6, max_attempts=100):
        """Generate a unique short slug for the receipt.
        
        Args:
            length: Length of the slug (default 6 characters)
            max_attempts: Maximum number of attempts to generate a unique slug
        
        Returns:
            A unique slug string
        
        Raises:
            ValueError: If unable to generate a unique slug after max_attempts
        """
        chars = string.ascii_lowercase + string.digits
        
        for attempt in range(max_attempts):
            slug = ''.join(random.choice(chars) for _ in range(length))
            if not Receipt.objects.filter(slug=slug).exists():
                return slug
        
        # If we still can't find a unique slug, try longer ones
        for extra_length in range(1, 4):
            slug = ''.join(random.choice(chars) for _ in range(length + extra_length))
            if not Receipt.objects.filter(slug=slug).exists():
                return slug
        
        raise ValueError(f"Unable to generate unique slug after {max_attempts} attempts")
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=30)
        if not self.slug:
            self.slug = self.generate_unique_slug()
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return f'/r/{self.slug}/'
    
    def __str__(self):
        return f"{self.restaurant_name} - {self.date.strftime('%Y-%m-%d')} - ${self.total}"


class LineItem(models.Model):
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=200)
    quantity_numerator = models.PositiveIntegerField(default=1)
    quantity_denominator = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=6)
    total_price = models.DecimalField(max_digits=12, decimal_places=6)
    prorated_tax = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    prorated_tip = models.DecimalField(max_digits=12, decimal_places=6, default=0)

    def calculate_prorations(self):
        if self.receipt.subtotal > 0:
            proportion = self.total_price / self.receipt.subtotal
            self.prorated_tax = self.receipt.tax * proportion
            self.prorated_tip = self.receipt.tip * proportion

    @property
    def quantity(self):
        """Backward-compatible quantity property: returns numerator/denominator as Fraction."""
        return Fraction(self.quantity_numerator, self.quantity_denominator)

    def get_total_share(self):
        return self.total_price + self.prorated_tax + self.prorated_tip

    def get_per_portion_share(self):
        """Get the share amount for one portion (one numerator unit).

        With shared denominator, each portion = 1/quantity_numerator of the total share.
        """
        if self.quantity_numerator > 0:
            return self.get_total_share() / self.quantity_numerator
        return Decimal('0')

    def get_per_item_share(self):
        """Backward-compat alias. Returns per-portion share."""
        return self.get_per_portion_share()

    def get_available_quantity(self):
        """Available numerator units (same denominator as item)."""
        claimed_num = self.claims.aggregate(
            total=models.Sum('quantity_numerator')
        )['total'] or 0
        return self.quantity_numerator - claimed_num

    def __str__(self):
        if self.quantity_denominator == 1:
            return f"{self.name} x{self.quantity_numerator} - ${self.total_price}"
        return f"{self.name} x{self.quantity_numerator}/{self.quantity_denominator} - ${self.total_price}"


class Claim(models.Model):
    line_item = models.ForeignKey(LineItem, on_delete=models.CASCADE, related_name='claims')
    claimer_name = models.CharField(max_length=50)
    quantity_numerator = models.PositiveIntegerField(default=1)
    session_id = models.CharField(max_length=100)
    claimed_at = models.DateTimeField(auto_now_add=True)
    is_finalized = models.BooleanField(default=False)
    finalized_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.is_finalized and not self.finalized_at:
            self.finalized_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def quantity_denominator(self):
        """Denominator always comes from the parent line item."""
        return self.line_item.quantity_denominator

    @property
    def quantity_claimed(self):
        """Backward-compatible: returns numerator (same denominator as item)."""
        return self.quantity_numerator

    def get_share_amount(self):
        """Share = (claim_numerator / item_numerator) * item_total_share."""
        item = self.line_item
        if item.quantity_numerator > 0:
            frac = Fraction(self.quantity_numerator, item.quantity_numerator)
            return Decimal(frac.numerator) / Decimal(frac.denominator) * item.get_total_share()
        return Decimal('0')

    def __str__(self):
        status = " (finalized)" if self.is_finalized else ""
        return f"{self.claimer_name} claimed {self.quantity_numerator}x {self.line_item.name}{status}"

    class Meta:
        indexes = [
            models.Index(fields=['session_id']),
            models.Index(fields=['claimer_name']),
            models.Index(fields=['line_item', 'session_id']),
        ]


class ActiveViewer(models.Model):
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name='viewers')
    viewer_name = models.CharField(max_length=50)
    session_id = models.CharField(max_length=100)
    venmo_username = models.CharField(max_length=30, blank=True, default='')
    last_seen = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['receipt', 'session_id']
        indexes = [
            models.Index(fields=['session_id']),
        ]
    
    def __str__(self):
        return f"{self.viewer_name} viewing {self.receipt}"