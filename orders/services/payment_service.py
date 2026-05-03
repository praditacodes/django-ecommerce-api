"""Stripe PaymentIntent creation and webhook side-effects — totals stay immutable."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction

import stripe

from orders.models import Order, PaymentMethod, PaymentStatus

# Stripe documents zero-decimal currencies; amounts are whole currency units.
_ZERO_DECIMAL_CURRENCIES = frozenset(
    {
        'bif',
        'clp',
        'djf',
        'gnf',
        'jpy',
        'kmf',
        'krw',
        'mga',
        'pyg',
        'rwf',
        'ugx',
        'vnd',
        'vuv',
        'xaf',
        'xof',
        'xpf',
    }
)


def _configure_stripe() -> None:
    key = getattr(settings, 'STRIPE_SECRET_KEY', '').strip()
    if not key:
        raise ValueError('Stripe is not configured (missing STRIPE_SECRET_KEY).')
    stripe.api_key = key


def order_total_to_stripe_amount(total: Decimal, currency: str) -> int:
    """
    Convert stored ``Order.total`` (major units, e.g. dollars) to Stripe's integer amount.

    https://docs.stripe.com/currencies#zero-decimal
    """

    cur = currency.strip().lower()
    quantized_major = total.quantize(Decimal('0.01'))

    if cur in _ZERO_DECIMAL_CURRENCIES:
        return int(quantized_major.quantize(Decimal('1'), rounding=ROUND_HALF_UP))

    return int((quantized_major * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def create_payment_intent_for_order(order: Order) -> dict:
    """
    Create a PaymentIntent priced exactly from ``order.total`` (never from client input).

    Persists ``stripe_payment_intent_id`` after Stripe confirms creation. Stripe calls run
    outside row locks; only the ID write is transactional.
    """

    if order.payment_method != PaymentMethod.STRIPE:
        raise ValueError('This order does not use Stripe.')

    if order.payment_status != PaymentStatus.UNPAID:
        raise ValueError('Order is not payable.')

    _configure_stripe()

    currency = getattr(settings, 'STRIPE_CURRENCY', 'usd').strip().lower()
    amount = order_total_to_stripe_amount(order.total, currency)

    intent = stripe.PaymentIntent.create(
        amount=amount,
        currency=currency,
        metadata={'order_id': str(order.pk)},
        payment_method_types=['card'],
    )

    with transaction.atomic():
        locked = Order.objects.select_for_update().get(pk=order.pk)
        if locked.payment_status != PaymentStatus.UNPAID:
            raise ValueError('Order is no longer payable.')
        if locked.payment_method != PaymentMethod.STRIPE:
            raise ValueError('This order does not use Stripe.')

        locked.stripe_payment_intent_id = intent.id
        locked.save(update_fields=('stripe_payment_intent_id', 'updated_at'))

    return {'client_secret': intent.client_secret}


def mark_order_paid_for_payment_intent(*, payment_intent_id: str) -> None:
    """Idempotent: only moves UNPAID → PAID."""

    Order.objects.filter(
        stripe_payment_intent_id=payment_intent_id,
        payment_status=PaymentStatus.UNPAID,
    ).update(payment_status=PaymentStatus.PAID)


def mark_order_failed_for_payment_intent(*, payment_intent_id: str) -> None:
    """Idempotent: only moves UNPAID → FAILED (never overwrites PAID)."""

    Order.objects.filter(
        stripe_payment_intent_id=payment_intent_id,
        payment_status=PaymentStatus.UNPAID,
    ).update(payment_status=PaymentStatus.FAILED)


def dispatch_stripe_webhook_event(event: stripe.Event) -> None:
    if event.type == 'payment_intent.succeeded':
        mark_order_paid_for_payment_intent(payment_intent_id=event.data.object.id)
    elif event.type == 'payment_intent.payment_failed':
        mark_order_failed_for_payment_intent(payment_intent_id=event.data.object.id)
