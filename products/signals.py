"""Product-level signal handlers (image primacy, eventual cache invalidation)."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ProductImage


@receiver(post_save, sender=ProductImage)
def ensure_single_primary_image(sender, instance, **kwargs):  # noqa: ARG001
    if instance.is_primary:
        ProductImage.objects.filter(product_id=instance.product_id).exclude(
            pk=instance.pk,
        ).update(is_primary=False)
