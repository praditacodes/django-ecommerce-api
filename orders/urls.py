"""Routes mounted at ``/api/`` — cart basket + order lifecycle."""

from django.urls import path

from orders import views

urlpatterns = [
    path('cart/', views.CartDetailView.as_view(), name='orders-cart'),
    path('cart/items/', views.CartItemCreateView.as_view(), name='orders-cart-items'),
    path(
        'cart/items/<int:pk>/',
        views.CartItemMutateView.as_view(),
        name='orders-cart-item',
    ),
    path('orders/create/', views.OrderCreateView.as_view(), name='orders-create'),
    path(
        'orders/<uuid:uuid>/pay/',
        views.OrderPayView.as_view(),
        name='orders-pay',
    ),
    path('orders/', views.OrderListView.as_view(), name='orders-list'),
    path(
        'orders/<uuid:order_uuid>/',
        views.OrderDetailView.as_view(),
        name='orders-detail',
    ),
    path(
        'stripe/webhook/',
        views.StripeWebhookView.as_view(),
        name='stripe-webhook',
    ),
]
