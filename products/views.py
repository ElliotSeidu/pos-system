from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Product
from .forms import ProductForm
from django.shortcuts import get_object_or_404
from accounts.decorators import role_required

# Create your views here.
@login_required
def product_list(request):
    products = Product.objects.all().order_by("product_name")
    return render(request, "products/product_list.html", {"products": products})

@login_required
@role_required(['admin', 'manager'])
def add_product(request):
    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("product_list")
    else:
        form = ProductForm()
    return render(request, "products/add_product.html", {"form": form})

@login_required
@role_required(['admin', 'manager'])
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            return redirect("product_list")
    else:
        form = ProductForm(instance=product)

    return render(request, "products/edit_product.html", {"form": form})

@login_required
@role_required(['admin'])
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.delete()
    return redirect("product_list")