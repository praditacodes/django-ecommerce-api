from django.contrib import admin

from orders.models import Cart, CartItem, Order, OrderItem, OrderStatus, PaymentStatus


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ('product', 'variant', 'quantity', 'unit_price', 'subtotal', 'created_at')
    can_delete = False


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'session_key', 'item_count', 'updated_at')
    list_select_related = ('user',)
    search_fields = ('user__email', 'user__username', 'session_key')
    readonly_fields = ('created_at', 'updated_at')
    inlines = (CartItemInline,)

    def item_count(self, obj: Cart) -> int:
        return obj.items.count()


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'variant', 'quantity', 'unit_price', 'subtotal')
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'uuid_short',
        'user',
        'status',
        'payment_status',
        'payment_method',
        'total',
        'created_at',
    )
    list_filter = ('status', 'payment_status', 'payment_method', 'created_at')
    search_fields = ('uuid', 'user__email', 'stripe_payment_intent_id')
    readonly_fields = ('uuid', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    inlines = (OrderItemInline,)

    fieldsets = (
        (
            None,
            {
                'fields': (
                    'uuid',
                    'user',
                    'status',
                    'subtotal',
                    'tax',
                    'shipping_cost',
                    'total',
                    'payment_status',
                    'payment_method',
                    'stripe_payment_intent_id',
                ),
            },
        ),
        ('Snapshots', {'fields': ('shipping_address_snapshot', 'billing_address_snapshot')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

    actions = ('mark_shipped',)

    def uuid_short(self, obj: Order) -> str:
        text = str(obj.uuid)
        return f'{text[:8]}…'

    uuid_short.short_description = 'UUID'

    def mark_shipped(self, request, queryset):
        queryset.filter(payment_status=PaymentStatus.PAID).exclude(
            status__in=(OrderStatus.CANCELLED, OrderStatus.REFUNDED),
        ).update(status=OrderStatus.SHIPPED)

    mark_shipped.short_description = 'Mark paid orders as shipped'
