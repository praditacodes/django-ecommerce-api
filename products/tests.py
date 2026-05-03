"""Regression coverage for catalogue querysets + public APIs."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APITestCase

from .models import (
    Availability,
    Category,
    Product,
    ProductReview,
    ProductVariant,
    ReviewModeration,
)
from .checkout_prep import allocate_variant_or_product_line
from .querysets import annotate_display_price, catalog_products_public


User = get_user_model()


class ProductModelTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name='Audio', slug='audio')
        self.prod = Product.objects.create(
            category=self.cat,
            name='Desk Mic',
            slug='desk-mic',
            short_description='Condenser capsule',
            description='Full description',
            sku='SKU-MIC',
            brand='SoundCo',
            price=Decimal('99.00'),
            discount_price=Decimal('79.00'),
            stock_quantity=5,
            availability=Availability.AVAILABLE,
        )

    def test_current_price_prioritises_discount(self):
        self.assertEqual(self.prod.current_price(), Decimal('79.00'))

    def test_variant_inventory_overrides_stock_bucket(self):
        ProductVariant.objects.create(
            product=self.prod,
            size='One-size',
            color='Matte-black',
            stock_quantity=3,
        )
        self.prod.stock_quantity = 50
        self.prod.save(update_fields=['stock_quantity'])
        self.assertEqual(self.prod.get_effective_stock(), 3)


class AnnotatedQueryTests(TestCase):
    def test_display_price_annotation_respects_sale_tag(self):
        cat = Category.objects.create(name='Peripherals', slug='peripherals')
        product = catalog_products_public().create(
            category=cat,
            name='USB Hub',
            slug='usb-hub',
            short_description='10 ports',
            description='Powered hub',
            sku='SKU-HUB',
            brand='PlugCo',
            price=Decimal('40.00'),
            discount_price=Decimal('34.99'),
            stock_quantity=40,
            availability=Availability.AVAILABLE,
        )

        labelled = annotate_display_price(catalog_products_public().filter(pk=product.pk)).first()
        self.assertEqual(labelled.display_price, Decimal('34.99'))


class CatalogueAPITests(APITestCase):
    databases = '__all__'

    def setUp(self):
        self.cat = Category.objects.create(name='Desks', slug='desks')

        self.product = Product.objects.create(
            category=self.cat,
            name='Standing Desk',
            slug='standing-desk',
            short_description='Height adjustable steel frame.',
            description='Great for ergonomics labs.',
            sku='SKU-DESK',
            brand='FrameCo',
            price=Decimal('450.00'),
            stock_quantity=6,
            availability=Availability.AVAILABLE,
            featured=True,
        )

        self.list_url = reverse('catalog-product-list')
        self.detail_url = reverse('catalog-product-detail', kwargs={'slug': self.product.slug})

    def test_product_detail_returns_nested_payload(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['sku'], self.product.sku)

    def test_category_filter_via_querystring(self):
        response = self.client.get(self.list_url, {'category_slug': 'desks'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['results']), 1)

    def test_review_requires_authentication_and_enforces_duplicates(self):
        user = User.objects.create_user(username='alice', password='alicepass', email='alice@example.test')
        user.email_verified = True
        user.save(update_fields=['email_verified'])

        url = reverse('catalog-product-reviews', kwargs={'product_slug': self.product.slug})

        response = self.client.post(url, data={'rating': 5, 'comment': 'Fantastic finish.'}, format='json')
        self.assertEqual(response.status_code, 401)

        self.client.force_authenticate(user)
        resp_ok = self.client.post(url, data={'rating': 5, 'comment': 'Fantastic finish.'}, format='json')

        self.assertEqual(resp_ok.status_code, 201)

        dup = self.client.post(url, data={'rating': 5, 'comment': 'Trying again'}, format='json')
        self.assertEqual(dup.status_code, 400)
        payload_repr = repr(getattr(dup, 'data', dup.json())).lower()
        self.assertTrue(('feedback' in payload_repr) or ('already' in payload_repr))

        self.assertEqual(ProductReview.objects.filter(product=self.product).count(), 1)


class AllocationHelperTests(TestCase):
    databases = '__all__'

    def test_variant_allocation_validates_inventory(self):
        cat = Category.objects.create(name='Chairs', slug='chairs')

        prod = Product.objects.create(
            category=cat,
            name='Conference Chair',
            slug='conf-chair',
            short_description='',
            description='Padded roller chair.',
            sku='SKU-CHAIR',
            brand='SeatCo',
            price=Decimal('120.00'),
            stock_quantity=0,
            availability=Availability.AVAILABLE,
        )

        variant = ProductVariant.objects.create(
            product=prod,
            size='M',
            color='Graphite',
            stock_quantity=5,
        )

        found, fetched_variant, _ = allocate_variant_or_product_line(
            product_slug='conf-chair',
            variant_id=variant.pk,
            qty=2,
        )

        self.assertEqual(found.slug, prod.slug)
        self.assertEqual(fetched_variant.pk, variant.pk)

        with self.assertRaises(ValueError):
            allocate_variant_or_product_line(
                product_slug='conf-chair',
                variant_id=variant.pk,
                qty=20,
            )
