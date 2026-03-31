from django.shortcuts import render, redirect, get_object_or_404
from .models import Customer
from .forms import CustomerForm
from sales.models import Sale
from django.contrib.auth.decorators import login_required

# Create your views here.
@login_required()
def customer_list(request):
    query = request.GET.get('q', '')
    if query:
        customers = Customer.objects.filter(first_name__icontains=query) | Customer.objects.filter(last_name__icontains=query)
    else:
        customers = Customer.objects.all()
    return render(request, 'customers/customer_list.html', {'customers': customers, 'query': query})

# Add new customer
@login_required()
def add_customer(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('customer_list')
    else:
        form = CustomerForm()
    return render(request, 'customers/customer_add.html', {'form': form})

# Edit customer
@login_required()
def edit_customer(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            return redirect('customer_list')
    else:
        form = CustomerForm(instance=customer)
    return render(request, 'customers/customer_edit.html', {'form': form, 'customer': customer})

# Delete customer
@login_required()
def delete_customer(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    customer.delete()
    return redirect('customer_list')

@login_required()
def customer_orders(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    orders = Sale.objects.filter(customer=customer).order_by('-created_at')
    return render(request, 'customers/customer_orders.html', {
        'customer': customer,
        'orders': orders,
    })