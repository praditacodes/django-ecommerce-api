from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """
    Stateless token tying verification to inactive accounts.
    When is_active toggles True, Django's hashing still validates the prior token for a short TTL;
    we perform activation in one request only.
    """

    def _make_hash_value(self, user, timestamp):
        # Include password so password changes invalidate lingering mail links.
        return f'{user.pk}{user.password}{timestamp}{user.is_active}{user.email}'


account_activation_token = EmailVerificationTokenGenerator()
