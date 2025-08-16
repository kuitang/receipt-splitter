from django.db import models
from django.utils import timezone
from datetime import timedelta
import uuid


class Receipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uploader_name = models.CharField(max_length=50)
    restaurant_name = models.CharField(max_length=100)
    date = models.DateTimeField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2)
    tip = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    image_url = models.URLField(blank=True, null=True)
    image = models.ImageField(upload_to='receipts/', blank=True, null=True)
    is_finalized = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=30)
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return f'/r/{self.id}/'
    
    def __str__(self):
        return f"{self.restaurant_name} - {self.date.strftime('%Y-%m-%d')} - ${self.total}"


class LineItem(models.Model):
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=200)
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    prorated_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    prorated_tip = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
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
    grace_period_ends = models.DateTimeField()
    
    def save(self, *args, **kwargs):
        if not self.grace_period_ends:
            self.grace_period_ends = timezone.now() + timedelta(seconds=30)
        super().save(*args, **kwargs)
    
    def is_within_grace_period(self):
        return timezone.now() < self.grace_period_ends
    
    def get_share_amount(self):
        return self.line_item.get_per_item_share() * self.quantity_claimed
    
    def __str__(self):
        return f"{self.claimer_name} claimed {self.quantity_claimed}x {self.line_item.name}"


class ActiveViewer(models.Model):
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name='viewers')
    viewer_name = models.CharField(max_length=50)
    session_id = models.CharField(max_length=100)
    last_seen = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['receipt', 'session_id']
    
    def __str__(self):
        return f"{self.viewer_name} viewing {self.receipt}"