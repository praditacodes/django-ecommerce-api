from rest_framework import serializers

from .models import Category,Product


class CategorySerializer(serializers.ModelSerializer):

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']

class ProductSerializer(serializers.ModelSerializer):

    category = CategorySerializer()

    class Meta:
        model = Product

        fields = [
            'id',
            'category',
            'name',
            'slug',
            'description',
            'price',
            'stock',
            'is_available',
            'created_at'
        ]
class ProductCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Product

        fields = [
            'category',
            'name',
            'slug',
            'description',
            'price',
            'stock',
            'is_available'
        ]