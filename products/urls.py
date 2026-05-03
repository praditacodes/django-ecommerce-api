"""Expose catalogue APIs under `/api/products/`."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from .api import CategoryViewSet, ProductReviewListCreateView, ProductViewSet

# Disable the bundled API-root view (`^$`), otherwise each DefaultRouter would occupy
# the empty slug and `/api/products/` would return the hyperlink map instead of data.
router = DefaultRouter(trailing_slash=True)
router.include_root_view = False
router.register(r'categories', CategoryViewSet, basename='catalog-category')

# Register products under the trailing prefix alongside `categories/` routes.
catalog_router = DefaultRouter(trailing_slash=True)
catalog_router.include_root_view = False
catalog_router.register(r'', ProductViewSet, basename='catalog-product')


urlpatterns = [
    path(
        '<slug:product_slug>/reviews/',
        ProductReviewListCreateView.as_view(),
        name='catalog-product-reviews',
    ),
]

urlpatterns += router.urls + catalog_router.urls
