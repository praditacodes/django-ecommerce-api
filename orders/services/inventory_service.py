"""Atomic inventory mutations executed post-payment validation."""

from __future__ import annotations

from django.db import transaction

from orders.models import CartItem
from products.models import Product, ProductVariant


def deduct_lines(lines: list[CartItem]) -> None:
    """
    Locks catalogue rows in deterministic order to reduce deadlocks,
    then subtracts fulfilled quantities.
    """

    ordered = sorted(lines, key=lambda row: (row.product_id, row.variant_id or 0))

    with transaction.atomic():
        for row in ordered:
            qty = row.quantity

            if row.variant_id:
                variant = (
                    ProductVariant.objects.select_for_update()
                    .select_related('product')
                    .get(pk=row.variant_id)
                )

                if variant.stock_quantity < qty:
                    raise ValueError(
                        f'Insufficient stock for variant {variant.pk} during fulfilment.'
                    )

                variant.stock_quantity -= qty
                variant.save(update_fields=['stock_quantity'])
                continue

            product = Product.objects.select_for_update().get(pk=row.product_id)

            if product.stock_quantity < qty:
                raise ValueError(
                    f'Insufficient master stock for product {product.slug} during fulfilment.'
                )

            product.stock_quantity -= qty
            product.save(update_fields=['stock_quantity'])
