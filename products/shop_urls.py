"""HTML catalogue routes (/shop/)."""

from django.urls import path

from .web_views import CatalogRootListView, CategoryProductListView, ProductShopDetailView

urlpatterns = [
    path('', CatalogRootListView.as_view(), name='shop-catalog-root'),
    path(
        'categories/<slug:category_slug>/',
        CategoryProductListView.as_view(),
        name='shop-category',
    ),
    path(
        'products/<slug:slug>/',
        ProductShopDetailView.as_view(),
        name='shop-product-detail',
    ),
]
