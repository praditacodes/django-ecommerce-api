"""DRF serializers for catalog, storefront templates, and moderated reviews."""

from rest_framework import serializers

from .models import (
    Availability,
    Category,
    Product,
    ProductImage,
    ProductReview,
    ProductVariant,
    ReviewModeration,
)


class CategoryChildSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'meta_title', 'meta_description', 'sort_order')


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField(read_only=True)
    parent_id = serializers.IntegerField(source='parent_id', allow_null=True, read_only=True)

    class Meta:
        model = Category
        fields = (
            'id',
            'parent_id',
            'name',
            'slug',
            'meta_title',
            'meta_description',
            'sort_order',
            'children',
        )

    def get_children(self, obj):
        child_qs = getattr(obj, '_prefetched_objects_cache', {}).get(
            'children',
            obj.children.order_by('sort_order', 'name'),
        )
        serializer = CategoryChildSerializer(child_qs[:50], many=True)
        return serializer.data


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = (
            'id',
            'size',
            'color',
            'sku_suffix',
            'stock_quantity',
        )


class ProductImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = (
            'id',
            'url',
            'alt_text',
            'is_primary',
            'sort_order',
        )

    def get_url(self, obj):
        request = self.context.get('request')
        if obj.image:
            img_url = obj.image.url
            if request:
                return request.build_absolute_uri(img_url)
            return img_url
        return None


class ProductReviewReadSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = ProductReview
        fields = (
            'id',
            'rating',
            'comment',
            'verified_purchase',
            'username',
            'created_at',
        )


class ProductReviewWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductReview
        fields = ('rating', 'comment')

    def validate_rating(self, value):
        if value not in range(1, 6):
            raise serializers.ValidationError('Ratings must be between 1 and 5 inclusive.')
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        product = self.context.get('catalog_product')

        if request is None or product is None:
            raise serializers.ValidationError('Review context incomplete.')

        if not request.user or not request.user.is_authenticated:
            raise serializers.ValidationError('Authenticated shoppers only.')

        if ProductReview.objects.filter(product_id=product.pk, user_id=request.user.id).exists():
            raise serializers.ValidationError('You already shared feedback for this item.')

        return attrs


class ProductListSerializer(serializers.ModelSerializer):
    category = CategoryChildSerializer(read_only=True)

    display_price = serializers.SerializerMethodField()
    current_price = serializers.SerializerMethodField()

    primary_image_url = serializers.SerializerMethodField()
    review_average = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    effective_inventory = serializers.SerializerMethodField()
    is_low_stock = serializers.SerializerMethodField()
    is_out_of_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'id',
            'category',
            'name',
            'slug',
            'short_description',
            'sku',
            'brand',
            'price',
            'discount_price',
            'display_price',
            'current_price',
            'featured',
            'availability',
            'effective_inventory',
            'is_low_stock',
            'is_out_of_stock',
            'review_average',
            'review_count',
            'primary_image_url',
            'created_at',
        )

    def _pick_primary_image(self, obj):
        images_rel = getattr(obj, 'images', None)
        if not images_rel or not hasattr(images_rel, 'all'):
            return None
        ordered = sorted(images_rel.all(), key=lambda im: (-im.is_primary, im.sort_order, im.pk))
        return ordered[0] if ordered else None

    def get_primary_image_url(self, obj):
        image = self._pick_primary_image(obj)
        if not image:
            return None
        serializer = ProductImageSerializer(image, context=self.context)
        return serializer.data['url']

    def get_display_price(self, obj):
        annotated = getattr(obj, 'display_price', None)
        if annotated is None:
            return obj.current_price()
        return annotated

    def get_current_price(self, obj):
        return obj.current_price()

    def get_effective_inventory(self, obj):
        annotated = getattr(obj, 'effective_inventory', None)
        if annotated is None:
            return obj.get_effective_stock()
        return annotated

    def get_is_low_stock(self, obj):
        if getattr(obj, 'availability') != Availability.AVAILABLE:
            return False

        qty = self.get_effective_inventory(obj)
        threshold = getattr(obj, 'low_stock_threshold', Product.LOW_STOCK_DEFAULT)
        return 0 < qty <= threshold

    def get_is_out_of_stock(self, obj):
        qty = self.get_effective_inventory(obj)
        avail = getattr(obj, 'availability', Availability.AVAILABLE)

        if avail == Availability.OUT_OF_STOCK:
            return True

        if avail == Availability.PREORDER:
            return qty <= 0

        return qty <= 0

    def get_review_average(self, obj):
        avg = getattr(obj, 'review_average', None)
        return float(avg) if avg is not None else None

    def get_review_count(self, obj):
        return getattr(obj, 'review_count', 0)


class ProductDetailSerializer(ProductListSerializer):
    variants = ProductVariantSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)

    low_stock_threshold = serializers.IntegerField(read_only=True)

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + (
            'description',
            'low_stock_threshold',
            'variants',
            'images',
            'updated_at',
        )
