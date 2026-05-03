import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class Cart(models.Model):
    """
    Shopping basket.

    ``user`` is nullable so anonymous/session carts can be added later; currently API binds carts to JWT users only.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart',
        null=True,
        blank=True,
        db_index=True,
    )
    session_key = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text='Reserved for guest checkout orchestration.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-updated_at',)
        indexes = [
            models.Index(fields=('session_key',), name='orders_cart_sess_idx'),
        ]

    def __str__(self):
        owner = self.user_id or self.session_key or 'anonymous'
        return f'Cart #{self.pk} ({owner})'


class CartItem(models.Model):
    """Line belonging to a cart — immutable SKU linkage via FK protections."""

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='+',
    )
    variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='+',
    )

    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('cart', 'product'),
                condition=Q(variant__isnull=True),
                name='cart_unique_simple_product_line',
            ),
            models.UniqueConstraint(
                fields=('cart', 'product', 'variant'),
                condition=Q(variant__isnull=False),
                name='cart_unique_variant_product_line',
            ),
            models.CheckConstraint(
                condition=Q(quantity__gte=1),
                name='cart_item_quantity_positive',
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=Decimal('0')),
                name='cart_item_price_nonneg',
            ),
            models.CheckConstraint(
                condition=Q(subtotal__gte=Decimal('0')),
                name='cart_item_subtotal_nonneg',
            ),
        ]
        indexes = [
            models.Index(fields=('cart', '-updated_at'), name='orders_cartitems_cart_upd'),
        ]

    def __str__(self):
        suffix = f' / variant={self.variant_id}' if self.variant_id else ''
        return f'{self.quantity} × {self.product.slug}{suffix}'

    def clean(self):
        if self.variant_id and self.variant.product_id != self.product_id:
            raise ValidationError('Variant does not belong to the referenced product.')

    def save(self, *args, **kwargs):
        self.full_clean(exclude=('cart',))
        q = Decimal(self.quantity)
        self.subtotal = (Decimal(self.unit_price) * q).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)


class OrderStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PAID = 'paid', 'Paid'
    SHIPPED = 'shipped', 'Shipped'
    DELIVERED = 'delivered', 'Delivered'
    CANCELLED = 'cancelled', 'Cancelled'
    REFUNDED = 'refunded', 'Refunded'


class PaymentStatus(models.TextChoices):
    UNPAID = 'unpaid', 'Unpaid'
    PAID = 'paid', 'Paid'
    FAILED = 'failed', 'Failed'
    REFUNDED = 'refunded', 'Refunded'


class PaymentMethod(models.TextChoices):
    COD = 'cod', 'Cash on delivery'
    STRIPE = 'stripe', 'Stripe'
    MANUAL = 'manual', 'Manual / invoicing'


class Order(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='orders',
    )

    status = models.CharField(
        max_length=16,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
        db_index=True,
    )

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    shipping_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    payment_status = models.CharField(
        max_length=16,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID,
        db_index=True,
    )
    payment_method = models.CharField(
        max_length=32,
        choices=PaymentMethod.choices,
        default=PaymentMethod.COD,
    )

    # Stripe integration placeholder — populate during PaymentIntent confirmation.
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, db_index=True)

    shipping_address_snapshot = models.JSONField(default=dict, blank=True)
    billing_address_snapshot = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('user', '-created_at'), name='orders_order_user_crt'),
            models.Index(fields=('status', '-created_at'), name='orders_order_stat_crt'),
        ]

    def __str__(self):
        return f'Order {self.uuid}'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='+',
    )
    variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='+',
    )

    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=('order', 'id'), name='orders_orditems_ord_id'),
        ]

    def save(self, *args, **kwargs):
        q = Decimal(self.quantity)
        self.subtotal = (Decimal(self.unit_price) * q).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)
