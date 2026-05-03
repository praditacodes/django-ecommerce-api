from decimal import Decimal, InvalidOperation

import django_filters
from django.db.models import F, Q

from .models import Availability, Product


def _truthy(raw) -> bool:
    if raw is None:
        return False
    return str(raw).strip().lower() in {'1', 'true', 'yes', 'on'}


class ProductCatalogFilter(django_filters.FilterSet):
    """Composable filterset reused by Django templates (`request.GET`) and DRF backends."""

    search = django_filters.CharFilter(method='filter_search')
    category_slug = django_filters.CharFilter(field_name='category__slug')
    brand = django_filters.CharFilter(field_name='brand', lookup_expr='icontains')
    availability = django_filters.MultipleChoiceFilter(
        choices=Availability.choices,
        field_name='availability',
    )
    featured = django_filters.BooleanFilter(method='filter_featured')

    price_min = django_filters.NumberFilter(method='filter_price_min')
    price_max = django_filters.NumberFilter(method='filter_price_max')

    low_stock_only = django_filters.BooleanFilter(method='filter_low_stock')
    in_stock = django_filters.BooleanFilter(method='filter_in_stock')

    class Meta:
        model = Product
        fields = []

    # --- helpers ---------------------------------------------------------
    def filter_search(self, queryset, name, value):
        term = value.strip()
        if not term:
            return queryset
        return queryset.filter(
            Q(name__icontains=term)
            | Q(brand__icontains=term)
            | Q(sku__icontains=term)
            | Q(short_description__icontains=term)
            | Q(description__icontains=term)
        ).distinct()

    def filter_price_min(self, queryset, name, value):
        if value is None:
            return queryset
        try:
            cents = Decimal(value)
        except (InvalidOperation, TypeError):
            return queryset
        return queryset.filter(display_price__gte=cents)

    def filter_price_max(self, queryset, name, value):
        if value is None:
            return queryset
        try:
            cents = Decimal(value)
        except (InvalidOperation, TypeError):
            return queryset
        return queryset.filter(display_price__lte=cents)

    def filter_low_stock(self, queryset, name, value):
        if not _truthy(value):
            return queryset
        return queryset.filter(
            availability=Availability.AVAILABLE,
            effective_inventory__lte=F('low_stock_threshold'),
            effective_inventory__gt=0,
        )

    def filter_in_stock(self, queryset, name, value):
        """True ⇒ purchasable units exist; False ⇒ depleted / marked unavailable."""

        val = ''
        if isinstance(value, str):
            val = value
        elif value is not None:
            val = str(value)
        if val == '':
            return queryset
        desired = _truthy(value)
        if desired:
            return queryset.filter(
                availability__in=[Availability.AVAILABLE, Availability.PREORDER],
                effective_inventory__gt=0,
            )
        return queryset.filter(Q(effective_inventory__lte=0) | ~Q(availability=Availability.AVAILABLE))

    def filter_featured(self, queryset, name, value):
        if value is None:
            return queryset
        if bool(value):
            return queryset.filter(featured=True)
        return queryset.filter(featured=False)
