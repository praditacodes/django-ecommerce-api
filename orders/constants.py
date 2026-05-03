"""Checkout defaults — centralise here until migrated to env-backed settings."""

from decimal import Decimal

# Percentage expressed as decimal fraction (e.g. 0.0825 == 8.25%).
DEFAULT_TAX_RATE = Decimal('0.00')

DEFAULT_SHIPPING_FLAT = Decimal('0.00')

# Canonical catalogue comparison tolerance when spotting stale cart prices.
PRICE_TOLERANCE = Decimal('0.02')
