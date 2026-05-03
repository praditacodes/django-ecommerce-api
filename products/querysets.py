"""Compose querysets reused by REST + HTML catalog views (no cart side-effects here)."""

from django.db.models import (
    Avg,
    Case,
    Count,
    DecimalField,
    F,
    IntegerField,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce

from .models import Availability, Product, ProductImage, ProductReview, ProductVariant, ReviewModeration


def annotate_review_stats(product_qs):
    """Approved-only aggregates via subqueries to avoid join amplification."""
    approved = ReviewModeration.APPROVED
    scoped = ProductReview.objects.filter(
        product_id=OuterRef('pk'),
        moderation_status=approved,
    ).values('product')

    avg_sq = scoped.annotate(metric=Avg('rating')).values('metric')[:1]
    count_sq = scoped.annotate(metric=Count('id')).values('metric')[:1]

    return product_qs.annotate(
        review_average=Subquery(
            avg_sq,
            output_field=DecimalField(max_digits=6, decimal_places=4, null=True),
        ),
        review_count=Coalesce(
            Subquery(count_sq, output_field=IntegerField()),
            Value(0),
        ),
    )


def annotate_display_price(product_qs):
    return product_qs.annotate(
        display_price=Case(
            When(
                Q(discount_price__isnull=False) & Q(discount_price__lt=F('price')),
                then=F('discount_price'),
            ),
            default=F('price'),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
    )


def annotate_effective_inventory(product_qs):
    variant_agg = ProductVariant.objects.filter(product_id=OuterRef('pk')).values('product').annotate(
        total=Sum('stock_quantity'), kinds=Count('id')
    )

    totals = variant_agg.values('total')[:1]
    kinds = variant_agg.values('kinds')[:1]

    return product_qs.annotate(
        variant_inventory=Coalesce(
            Subquery(totals, output_field=IntegerField()),
            Value(0),
        ),
        variant_kind_count=Coalesce(
            Subquery(kinds, output_field=IntegerField()),
            Value(0),
        ),
        effective_inventory=Case(
            When(variant_kind_count__gt=0, then=F('variant_inventory')),
            default=F('stock_quantity'),
            output_field=IntegerField(),
        ),
    )


def catalog_products_public():
    return Product.objects.filter(availability__in=[Availability.AVAILABLE, Availability.PREORDER])


def refined_catalog(include_images=True, include_variants=True):
    qs = catalog_products_public().select_related('category')
    qs = annotate_effective_inventory(qs)
    qs = annotate_display_price(qs)
    qs = annotate_review_stats(qs)

    prefetch = []
    if include_images:
        imgs = ProductImage.objects.order_by('-is_primary', 'sort_order', 'id')
        prefetch.append(Prefetch('images', queryset=imgs))
    if include_variants:
        prefetch.append('variants')

    if prefetch:
        qs = qs.prefetch_related(*prefetch)
    return qs


def reviews_for_product_public(product_slug: str):
    return ProductReview.objects.filter(
        product__slug=product_slug,
        moderation_status=ReviewModeration.APPROVED,
    ).select_related('user')

