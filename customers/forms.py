from django import forms
from .models import Customer

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['first_name', 'last_name', 'phone', 'email', 'address']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
        }