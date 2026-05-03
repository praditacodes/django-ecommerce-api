"""DRF serializers — authoritative pricing stays server-side via cart/checkout services."""

from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from orders.models import Cart, CartItem, Order, OrderItem, PaymentMethod
from orders.services.cart_service import cart_subtotal


class CartItemSerializer(serializers.ModelSerializer):
    product_slug = serializers.CharField(source='product.slug', read_only=True)

    class Meta:
        model = CartItem
        fields = (
            'id',
            'product_slug',
            'variant_id',
            'quantity',
            'unit_price',
            'subtotal',
        )
        read_only_fields = fields


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    merchandise_total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ('id', 'items', 'merchandise_total', 'created_at', 'updated_at')
        read_only_fields = fields

    def get_merchandise_total(self, obj: Cart) -> str:
        total = cart_subtotal(obj)
        return format(total, 'f')


class CartItemCreateSerializer(serializers.Serializer):
    product_slug = serializers.SlugField()
    variant_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1)


class CartItemQuantitySerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)


class OrderItemSerializer(serializers.ModelSerializer):
    product_slug = serializers.CharField(source='product.slug', read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            'id',
            'product_slug',
            'variant_id',
            'quantity',
            'unit_price',
            'subtotal',
        )
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            'uuid',
            'status',
            'subtotal',
            'tax',
            'shipping_cost',
            'total',
            'payment_status',
            'payment_method',
            'stripe_payment_intent_id',
            'shipping_address_snapshot',
            'billing_address_snapshot',
            'items',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class OrderCreateSerializer(serializers.Serializer):
    shipping_address_id = serializers.IntegerField(min_value=1)
    billing_address_id = serializers.IntegerField(required=False, allow_null=True)
    payment_method = serializers.ChoiceField(
        choices=PaymentMethod.choices,
        default=PaymentMethod.COD,
    )
