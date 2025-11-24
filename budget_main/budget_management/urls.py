from django.urls import path
from . import views

urlpatterns = [
# Accounts
    path('Manage-Accounts', views.account_list, name='accounts'),
    path('Create-Accounts', views.account_create, name='account_create'),
    path('Edit-Accounts/<int:pk>/edit/', views.account_edit, name='account_edit'),
    path('Delete-Accounts/<int:pk>/delete/', views.account_delete, name='account_delete'),
    path('Transfer-Accounts/transfer/', views.account_transfer, name='account_transfer'),

# Budgets
    path('Manage-Budgets/', views.budget_list, name='budgets'),
    path('Create-Budgets/', views.budget_create, name='budget_create'),
    path('Edit-Budgets/<int:pk>/edit/', views.budget_edit, name='budget_edit'),
    path('Delete-Budgets/<int:pk>/delete/', views.budget_delete, name='budget_delete'),

# Categories
    path('Manage-Categories/', views.category_list, name='categories'),
    path('Create-Categories/', views.category_create, name='category_create'),
    path('Edit-Categories<int:pk>/edit/', views.category_edit, name='category_edit'),
    path('Delete-Categories/<int:pk>/delete/', views.category_delete, name='category_delete'),

# Transactions
    path('Manage-Transactions/', views.transaction_list, name='transactions'),
    path('Create-Transactions/', views.transaction_create, name='transaction_create'),
    path('Edit-Transactions/<int:pk>/edit/', views.transaction_edit, name='transaction_edit'),
    path('Delete-Transactions/<int:pk>/delete/', views.transaction_delete, name='transaction_delete'),

]