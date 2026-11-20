from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('sales/', views.sales_report, name='sales_report'),
    path('customers/', views.customer_profile, name='customer_profile'),
    path('revenue-loss/', views.revenue_loss_report, name='revenue_loss_report'),
    path('cost/', views.cost_report, name='cost_report'),
]