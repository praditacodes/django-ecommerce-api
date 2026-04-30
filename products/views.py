from rest_framework.decorators import api_view
from django.shortcuts import get_object_or_404

from rest_framework.response import Response
from rest_framework import status

from .models import Product

from .serializers import (
    ProductSerializer,
    ProductCreateSerializer
)


@api_view(['GET'])
def product_list(request):

    products = Product.objects.filter(
        is_available=True
    )

    serializer = ProductSerializer(
        products,
        many=True
    )

    return Response(serializer.data)

@api_view(['GET'])
def product_detail(request, slug):

    product = get_object_or_404(
        Product,
        slug=slug,
        is_available=True
    )

    serializer = ProductSerializer(product)

    return Response(serializer.data)


@api_view(['POST'])
def create_product(request):

    serializer = ProductCreateSerializer(
        data=request.data
    )

    if serializer.is_valid():

        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )

    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST
    )

@api_view(['PUT'])
def update_product(request, slug):

    product = get_object_or_404(
        Product,
        slug=slug
    )

    serializer = ProductCreateSerializer(
        product,
        data=request.data
    )

    if serializer.is_valid():

        serializer.save()

        return Response(serializer.data)

    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST
    )

@api_view(['DELETE'])
def delete_product(request, slug):

    product = get_object_or_404(
        Product,
        slug=slug
    )

    product.delete()

    return Response(
        {
            'message': 'Product deleted successfully'
        },
        status=status.HTTP_204_NO_CONTENT
    )