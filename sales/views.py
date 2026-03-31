from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from decimal import Decimal
from products.models import Product
from sales.models import Sale, SaleItem
from customers.models import Customer
import random
import string
from django.db import transaction
import requests
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import json
import hmac
import hashlib
from django.http import JsonResponse


def generate_order_number():
    return "SALE-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

def _deduct_stock(sale):
    for item in sale.items.all():
        product = item.product
        product.quantity -= item.quantity
        product.save()

def initiate_momo_charge(email, amount_pesewas, phone, provider, reference):
    url = "https://api.paystack.co/charge"
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}", "Content-Type": "application/json"}
    payload = {
        "email": email,
        "amount": amount_pesewas,
        "currency": "GHS",
        "reference": reference,
        "mobile_money": {"phone": phone, "provider": provider}
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()

# ------------------ POS / Cart ------------------

@login_required
def pos(request):
    query = request.GET.get("q", "").strip()
    products = Product.objects.filter(
        Q(product_name__icontains=query) |
        Q(category__icontains=query) |
        Q(barcode__icontains=query)
    ) if query else Product.objects.all()

    cart = request.session.get("cart", {})
    cart_product_map = Product.objects.in_bulk([int(k) for k in cart.keys()])

    cart_items = []
    total = Decimal("0")
    for product_id, quantity in cart.items():
        product = cart_product_map.get(int(product_id))
        if not product:
            continue
        subtotal = product.price * quantity
        cart_items.append({"product": product, "quantity": quantity, "subtotal": subtotal})
        total += subtotal

    customers = Customer.objects.all()
    return render(request, "sales/pos.html", {
        "products": products,
        "cart_items": cart_items,
        "total": total,
        "customers": customers,
        "query": query,
    })

@login_required
def add_to_cart(request, product_id):
    cart = request.session.get("cart", {})
    key = str(product_id)
    product = get_object_or_404(Product, id=product_id)
    current_quantity = cart.get(key, 0)

    if current_quantity + 1 > product.quantity:
        messages.error(request, f"Only {product.quantity} units of {product.product_name} available.")
        return redirect("pos")

    cart[key] = current_quantity + 1
    request.session["cart"] = cart
    return redirect("pos")

@login_required
def remove_from_cart(request, product_id):
    cart = request.session.get("cart", {})
    key = str(product_id)
    if key in cart:
        if cart[key] > 1:
            cart[key] -= 1
        else:
            del cart[key]
        request.session["cart"] = cart
    return redirect("pos")

@login_required
def complete_sale(request):
    if request.method != "POST":
        return redirect("pos")
    cart = request.session.get("cart", {})
    if not cart:
        return redirect("pos")

    customer_id = request.POST.get("customer_id")
    customer = Customer.objects.filter(id=customer_id).first() if customer_id else None

    with transaction.atomic():
        order_number = generate_order_number()
        while Sale.objects.filter(order_number=order_number).exists():
            order_number = generate_order_number()

        sale = Sale.objects.create(
            cashier=request.user,
            customer=customer,
            total_amount=0,
            order_number=order_number,
        )

        total = Decimal("0")
        for product_id, quantity in cart.items():
            product = get_object_or_404(Product, id=product_id)
            if product.quantity < quantity:
                messages.error(request, f"Insufficient stock for {product.product_name}.")
                return redirect("pos")
            SaleItem.objects.create(
                sale=sale,
                product=product,
                quantity=quantity,
                price=product.price,
            )
            total += product.price * quantity

        sale.total_amount = total
        sale.save()

    request.session["cart"] = {}
    return redirect("payment", sale_id=sale.id)

# ------------------ Payment Views ------------------

@login_required
def payment_view(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    if sale.is_paid:
        return redirect("receipt", sale_id=sale.id)

    customer_email = sale.customer.email if sale.customer and sale.customer.email else request.user.email

    if request.method == "POST":
        payment_method = request.POST.get("payment_method")

        # ------------------ Cash ------------------
        if payment_method == "cash":
            amount_paid = Decimal(request.POST.get("amount_paid", "0"))
            if amount_paid < sale.total_amount:
                return render(request, "sales/payment.html", {
                    "sale": sale,
                    "error": "Amount paid is less than total.",
                    "paystack_public_key": settings.PAYSTACK_PUBLIC_KEY,
                    "customer_email": customer_email
                })
            sale.amount_paid = amount_paid
            sale.change = amount_paid - sale.total_amount
            sale.payment_method = "cash"
            sale.is_paid = True
            sale.save()
            _deduct_stock(sale)
            return redirect("receipt", sale_id=sale.id)

        # ------------------ Mobile Money ------------------
        elif payment_method == "mobile_money":
            phone = request.POST.get("momo_phone", "").strip()
            provider = request.POST.get("momo_provider", "mtn")
            reference = sale.order_number

            # Demo mode — mark paid immediately
            if getattr(settings, "PAYSTACK_TEST_MODE", False):
                sale.payment_method = "mobile_money"
                sale.payment_reference = reference
                sale.amount_paid = sale.total_amount
                sale.change = Decimal("0")
                sale.is_paid = True
                sale.save()
                _deduct_stock(sale)
                return redirect("receipt", sale_id=sale.id)

            # Real Paystack call
            result = initiate_momo_charge(customer_email, int(sale.total_amount * 100), phone, provider, reference)
            if result.get("status") and result["data"]["status"] in ("send_otp", "pay_offline", "pending"):
                sale.payment_method = "mobile_money"
                sale.payment_reference = reference
                sale.save()
                return render(request, "sales/payment_pending.html", {
                    "sale": sale,
                    "phone": phone,
                    "message": "Awaiting customer confirmation..."
                })
            else:
                error_msg = result.get("message", "Mobile money charge failed. Check the phone number and try again.")
                return render(request, "sales/payment.html", {
                    "sale": sale,
                    "error": error_msg,
                    "paystack_public_key": settings.PAYSTACK_PUBLIC_KEY,
                    "customer_email": customer_email
                })

        # ------------------ Card ------------------
        elif payment_method == "card":
            reference = request.POST.get("reference", "").strip()

            # Demo mode — mark paid immediately
            sale.payment_method = "card"
            sale.payment_reference = reference or "TESTCARD-" + generate_order_number()
            sale.amount_paid = sale.total_amount
            sale.change = Decimal("0")
            sale.is_paid = True
            sale.save()
            _deduct_stock(sale)
            return redirect("receipt", sale_id=sale.id)

    return render(request, "sales/payment.html", {
        "sale": sale,
        "paystack_public_key": settings.PAYSTACK_PUBLIC_KEY,
        "customer_email": customer_email
    })

# ------------------ Receipt & Reports ------------------

@login_required
def receipt(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    sale_items = SaleItem.objects.filter(sale=sale)
    return render(request, "sales/receipt.html", {"sale": sale, "sale_items": sale_items})

@login_required
def daily_report(request):
    report = (
        Sale.objects
        .values('created_at__date')
        .annotate(orders=Count('id'), total_sales=Sum('total_amount'))
        .order_by('-created_at__date')
    )
    return render(request, "sales/report.html", {"report": report})

@login_required
def dashboard(request):
    today = timezone.now().date()
    total_sales = Sale.objects.filter(created_at__date=today).aggregate(total=Sum('total_amount'))['total'] or Decimal("0")
    total_orders = Sale.objects.filter(created_at__date=today).count()
    top_products = (
        SaleItem.objects
        .filter(sale__created_at__date=today)
        .values('product__product_name')
        .annotate(quantity_sold=Sum('quantity'))
        .order_by('-quantity_sold')[:5]
    )
    return render(request, "sales/dashboard.html", {
        "total_sales": total_sales,
        "total_orders": total_orders,
        "top_products": top_products,
        "total_customers": Customer.objects.count(),
        "total_products": Product.objects.count(),
    })

# ------------------ Webhook ------------------

@csrf_exempt
def paystack_webhook(request):
    if request.method != "POST":
        return JsonResponse({"status": "ignored"}, status=200)

    paystack_signature = request.headers.get("x-paystack-signature", "")
    body = request.body
    expected = hmac.new(settings.PAYSTACK_SECRET_KEY.encode(), body, hashlib.sha512).hexdigest()

    if not hmac.compare_digest(expected, paystack_signature):
        return JsonResponse({"error": "Invalid signature"}, status=400)

    payload = json.loads(body)
    if payload.get("event") == "charge.success":
        reference = payload["data"]["reference"]
        try:
            sale = Sale.objects.get(payment_reference=reference)
            if not sale.is_paid:
                sale.is_paid = True
                sale.amount_paid = sale.total_amount
                sale.change = Decimal("0")
                sale.save()
                _deduct_stock(sale)
        except Sale.DoesNotExist:
            pass

    return JsonResponse({"status": "ok"}, status=200)

# ------------------ Check Mobile Money Status ------------------

@login_required
def check_momo_status(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    if sale.is_paid:
        return redirect("receipt", sale_id=sale.id)
    if not sale.payment_reference:
        messages.error(request, "No payment reference found for this sale.")
        return redirect("payment", sale_id=sale.id)

    url = f"https://api.paystack.co/transaction/verify/{sale.payment_reference}"
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    result = requests.get(url, headers=headers).json()
    if result.get("status") and result["data"]["status"] == "success":
        sale.is_paid = True
        sale.amount_paid = sale.total_amount
        sale.change = Decimal("0")
        sale.save()
        _deduct_stock(sale)
        return redirect("receipt", sale_id=sale.id)
    return render(request, "sales/payment_pending.html", {
        "sale": sale,
        "phone": request.GET.get("phone", ""),
        "message": "Waiting for customer approval..."
    })