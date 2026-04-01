from django.urls import path
from . import views

urlpatterns = [
    path('', views.pos, name="pos"),
    path('add/<int:product_id>/', views.add_to_cart, name="add_to_cart"),
    path('remove/<int:product_id>/', views.remove_from_cart, name="remove_from_cart"),
    path('complete/', views.complete_sale, name="complete_sale"),
    path('receipts/<int:sale_id>/', views.receipt, name="receipt"),
    path('report/', views.daily_report, name='daily_report'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('payment/<int:sale_id>/', views.payment_view, name="payment"),
    path('payment/<int:sale_id>/check-momo/', views.check_momo_status, name="check_momo_status"),
    path('webhook/paystack/', views.paystack_webhook, name="paystack_webhook"),
]