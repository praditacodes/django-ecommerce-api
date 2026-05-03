from django.apps import AppConfig


class ProductsConfig(AppConfig):
    name = 'products'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self) -> None:  # noqa: D401
        from . import signals  # noqa: F401  # signal registration side-effect only
