from django.urls import path
from . import views

urlpatterns = [
# Dashboard
    path('Dashboard', views.dashboard, name='dashboard'),
    path("Advance-Analytics/", views.advanced_analytics, name="advanced_analytics"),     
    path("api/finance-assistant/", views.finance_assistant_api, name="finance_assistant_api"),
]