"""Cart + checkout integration tests."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from rest_framework.test import APITestCase

from orders.models import Cart, CartItem, Order, PaymentMethod, PaymentStatus
from orders.services.cart_service import active_cart_for_user
from orders.services.payment_service import (
    create_payment_intent_for_order,
    dispatch_stripe_webhook_event,
)
from products.models import Availability, Category, Product

User = get_user_model()


class CartServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='buyer',
            email='buyer@example.test',
            password='buyerpass',
        )
        self.cat = Category.objects.create(name='Gear', slug='gear')
        self.product = Product.objects.create(
            category=self.cat,
            name='Simple Mug',
            slug='simple-mug',
            short_description='Ceramic',
            description='Holds liquid.',
            sku='SKU-MUG',
            brand='MugCo',
            price=Decimal('12.00'),
            stock_quantity=10,
            availability=Availability.AVAILABLE,
        )

    def test_active_cart_get_or_create(self):
        cart1 = active_cart_for_user(self.user)
        cart2 = active_cart_for_user(self.user)
        self.assertEqual(cart1.pk, cart2.pk)


class CartAPITests(APITestCase):
    databases = '__all__'

    def setUp(self):
        self.user = User.objects.create_user(
            username='api_buyer',
            email='api_buyer@example.test',
            password='pass12345',
        )
        self.cat = Category.objects.create(name='Tools', slug='tools')
        self.product = Product.objects.create(
            category=self.cat,
            name='Hammer',
            slug='steel-hammer',
            short_description='Heavy',
            description='Strikes nails.',
            sku='SKU-HAM',
            brand='ToolCo',
            price=Decimal('25.00'),
            stock_quantity=4,
            availability=Availability.AVAILABLE,
        )
        self.cart_url = reverse('orders-cart')
        self.cart_items_url = reverse('orders-cart-items')

    def _auth(self):
        self.client.force_authenticate(user=self.user)

    def test_cart_requires_login(self):
        response = self.client.get(self.cart_url)
        self.assertEqual(response.status_code, 401)

    def test_add_and_list_cart(self):
        self._auth()

        create = self.client.post(
            self.cart_items_url,
            {'product_slug': self.product.slug, 'quantity': 2},
            format='json',
        )
        self.assertEqual(create.status_code, 201)

        detail = self.client.get(self.cart_url)
        self.assertEqual(detail.status_code, 200)
        payload = detail.json()
        self.assertEqual(len(payload['items']), 1)
        self.assertEqual(Decimal(payload['merchandise_total']), Decimal('50.00'))

    def test_patch_quantity_and_delete(self):
        self._auth()
        self.client.post(
            self.cart_items_url,
            {'product_slug': self.product.slug, 'quantity': 1},
            format='json',
        )

        row = CartItem.objects.get(cart__user=self.user)
        url = reverse('orders-cart-item', kwargs={'pk': row.pk})

        patch = self.client.patch(url, {'quantity': 3}, format='json')
        self.assertEqual(patch.status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.quantity, 3)

        delete = self.client.delete(url)
        self.assertEqual(delete.status_code, 204)
        self.assertEqual(CartItem.objects.filter(cart__user=self.user).count(), 0)


class CheckoutAPITests(APITestCase):
    databases = '__all__'

    def setUp(self):
        self.user = User.objects.create_user(
            username='checkout_user',
            email='checkout_user@example.test',
            password='pass12345',
        )
        self.address = self.user.addresses.create(
            recipient_name='Checkout User',
            phone='+100000000',
            address_line_1='1 Test Lane',
            city='Testville',
            postal_code='00000',
            country='US',
        )
        self.cat = Category.objects.create(name='Stock', slug='stock')
        self.product = Product.objects.create(
            category=self.cat,
            name='Widget',
            slug='stock-widget',
            short_description='Consumable',
            description='Used in checkout tests.',
            sku='SKU-WID',
            brand='Co',
            price=Decimal('10.00'),
            stock_quantity=5,
            availability=Availability.AVAILABLE,
        )
        self.cart_items_url = reverse('orders-cart-items')
        self.checkout_url = reverse('orders-create')

    def test_checkout_creates_order_and_reduces_stock(self):
        self.client.force_authenticate(user=self.user)

        self.client.post(
            self.cart_items_url,
            {'product_slug': self.product.slug, 'quantity': 2},
            format='json',
        )

        response = self.client.post(
            self.checkout_url,
            {
                'shipping_address_id': self.address.pk,
                'payment_method': 'cod',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertIn('uuid', body)
        self.assertEqual(Decimal(body['total']), Decimal('20.00'))

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 3)

        cart = Cart.objects.filter(user=self.user).first()
        self.assertIsNotNone(cart)
        self.assertEqual(cart.items.count(), 0)

        self.assertEqual(Order.objects.filter(user=self.user).count(), 1)


class StripePaymentIntentTests(TestCase):
    databases = '__all__'

    def setUp(self):
        self.user = User.objects.create_user(
            username='stripe_buyer',
            email='stripe_buyer@example.test',
            password='pass12345',
        )

    @override_settings(STRIPE_SECRET_KEY='sk_test_placeholder', STRIPE_CURRENCY='usd')
    def test_create_payment_intent_stores_intent_id_and_returns_secret(self):
        order = Order.objects.create(
            user=self.user,
            subtotal=Decimal('15.00'),
            tax=Decimal('0.00'),
            shipping_cost=Decimal('0.00'),
            total=Decimal('15.00'),
            payment_method=PaymentMethod.STRIPE,
            payment_status=PaymentStatus.UNPAID,
        )

        fake_intent = MagicMock()
        fake_intent.id = 'pi_unit_test_123'
        fake_intent.client_secret = 'cs_unit_test_secret'

        with patch(
            'orders.services.payment_service.stripe.PaymentIntent.create',
            return_value=fake_intent,
        ) as mocked_create:
            payload = create_payment_intent_for_order(order)

        mocked_create.assert_called_once()
        call_kw = mocked_create.call_args.kwargs
        self.assertEqual(call_kw['amount'], 1500)
        self.assertEqual(call_kw['currency'], 'usd')
        self.assertEqual(call_kw['metadata']['order_id'], str(order.pk))

        order.refresh_from_db()
        self.assertEqual(order.stripe_payment_intent_id, 'pi_unit_test_123')
        self.assertEqual(payload['client_secret'], 'cs_unit_test_secret')


class StripeWebhookTests(TestCase):
    databases = '__all__'

    def setUp(self):
        self.user = User.objects.create_user(
            username='wh_buyer',
            email='wh_buyer@example.test',
            password='pass12345',
        )

    def _stripe_order(self):
        return Order.objects.create(
            user=self.user,
            subtotal=Decimal('9.99'),
            tax=Decimal('0.00'),
            shipping_cost=Decimal('0.00'),
            total=Decimal('9.99'),
            payment_method=PaymentMethod.STRIPE,
            payment_status=PaymentStatus.UNPAID,
            stripe_payment_intent_id='pi_wh_example',
        )

    def test_payment_intent_succeeded_sets_paid(self):
        order = self._stripe_order()

        event = MagicMock()
        event.type = 'payment_intent.succeeded'
        event.data.object.id = 'pi_wh_example'

        dispatch_stripe_webhook_event(event)

        order.refresh_from_db()
        self.assertEqual(order.payment_status, PaymentStatus.PAID)

    def test_payment_intent_succeeded_is_idempotent(self):
        order = self._stripe_order()
        order.payment_status = PaymentStatus.PAID
        order.save(update_fields=('payment_status',))

        event = MagicMock()
        event.type = 'payment_intent.succeeded'
        event.data.object.id = 'pi_wh_example'

        dispatch_stripe_webhook_event(event)

        order.refresh_from_db()
        self.assertEqual(order.payment_status, PaymentStatus.PAID)

    def test_payment_intent_failed_sets_failed_and_never_overwrites_paid(self):
        order = self._stripe_order()

        failed_event = MagicMock()
        failed_event.type = 'payment_intent.payment_failed'
        failed_event.data.object.id = 'pi_wh_example'
        dispatch_stripe_webhook_event(failed_event)

        order.refresh_from_db()
        self.assertEqual(order.payment_status, PaymentStatus.FAILED)

        order.payment_status = PaymentStatus.PAID
        order.save(update_fields=('payment_status',))

        dispatch_stripe_webhook_event(failed_event)

        order.refresh_from_db()
        self.assertEqual(order.payment_status, PaymentStatus.PAID)


@override_settings(
    STRIPE_SECRET_KEY='sk_test_placeholder',
    STRIPE_WEBHOOK_SECRET='whsec_test',
    STRIPE_CURRENCY='usd',
)
class StripePaymentAPITests(APITestCase):
    databases = '__all__'

    def setUp(self):
        self.user = User.objects.create_user(
            username='pay_api',
            email='pay_api@example.test',
            password='pass12345',
        )
        self.order = Order.objects.create(
            user=self.user,
            subtotal=Decimal('5.00'),
            tax=Decimal('0.00'),
            shipping_cost=Decimal('0.00'),
            total=Decimal('5.00'),
            payment_method=PaymentMethod.STRIPE,
            payment_status=PaymentStatus.UNPAID,
        )

    def test_pay_endpoint_returns_client_secret(self):
        fake_intent = MagicMock()
        fake_intent.id = 'pi_api_test'
        fake_intent.client_secret = 'cs_api_secret'

        self.client.force_authenticate(user=self.user)

        with patch(
            'orders.services.payment_service.stripe.PaymentIntent.create',
            return_value=fake_intent,
        ):
            url = reverse('orders-pay', kwargs={'uuid': self.order.uuid})
            response = self.client.post(url, {}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['client_secret'], 'cs_api_secret')

        self.order.refresh_from_db()
        self.assertEqual(self.order.stripe_payment_intent_id, 'pi_api_test')

    def test_webhook_view_updates_order_via_construct_event(self):
        self.order.stripe_payment_intent_id = 'pi_hook_flow'
        self.order.save(update_fields=('stripe_payment_intent_id',))

        fake_event = MagicMock()
        fake_event.type = 'payment_intent.succeeded'
        fake_event.data.object.id = 'pi_hook_flow'

        with patch('orders.views.stripe.Webhook.construct_event', return_value=fake_event):
            response = self.client.post(
                reverse('stripe-webhook'),
                data=b'{}',
                content_type='application/json',
                HTTP_STRIPE_SIGNATURE='test_sig',
            )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, PaymentStatus.PAID)
