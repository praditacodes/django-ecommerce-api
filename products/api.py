"""REST interface for catalogue discovery (JWT optional for authenticated reviews)."""

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404

from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import filters as drf_filters
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ReadOnlyModelViewSet

from .filters import ProductCatalogFilter
from .models import Category, ProductReview, ReviewModeration
from .permissions import CatalogReadOnlyStaffWrite, ProductReviewPermissions
from .querysets import refined_catalog
from .serializers import (
    CategorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    ProductReviewReadSerializer,
    ProductReviewWriteSerializer,
)


class CategoryViewSet(ReadOnlyModelViewSet):
    queryset = (
        Category.objects.all()
        .select_related('parent')
        .prefetch_related(
            Prefetch(
                'children',
                queryset=Category.objects.order_by('sort_order', 'name'),
            ),
        )
        .order_by('sort_order', 'name')
    )
    serializer_class = CategorySerializer
    permission_classes = [CatalogReadOnlyStaffWrite]
    lookup_field = 'slug'


class ProductViewSet(ReadOnlyModelViewSet):
    queryset = refined_catalog(include_images=True, include_variants=True)
    lookup_field = 'slug'
    permission_classes = [CatalogReadOnlyStaffWrite]
    filter_backends = [
        DjangoFilterBackend,
        drf_filters.SearchFilter,
        drf_filters.OrderingFilter,
    ]
    filterset_class = ProductCatalogFilter
    search_fields = ('name', 'brand', 'sku', 'short_description', 'description')
    ordering_fields = (
        'name',
        'featured',
        'created_at',
        'display_price',
        'effective_inventory',
        'review_average',
    )
    ordering = ('-featured', '-created_at')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProductDetailSerializer
        return ProductListSerializer


class ProductReviewListCreateView(ListCreateAPIView):
    """
    Approved reviews surface publicly on GET while authors (and staff) can see drafts.
    POST requires authenticated shoppers.
    """

    def get_permissions(self):  # type: ignore[override]
        if self.request.method == 'GET':
            return [AllowAny()]
        return [ProductReviewPermissions()]

    def get_product_queryset(self):
        return refined_catalog(include_images=False, include_variants=False)

    def _product(self):
        return get_object_or_404(self.get_product_queryset(), slug=self.kwargs['product_slug'])

    def get_serializer_context(self):  # type: ignore[override]
        ctx = super().get_serializer_context()
        # Skip the extra catalogue hit for anonymous read traffic.
        if self.request.method == 'POST':
            ctx['catalog_product'] = self._product()
        return ctx

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return ProductReviewReadSerializer
        return ProductReviewWriteSerializer

    def get_queryset(self):  # type: ignore[override]
        product = self._product()
        reviewer = getattr(self.request, 'user', None)

        base = ProductReview.objects.filter(product=product).select_related('user')

        if self.request.method != 'GET':
            return base.order_by('-created_at')

        approved = base.filter(moderation_status=ReviewModeration.APPROVED)

        if reviewer and reviewer.is_staff:
            return base.order_by('-created_at')

        if reviewer and reviewer.is_authenticated:
            mine = base.filter(user=reviewer)
            return (approved | mine).distinct().order_by('-created_at')

        return approved.order_by('-created_at')

    def perform_create(self, serializer):
        product = self._product()
        reviewer = getattr(self.request, 'user', None)

        if not reviewer or not reviewer.is_authenticated:
            raise ValidationError({'detail': 'Authentication required to submit a review.'})

        serializer.save(
            product=product,
            user=reviewer,
            moderation_status=ReviewModeration.PENDING,
        )
