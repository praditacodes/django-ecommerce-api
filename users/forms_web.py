from django import forms
from django.contrib.auth.password_validation import validate_password


class PasswordSetFromEmailLinkForm(forms.Form):
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )

    def clean(self):
        data = super().clean()
        p1 = data.get('new_password')
        p2 = data.get('confirm_password')

        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Passwords do not match.')

        if p1:
            validate_password(p1)

        return data
