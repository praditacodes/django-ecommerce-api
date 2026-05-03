from decimal import Decimal

from products.models import Product


def catalogue_unit_price(product: Product) -> Decimal:
    """Always derive authoritative pricing server-side (discount-aware)."""

    return Decimal(product.current_price()).quantize(Decimal('0.01'))
