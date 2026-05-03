from rest_framework.permissions import SAFE_METHODS, BasePermission


class CatalogReadOnlyStaffWrite(BasePermission):
    """Expose catalog reads to anyone; mutate catalog records only via staff JWT."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


class ProductReviewPermissions(BasePermission):
    """Reads are open (approved subset enforced in queryset). Creation requires authentication."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated


class OwnerOrStaffReviewEdit(BasePermission):
    """Allows authors to PATCH their review when exposed (optional future routes)."""

    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_staff:
            return True
        if request.method not in SAFE_METHODS:
            return obj.user_id == getattr(request.user, 'id', None)
        return True

