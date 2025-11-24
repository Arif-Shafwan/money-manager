from django.urls import path
from . import views

urlpatterns = [
# Auth
    path('', views.login_view, name='login'),
    path('logout/', views.Logout_View, name='logout'),
    path('signup/', views.signup_view, name='signup'),
]