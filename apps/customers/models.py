from django.db import models
from django.utils import timezone
from apps.accounts.models import User

class Customer(models.Model):
    """
    Model to store customer information linked to User accounts.
    """
    BUSINESS_TYPE_CHOICES = (
        ('sole_proprietorship', 'Sole Proprietorship'),
        ('partnership', 'Partnership'),
        ('private_limited', 'Private Limited'),
        ('public_limited', 'Public Limited'),
        ('llp', 'LLP (Limited Liability Partnership)'),
        ('non_profit', 'Non-Profit Organization'),
        ('government', 'Government'),
        ('individual', 'Individual'),
        ('other', 'Other'),
    )
    
    # Link to User account for authentication
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,
        related_name='customer_profile',
        help_text="Linked user account for authentication"
    )
    
    # Basic Information
    customer_id = models.CharField(max_length=50, unique=True, editable=False)
    name = models.CharField(max_length=200, verbose_name="Customer Name")
    email = models.EmailField(unique=True, verbose_name="Email Address")
    phone = models.CharField(max_length=20, verbose_name="Contact Number", blank=True, null=True)
    alternate_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Alternate Phone")
    
    # Business Information
    business_name = models.CharField(max_length=200, verbose_name="Business/Company Name")
    business_type = models.CharField(
        max_length=50, 
        choices=BUSINESS_TYPE_CHOICES,
        default='individual',
        verbose_name="Business Type"
    )
    gst_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="GST Number")
    pan_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="PAN Number")
    
    # Address Information
    address_line1 = models.CharField(max_length=255, verbose_name="Address Line 1")
    address_line2 = models.CharField(max_length=255, blank=True, null=True, verbose_name="Address Line 2")
    city = models.CharField(max_length=100, verbose_name="City")
    state = models.CharField(max_length=100, verbose_name="State")
    country = models.CharField(max_length=100, default='India', verbose_name="Country")
    pincode = models.CharField(max_length=20, verbose_name="Pincode")
    
    # Additional Information
    website = models.URLField(blank=True, null=True, verbose_name="Website")
    notes = models.TextField(blank=True, null=True, verbose_name="Additional Notes")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='customers_created'
    )
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
        indexes = [
            models.Index(fields=['customer_id']),
            models.Index(fields=['email']),
            models.Index(fields=['business_name']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.business_name}"
    
    def save(self, *args, **kwargs):
        if not self.customer_id:
            self.customer_id = self.generate_customer_id()
        super().save(*args, **kwargs)
    
    def generate_customer_id(self):
        """Generate a unique customer ID."""
        today = timezone.now().strftime('%Y%m')
        last_customer = Customer.objects.filter(
            customer_id__startswith=f'CUST-{today}'
        ).order_by('-customer_id').first()
        
        if last_customer:
            last_number = int(last_customer.customer_id.split('-')[-1])
            new_number = last_number + 1
        else:
            new_number = 1
        
        return f'CUST-{today}-{new_number:04d}'
    
    def get_full_address(self):
        """Return formatted full address."""
        parts = [self.address_line1]
        if self.address_line2:
            parts.append(self.address_line2)
        parts.append(f"{self.city}, {self.state} - {self.pincode}")
        parts.append(self.country)
        return ', '.join(filter(None, parts))
    
    @property
    def full_name(self):
        """Return the customer name (from Customer model)"""
        return self.name
    
    @property
    def user_email(self):
        """Return the email from linked User account"""
        return self.user.email if self.user else self.email