from django.db import models
from django.utils import timezone
from datetime import timedelta
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
    slug = models.CharField(max_length=10, unique=True, db_index=True, blank=True)
    uploader_name = models.CharField(max_length=50)
    restaurant_name = models.CharField(max_length=100)
    date = models.DateTimeField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=6)
    tax = models.DecimalField(max_digits=12, decimal_places=6)
    tip = models.DecimalField(max_digits=12, decimal_places=6)
    total = models.DecimalField(max_digits=12, decimal_places=6)
    image_url = models.URLField(blank=True, null=True)
    # Image removed - now stored in memory cache
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
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=6)
    total_price = models.DecimalField(max_digits=12, decimal_places=6)
    prorated_tax = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    prorated_tip = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    
    def calculate_prorations(self):
        if self.receipt.subtotal > 0:
            proportion = self.total_price / self.receipt.subtotal
            self.prorated_tax = self.receipt.tax * proportion
            self.prorated_tip = self.receipt.tip * proportion
    
    def get_total_share(self):
        return self.total_price + self.prorated_tax + self.prorated_tip
    
    def get_per_item_share(self):
        """Get the share amount for a single item"""
        if self.quantity > 0:
            return self.get_total_share() / self.quantity
        return Decimal('0')
    
    def get_available_quantity(self):
        claimed = self.claims.aggregate(
            total_claimed=models.Sum('quantity_claimed')
        )['total_claimed'] or 0
        return self.quantity - claimed
    
    def __str__(self):
        return f"{self.name} x{self.quantity} - ${self.total_price}"


class Claim(models.Model):
    line_item = models.ForeignKey(LineItem, on_delete=models.CASCADE, related_name='claims')
    claimer_name = models.CharField(max_length=50)
    quantity_claimed = models.IntegerField(default=1)
    session_id = models.CharField(max_length=100)
    claimed_at = models.DateTimeField(auto_now_add=True)
    is_finalized = models.BooleanField(default=False)
    finalized_at = models.DateTimeField(null=True, blank=True)
    
    # Legacy fields - will be removed in cleanup
    grace_period_ends = models.DateTimeField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        # Legacy grace period logic for backwards compatibility
        if not self.grace_period_ends and not self.is_finalized:
            self.grace_period_ends = timezone.now() + timedelta(seconds=30)
        
        # Set finalized_at when finalizing
        if self.is_finalized and not self.finalized_at:
            self.finalized_at = timezone.now()
            
        super().save(*args, **kwargs)
    
    def is_within_grace_period(self):
        """Legacy method - will be removed"""
        if self.is_finalized:
            return False
        return self.grace_period_ends and timezone.now() < self.grace_period_ends
    
    def get_share_amount(self):
        return self.line_item.get_per_item_share() * self.quantity_claimed
    
    def __str__(self):
        status = " (finalized)" if self.is_finalized else ""
        return f"{self.claimer_name} claimed {self.quantity_claimed}x {self.line_item.name}{status}"
    
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
    last_seen = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['receipt', 'session_id']
        indexes = [
            models.Index(fields=['session_id']),
        ]
    
    def __str__(self):
        return f"{self.viewer_name} viewing {self.receipt}"