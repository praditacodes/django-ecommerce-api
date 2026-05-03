from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from users.views import CustomTokenObtainPairView, CustomTokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('users.web_urls')),
    path('shop/', include('products.shop_urls')),
    path(
        'api/products/',
        include('products.urls'),
    ),
    path(
        'api/users/',
        include('users.urls'),
    ),
    path(
        'api/',
        include('orders.urls'),
    ),
    path(
        'api/token/',
        CustomTokenObtainPairView.as_view(),
        name='token_obtain_pair',
    ),
    path(
        'api/token/refresh/',
        CustomTokenRefreshView.as_view(),
        name='token_refresh',
    ),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
