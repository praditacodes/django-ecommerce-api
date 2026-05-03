from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Category, Product, ProductImage, ProductReview, ProductVariant


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


class ProductImageInline(admin.StackedInline):
    model = ProductImage
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'sort_order', 'parent', 'updated_at')
    list_filter = ('parent',)
    search_fields = ('name', 'slug', 'meta_title')
    autocomplete_fields = ('parent',)
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('sort_order', 'name')

    fields = ('name', 'slug', 'parent', 'sort_order', 'meta_title', 'meta_description')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'thumbnail',
        'name',
        'sku',
        'category',
        'display_price_preview',
        'availability',
        'featured',
        'stock_quantity_snapshot',
        'updated_at',
    )
    list_filter = ('availability', 'featured', 'category')
    search_fields = ('name', 'slug', 'sku', 'brand', 'short_description')
    autocomplete_fields = ('category',)
    ordering = ('-featured', '-created_at')
    list_select_related = ('category',)
    list_per_page = 40
    inlines = (ProductVariantInline, ProductImageInline)
    readonly_fields = ('created_at', 'updated_at')

    prepopulated_fields = {'slug': ('name',)}

    fieldsets = (
        (
            None,
            {
                'fields': ('name', 'slug', 'category', 'brand', 'sku'),
            },
        ),
        ('Copy', {'fields': ('short_description', 'description')}),
        ('Commercials', {'fields': ('price', 'discount_price', 'availability', 'featured')}),
        ('Inventory', {'fields': ('stock_quantity', 'low_stock_threshold')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

    actions = ('mark_available',)

    def get_queryset(self, request):  # type: ignore[override]
        qs = super().get_queryset(request)
        return qs.select_related('category').prefetch_related('variants', 'images')

    def display_price_preview(self, obj):  # noqa: D401 ignored
        return obj.current_price()

    display_price_preview.short_description = 'Price'

    def stock_quantity_snapshot(self, obj):
        return obj.get_effective_stock()

    stock_quantity_snapshot.short_description = 'Effective qty'

    @admin.action(description='Mark selected products as AVAILABLE')
    def mark_available(self, request, queryset):
        from .models import Availability

        queryset.update(availability=Availability.AVAILABLE)

    @staticmethod
    def thumbnail(obj):  # noqa: D401
        primary = (
            ProductImage.objects.filter(product_id=obj.pk)
            .order_by('-is_primary', 'sort_order', 'pk')
            .first()
        )
        if not primary or not primary.image:
            return '—'

        url = reverse('admin:products_product_change', args=(obj.pk,))
        return format_html('<a href="{}"><img src="{}" style="width:48px;height:48px;object-fit:cover;" /></a>', url, primary.image.url)

    thumbnail.short_description = 'Thumb'


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'moderation_status', 'verified_purchase', 'created_at')
    list_filter = ('moderation_status', 'verified_purchase')
    search_fields = ('product__slug', 'user__username', 'comment')
    autocomplete_fields = ('product', 'user')
    list_select_related = ('product', 'user')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('product', 'size', 'color', 'sku_suffix', 'stock_quantity')
    search_fields = ('sku_suffix', 'color', 'size', 'product__name')
    autocomplete_fields = ('product',)
