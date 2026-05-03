"""Mutable basket helpers — every mutation re-validates catalogue inventory."""

from __future__ import annotations

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Sum
from django.utils import timezone

from orders.constants import PRICE_TOLERANCE
from orders.models import Cart, CartItem
from products.checkout_prep import allocate_variant_or_product_line

from .pricing import catalogue_unit_price


def active_cart_for_user(user, *, create: bool = True) -> Cart | None:
    if create:
        cart, _ = Cart.objects.get_or_create(user=user)
        return cart

    return Cart.objects.filter(user=user).first()


def refresh_cart_item_prices(cart: Cart) -> None:
    """Snap cart rows to live catalogue pricing."""

    rows = list(cart.items.select_related('product'))
    if not rows:
        return

    for item in rows:
        canonical = catalogue_unit_price(item.product)
        item.unit_price = canonical
        item.subtotal = (canonical * Decimal(item.quantity)).quantize(Decimal('0.01'))

    CartItem.objects.bulk_update(rows, fields=('unit_price', 'subtotal'), batch_size=50)


def cart_subtotal(cart: Cart) -> Decimal:
    agg = cart.items.aggregate(total=Sum('subtotal'))['total']
    return Decimal(agg or Decimal('0.00')).quantize(Decimal('0.01'))


def validate_cart_prices(cart: Cart) -> None:
    """Detect stale rows before charging cards."""

    for item in cart.items.select_related('product'):
        canonical = catalogue_unit_price(item.product)
        drift = abs(Decimal(item.unit_price) - canonical)
        if drift > PRICE_TOLERANCE:
            raise ValueError(
                f'Sale price changed for {item.product.slug}. Refresh cart before checkout.'
            )


def _touch_cart(cart_pk: int) -> None:
    Cart.objects.filter(pk=cart_pk).update(updated_at=timezone.now())


def add_or_update_line(
    *,
    cart: Cart,
    product_slug: str,
    variant_id: int | None,
    quantity: int,
) -> CartItem:
    if quantity <= 0:
        raise ValueError('Quantity must be positive.')

    product, variant, _ = allocate_variant_or_product_line(
        product_slug=product_slug,
        variant_id=variant_id,
        qty=quantity,
    )

    canonical = catalogue_unit_price(product)

    def _attempt_merge():
        with transaction.atomic():
            Cart.objects.select_for_update().filter(pk=cart.pk).first()

            lookup = {'cart_id': cart.pk, 'product_id': product.pk}

            if variant:
                lookup['variant_id'] = variant.pk
                qs_filter = CartItem.objects.select_for_update().filter(**lookup)
            else:
                qs_filter = CartItem.objects.select_for_update().filter(
                    cart_id=cart.pk,
                    product_id=product.pk,
                    variant__isnull=True,
                )

            existing = qs_filter.first()

            if existing:
                merged_qty = existing.quantity + quantity

                allocate_variant_or_product_line(
                    product_slug=product_slug,
                    variant_id=variant_id,
                    qty=merged_qty,
                )

                existing.quantity = merged_qty
                existing.unit_price = canonical
                existing.save()

                _touch_cart(cart.pk)
                return existing

            item = CartItem.objects.create(
                cart_id=cart.pk,
                product_id=product.pk,
                variant_id=variant.pk if variant else None,
                quantity=quantity,
                unit_price=canonical,
                subtotal=Decimal('0.00'),
            )

            _touch_cart(cart.pk)
            return item

    try:
        return _attempt_merge()
    except IntegrityError:
        # Extremely narrow race on partial unique constraint — retry once.
        return _attempt_merge()


def set_line_quantity(*, item: CartItem, quantity: int) -> CartItem:
    if quantity <= 0:
        raise ValueError('Quantity must remain positive — delete the row instead.')

    allocate_variant_or_product_line(
        product_slug=item.product.slug,
        variant_id=item.variant_id,
        qty=quantity,
    )

    canonical = catalogue_unit_price(item.product)

    with transaction.atomic():
        Cart.objects.select_for_update().filter(pk=item.cart_id).first()

        locked_item = CartItem.objects.select_for_update().select_related('product').get(pk=item.pk)
        locked_item.quantity = quantity
        locked_item.unit_price = canonical
        locked_item.save()

        _touch_cart(locked_item.cart_id)
        return locked_item


def remove_line(*, item: CartItem) -> None:
    cart_pk = item.cart_id

    with transaction.atomic():
        Cart.objects.select_for_update().filter(pk=cart_pk).first()
        CartItem.objects.filter(pk=item.pk).delete()
        _touch_cart(cart_pk)


def clear_cart(*, cart: Cart) -> None:
    with transaction.atomic():
        Cart.objects.select_for_update().filter(pk=cart.pk).first()
        cart.items.all().delete()
        _touch_cart(cart.pk)


def hydrated_cart_queryset():
    return (
        Cart.objects.select_related('user')
        .prefetch_related(
            Prefetch(
                'items',
                queryset=CartItem.objects.select_related('product', 'variant').order_by('pk'),
            ),
        )
        .order_by('-updated_at')
    )
