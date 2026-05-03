"""Serialize linked rows into JSON snapshots attached to immutable orders."""

from users.models import Address


def snapshot_address(addr: Address | None) -> dict:
    if addr is None:
        return {}

    return {
        'id': addr.pk,
        'label': addr.label,
        'recipient_name': addr.recipient_name,
        'phone': addr.phone,
        'address_line_1': addr.address_line_1,
        'address_line_2': addr.address_line_2,
        'city': addr.city,
        'state_province': addr.state_province,
        'postal_code': addr.postal_code,
        'country': addr.country,
    }
