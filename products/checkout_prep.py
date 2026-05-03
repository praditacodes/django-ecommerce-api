"""Inventory helpers slated for reuse by cart/order services."""

from django.shortcuts import get_object_or_404

from .models import Availability, ProductVariant
from .querysets import refined_catalog


def get_cart_snapshot(*, slug: str):
    """
    Lightweight helper that returns the optimised catalogue queryset row.

    Intended for CheckoutLine validation so stock math stays deterministic.
    """

    return get_object_or_404(refined_catalog(include_images=True, include_variants=True), slug=slug)


def allocate_variant_or_product_line(
    *,
    product_slug: str,
    variant_id: int | None,
    qty: int,
):
    """Same-origin validation entrypoint for future cart serializers."""

    if qty <= 0:
        raise ValueError('Cart quantity must be positive.')

    product = get_object_or_404(refined_catalog(), slug=product_slug)

    variants = ProductVariant.objects.filter(product_id=product.pk)
    if variants.exists():
        if variant_id is None:
            raise ValueError('Variant selection required for assorted inventory.')

        variant = get_object_or_404(ProductVariant, pk=variant_id, product_id=product.pk)
        stock = variant.stock_quantity
        if stock < qty:
            raise ValueError(f'Insufficient variant stock ({stock} remaining).')

        if product.availability not in (Availability.AVAILABLE, Availability.PREORDER):
            raise ValueError(f'Listing "{product.slug}" is not currently orderable.')

        return product, variant, stock

    if product.stock_quantity < qty:
        raise ValueError(f'Insufficient product stock ({product.stock_quantity}).')

    if product.availability not in (Availability.AVAILABLE, Availability.PREORDER):
        raise ValueError(f'Listing "{product.slug}" is not currently orderable.')

    return product, None, product.stock_quantity
