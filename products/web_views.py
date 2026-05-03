"""Bootstrap storefront pages aligned with catalogue API filters/search."""

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView

from .filters import ProductCatalogFilter
from .models import Category
from .querysets import refined_catalog, reviews_for_product_public


def shop_page_size() -> int:
    return int(getattr(settings, 'REST_FRAMEWORK', {}).get('PAGE_SIZE', 24))


def _ordering_map():
    """
    Mirrors DRF OrderingFilter choices for template-friendly URLs.

    Allowed query param values for ``ordering``::
        featured, newest, price, -price, name, -name, reviews
    """
    return {
        'featured': ['-featured', '-created_at'],
        'newest': ['-created_at'],
        'price': ['display_price'],
        '-price': ['-display_price'],
        'name': ['name'],
        '-name': ['-name'],
        'reviews': ['-review_average'],
    }


def _apply_shop_sort(queryset, request):
    mapping = _ordering_map()
    raw_ordering = request.GET.get('ordering', 'featured')
    return queryset.order_by(*mapping.get(raw_ordering, mapping['featured']))


class CatalogRootListView(ListView):
    """All purchasable products with shared filter form."""

    template_name = 'catalog/product_list.html'
    context_object_name = 'products'
    paginate_by = shop_page_size()

    def get_queryset(self):
        queryset = refined_catalog(include_images=True, include_variants=True)
        queryset = ProductCatalogFilter(self.request.GET, queryset=queryset).qs
        queryset = _apply_shop_sort(queryset, self.request)
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['current_filters'] = self.request.GET.copy()
        ctx['category'] = None
        ctx['category_breadcrumbs'] = []
        ctx['meta_title'] = 'Shop catalog'
        ctx['meta_description'] = ''
        return ctx


class CategoryProductListView(CatalogRootListView):
    """Category-scoped storefront listing (SEO breadcrumbs + tighter queryset)."""

    def get_queryset(self):
        slug = self.kwargs['category_slug']
        queryset = refined_catalog(include_images=True, include_variants=True).filter(
            category__slug=slug,
        )
        queryset = ProductCatalogFilter(self.request.GET, queryset=queryset).qs
        queryset = _apply_shop_sort(queryset, self.request)
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        category = get_object_or_404(Category, slug=self.kwargs['category_slug'])
        ctx['category'] = category
        ctx['category_breadcrumbs'] = category.breadcrumb_pairs()

        meta_title = category.meta_title.strip() if category.meta_title else category.name
        ctx['meta_title'] = meta_title
        ctx['meta_description'] = category.meta_description
        ctx['current_filters'] = self.request.GET.copy()
        return ctx


class ProductShopDetailView(DetailView):
    template_name = 'catalog/product_detail.html'
    context_object_name = 'product'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return refined_catalog(include_images=True, include_variants=True)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        product = self.object

        ctx['reviews'] = list(reviews_for_product_public(product.slug)[:10])
        qty = getattr(product, 'effective_inventory', product.get_effective_stock())
        threshold = getattr(product, 'low_stock_threshold', product.LOW_STOCK_DEFAULT)

        ctx['effective_quantity'] = qty
        ctx['low_stock_notice'] = 0 < qty <= threshold

        category_segments = []
        if product.category:
            category_segments = product.category.breadcrumb_pairs()

        ctx['category_breadcrumbs'] = category_segments

        ctx['meta_title'] = product.name[:60]
        desc = product.short_description or product.description or ''
        ctx['meta_description'] = desc.strip()[:158]
        return ctx
