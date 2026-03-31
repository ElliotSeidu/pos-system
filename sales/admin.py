from django.contrib import admin
from .models import Sale, SaleItem

# Register your models here.
admin.site.register(Sale)
admin.site.register(SaleItem)