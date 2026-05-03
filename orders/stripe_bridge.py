"""
Stripe boundary — HTTP verification stays in views; money mutations stay in services.

- Client flow: ``POST /api/orders/<uuid>/pay/`` → ``payment_service.create_payment_intent_for_order``.
- Server flow: ``POST /api/stripe/webhook/`` → ``stripe.Webhook.construct_event`` then
  ``payment_service.dispatch_stripe_webhook_event``.

Totals on ``Order`` are frozen at checkout; webhooks only flip ``payment_status``.
"""
