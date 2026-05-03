"""Checkout orchestration — validates, prices, persists orders, then clears carts."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from orders.constants import DEFAULT_SHIPPING_FLAT, DEFAULT_TAX_RATE
from orders.models import Cart, CartItem, Order, OrderItem, PaymentMethod, PaymentStatus
from orders.services.address_snapshot import snapshot_address
from orders.services.cart_service import (
    cart_subtotal,
    clear_cart,
    refresh_cart_item_prices,
    validate_cart_prices,
)
from orders.services.inventory_service import deduct_lines
from products.checkout_prep import allocate_variant_or_product_line
from users.models import Address


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal('0.01'))


def load_cart_bundle(user) -> tuple[Cart, list[CartItem]]:
    cart = Cart.objects.filter(user=user).first()

    if cart is None:
        raise ValueError('Cart does not exist.')

    items = list(cart.items.select_related('product', 'variant').order_by('pk'))

    if not items:
        raise ValueError('Cannot checkout an empty cart.')

    return cart, items


def final_inventory_probe(items: list[CartItem]) -> None:
    for row in items:
        allocate_variant_or_product_line(
            product_slug=row.product.slug,
            variant_id=row.variant_id,
            qty=row.quantity,
        )


def checkout_from_cart(
    *,
    user,
    shipping_address_id: int,
    billing_address_id: int | None,
    payment_method: str,
    tax_rate: Decimal | None = None,
    shipping_flat: Decimal | None = None,
) -> Order:
    """
    Money-collecting COD/manual rail today.

    Stripe should:
      1. Create ``Order`` with ``payment_method=stripe`` + ``payment_status=unpaid``.
      2. Attach ``stripe_payment_intent_id`` once PaymentIntent succeeds.
      3. Flip ``payment_status`` / ``status`` from webhook handlers without mutating totals.
    """

    rate = DEFAULT_TAX_RATE if tax_rate is None else tax_rate
    ship_fee = DEFAULT_SHIPPING_FLAT if shipping_flat is None else shipping_flat

    shipping_address = Address.objects.filter(pk=shipping_address_id, user_id=user.id).first()

    if shipping_address is None:
        raise ValueError('Shipping address is unknown for this account.')

    billing_pk = billing_address_id or shipping_address_id

    billing_address = Address.objects.filter(pk=billing_pk, user_id=user.id).first()

    if billing_address is None:
        raise ValueError('Billing address is unknown for this account.')

    try:
        payment_enum = PaymentMethod(payment_method)
    except ValueError as exc:
        raise ValueError('Unsupported payment rail.') from exc

    cart, _bootstrap_items = load_cart_bundle(user)

    with transaction.atomic():
        Cart.objects.select_for_update().get(pk=cart.pk)

        refresh_cart_item_prices(cart)
        validate_cart_prices(cart)

        lines = list(cart.items.select_related('product', 'variant').order_by('pk'))

        final_inventory_probe(lines)

        merchandise_total = cart_subtotal(cart)

        tax_component = _money(merchandise_total * Decimal(rate))
        shipping_component = _money(ship_fee)

        grand_total = _money(merchandise_total + tax_component + shipping_component)

        order = Order.objects.create(
            user=user,
            subtotal=merchandise_total,
            tax=tax_component,
            shipping_cost=shipping_component,
            total=grand_total,
            payment_method=payment_enum,
            payment_status=PaymentStatus.UNPAID,
            shipping_address_snapshot=snapshot_address(shipping_address),
            billing_address_snapshot=snapshot_address(billing_address),
        )

        for row in lines:
            OrderItem.objects.create(
                order=order,
                product_id=row.product_id,
                variant_id=row.variant_id,
                quantity=row.quantity,
                unit_price=row.unit_price,
                subtotal=row.subtotal,
            )

        deduct_lines(lines)

        clear_cart(cart=cart)

        return order
