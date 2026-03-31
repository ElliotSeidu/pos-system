# forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User

ROLE_CHOICES = [
    ('admin', 'Admin'),
    ('manager', 'Manager'),
    ('cashier', 'Cashier'),
]

class CustomUserCreationForm(UserCreationForm):
    role = forms.ChoiceField(choices=ROLE_CHOICES, required=True)

    class Meta:
        model = User  # your custom User model
        fields = ("username", "email", "password1", "password2", "role")