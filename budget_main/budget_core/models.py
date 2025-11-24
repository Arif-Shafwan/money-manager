from django.db import models
from django.contrib.auth.models import User

class Category(models.Model):
    TYPE_CHOICES = (
        ('income', 'Income'),
        ('expense', 'Expense'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=64)
    type = models.CharField(max_length=7, choices=TYPE_CHOICES)

    class Meta:
        unique_together = ('user', 'name', 'type')
        ordering = ['type', 'name']
        db_table = "money_category" 

    def __str__(self):
        return f"{self.name} ({self.type})"

class Account(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=64)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        unique_together = ('user', 'name')
        ordering = ['name']
        db_table = "money_account" 

    def __str__(self):
        return self.name

class Transaction(models.Model):
    TYPE_CHOICES = Category.TYPE_CHOICES
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    type = models.CharField(max_length=7, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']
        db_table = "money_transaction" 

    def __str__(self):
        return f"{self.type} {self.amount} - {self.category}"

class Budget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    month = models.DateField(help_text='Use the 1st of month, e.g., 2025-08-01')
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ('user', 'category', 'month')
        ordering = ['-month']
        db_table = "money_budget" 

    def __str__(self):
        return f"{self.category.name} - {self.month:%Y-%m}"
