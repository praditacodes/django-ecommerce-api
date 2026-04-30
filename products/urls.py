from django.urls import path

from .views import (
    product_list,
    product_detail,
    create_product,
    update_product,
    delete_product
)

urlpatterns = [

    path(
        '',
        product_list,
        name='product_list'
    ),

    path(
        'create/',
        create_product,
        name='create_product'
    ),

    path(
        '<slug:slug>/',
        product_detail,
        name='product_detail'
    ),

    path(
        '<slug:slug>/update/',
        update_product,
        name='update_product'
    ),

    path(
        '<slug:slug>/delete/',
        delete_product,
        name='delete_product'
    ),
]