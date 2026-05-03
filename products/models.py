from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q, Sum
from django.utils.text import slugify


class Category(models.Model):
    """Hierarchical category tree with SEO-safe unique slugs (global per site)."""

    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('sort_order', 'name')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:255]
        super().save(*args, **kwargs)

    def breadcrumb_pairs(self):
        """Return [{'name','slug'}, ...] from root → current category for breadcrumbs."""
        chain = []
        node = self
        while node is not None:
            chain.append({'name': node.name, 'slug': node.slug})
            node = node.parent
        return list(reversed(chain))


class Availability(models.TextChoices):
    AVAILABLE = 'available', 'Available'
    OUT_OF_STOCK = 'out_of_stock', 'Out of stock'
    PREORDER = 'preorder', 'Preorder'


class Product(models.Model):
    """
    Purchasable item. Prefer variant-level inventory when variants exist;
    ``stock_quantity`` typically mirrors simple products without variants.

    Checkout/cart logic should rely on ``get_effective_stock()`` for availability.
    """

    LOW_STOCK_DEFAULT = 5

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
    )

    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    short_description = models.CharField(max_length=320, blank=True)
    description = models.TextField()
    brand = models.CharField(max_length=128, blank=True, db_index=True)
    sku = models.CharField(max_length=64, unique=True, db_index=True)

    price = models.DecimalField(max_digits=12, decimal_places=2)
    discount_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    stock_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(
        default=LOW_STOCK_DEFAULT,
        help_text='Used for admin/listing alerts; not a DB constraint.',
    )

    availability = models.CharField(
        max_length=20,
        choices=Availability.choices,
        default=Availability.AVAILABLE,
        db_index=True,
    )

    featured = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-featured', '-created_at')
        indexes = [
            models.Index(fields=('category', 'availability')),
            models.Index(fields=('featured', '-created_at')),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(stock_quantity__gte=0),
                name='product_stock_quantity_non_negative',
            ),
            models.CheckConstraint(
                condition=Q(price__gte=Decimal('0.00')),
                name='product_price_non_negative',
            ),
            models.CheckConstraint(
                condition=Q(discount_price__isnull=True) | Q(discount_price__gte=Decimal('0.00')),
                name='product_discount_price_non_negative',
            ),
            models.CheckConstraint(
                condition=Q(discount_price__isnull=True) | Q(discount_price__lt=F('price')),
                name='product_discount_below_price',
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:255]
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if (
            self.discount_price is not None
            and self.discount_price >= self.price
        ):
            raise ValidationError({'discount_price': 'Discount price must be less than price.'})

    def variant_stock_aggregate(self):
        qs = self.variants.all().aggregate(total=Sum('stock_quantity'))
        return qs['total'] or 0

    def get_effective_stock(self) -> int:
        """Use variant totals when variants exist; otherwise catalog-level quantity."""
        count = self.variants.count()
        if count > 0:
            return self.variant_stock_aggregate()
        return int(self.stock_quantity)

    def is_out_of_stock(self) -> bool:
        qty = self.get_effective_stock()

        if self.availability == Availability.OUT_OF_STOCK:
            return True

        if self.availability == Availability.PREORDER:
            return qty <= 0

        # AVAILABLE behaves like classic on-hand commerce rules.
        return qty <= 0

    def is_low_stock(self) -> bool:
        if self.availability != Availability.AVAILABLE:
            return False

        qty = self.get_effective_stock()
        return 0 < qty <= self.low_stock_threshold

    def current_price(self) -> Decimal:
        if self.discount_price is not None:
            return self.discount_price
        return self.price


class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants',
    )
    size = models.CharField(max_length=64)
    color = models.CharField(max_length=64)
    sku_suffix = models.CharField(
        max_length=32,
        blank=True,
        help_text='Appended or combined with parent SKU during checkout/export.',
    )
    stock_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = 'Product variants'
        constraints = [
            models.UniqueConstraint(
                fields=('product', 'size', 'color'),
                name='uniq_product_variant_size_color',
            ),
            models.CheckConstraint(
                condition=Q(stock_quantity__gte=0),
                name='variant_stock_non_negative',
            ),
        ]
        indexes = [
            models.Index(fields=('product', 'size')),
        ]

    def __str__(self):
        return f'{self.product.name} ({self.color} / {self.size})'


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images',
    )
    image = models.ImageField(upload_to='catalog/products/%Y/%m/')
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('sort_order', 'id')


class ReviewModeration(models.TextChoices):
    PENDING = 'pending', 'Pending'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'


class ProductReview(models.Model):
    """Attach reviews to authenticated customers; moderated for storefront display."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='product_reviews',
    )

    rating = models.PositiveSmallIntegerField(validators=[
        MinValueValidator(1),
        MaxValueValidator(5),
    ])
    comment = models.TextField()
    moderation_status = models.CharField(
        max_length=16,
        choices=ReviewModeration.choices,
        default=ReviewModeration.PENDING,
        db_index=True,
    )
    verified_purchase = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Set true automatically when wired to fulfilled orders.',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(fields=('product', 'user'), name='one_review_per_user_product'),
        ]
        indexes = [
            models.Index(fields=('product', 'moderation_status')),
        ]

    def __str__(self):
        return f'Review #{self.pk} ({self.product.slug})'

