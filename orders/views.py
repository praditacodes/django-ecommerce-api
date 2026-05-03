"""Authenticated cart + order HTTP surface."""

from __future__ import annotations

from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

import stripe
from stripe.error import SignatureVerificationError

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import CartItem, Order, PaymentMethod, PaymentStatus
from orders.services.payment_service import (
    create_payment_intent_for_order,
    dispatch_stripe_webhook_event,
)
from orders.serializers import (
    CartItemCreateSerializer,
    CartItemQuantitySerializer,
    CartItemSerializer,
    CartSerializer,
    OrderCreateSerializer,
    OrderSerializer,
)
from orders.services.cart_service import (
    active_cart_for_user,
    add_or_update_line,
    hydrated_cart_queryset,
    refresh_cart_item_prices,
    remove_line,
    set_line_quantity,
)
from orders.services.checkout_service import checkout_from_cart


class CartDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        cart = active_cart_for_user(request.user)
        refresh_cart_item_prices(cart)
        cart = hydrated_cart_queryset().get(pk=cart.pk)
        return Response(CartSerializer(cart).data)


class CartItemCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        ser = CartItemCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        cart = active_cart_for_user(request.user)

        try:
            row = add_or_update_line(
                cart=cart,
                product_slug=ser.validated_data['product_slug'],
                variant_id=ser.validated_data.get('variant_id'),
                quantity=ser.validated_data['quantity'],
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        row = CartItem.objects.select_related('product', 'variant').get(pk=row.pk)
        return Response(CartItemSerializer(row).data, status=status.HTTP_201_CREATED)


class CartItemMutateView(APIView):
    permission_classes = (IsAuthenticated,)

    def _owned_line(self, pk: int) -> CartItem:
        cart = active_cart_for_user(self.request.user, create=False)
        if cart is None:
            raise Http404

        row = get_object_or_404(CartItem.objects.select_related('cart'), pk=pk)

        if row.cart_id != cart.pk:
            raise Http404

        return row

    def patch(self, request, pk: int, *args, **kwargs):
        ser = CartItemQuantitySerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        row = self._owned_line(pk)

        try:
            updated = set_line_quantity(item=row, quantity=ser.validated_data['quantity'])
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        updated = CartItem.objects.select_related('product', 'variant').get(pk=updated.pk)
        return Response(CartItemSerializer(updated).data)

    def delete(self, request, pk: int, *args, **kwargs):
        row = self._owned_line(pk)
        remove_line(item=row)
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrderCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        ser = OrderCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        payload = ser.validated_data

        try:
            order = checkout_from_cart(
                user=request.user,
                shipping_address_id=payload['shipping_address_id'],
                billing_address_id=payload.get('billing_address_id'),
                payment_method=payload['payment_method'],
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        order = (
            Order.objects.select_related('user')
            .prefetch_related('items__product', 'items__variant')
            .get(pk=order.pk)
        )

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderListView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = OrderSerializer

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user)
            .select_related('user')
            .prefetch_related('items__product', 'items__variant')
            .order_by('-created_at')
        )


class OrderDetailView(generics.RetrieveAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = OrderSerializer
    lookup_field = 'uuid'
    lookup_url_kwarg = 'order_uuid'

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user)
            .select_related('user')
            .prefetch_related('items__product', 'items__variant')
        )


class OrderPayView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, uuid, *args, **kwargs):
        order = get_object_or_404(Order.objects.filter(user=request.user), uuid=uuid)

        if order.payment_status != PaymentStatus.UNPAID:
            return Response(
                {'detail': 'Order is not awaiting payment.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if order.payment_method != PaymentMethod.STRIPE:
            return Response(
                {'detail': 'Stripe payment is not enabled for this order.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payload = create_payment_intent_for_order(order)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'client_secret': payload['client_secret']})


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    authentication_classes = ()
    permission_classes = ()

    def post(self, request, *args, **kwargs):
        webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '').strip()
        if not webhook_secret:
            return Response(
                {'detail': 'Stripe webhooks are not configured.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

        try:
            event = stripe.Webhook.construct_event(
                payload,
                sig_header,
                webhook_secret,
            )
        except ValueError:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        except SignatureVerificationError:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        dispatch_stripe_webhook_event(event)

        return Response(status=status.HTTP_200_OK)
