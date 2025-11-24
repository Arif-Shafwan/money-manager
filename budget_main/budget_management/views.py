from django.shortcuts import render
from datetime import date
from calendar import monthrange
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Value, DecimalField
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from budget_core.models import Transaction, Category, Account, Budget
from django.db.models.deletion import ProtectedError
from django.db.models.functions import TruncDate, Coalesce, Cast
from django.utils import timezone
from itertools import groupby
from django.db.models import Q

# ──────────────────────────────────────────────────────────────────────────────
# Management - Accounts
# ──────────────────────────────────────────────────────────────────────────────
@login_required
def account_list(request):
    # 1) Get all accounts for this user
    accounts = Account.objects.filter(user=request.user).order_by('name')

    # 2) Compute live balances: opening + income - expense per account
    tx = Transaction.objects.filter(user=request.user)
    totals = (
        tx.values('account_id', 'type')
          .annotate(total=Sum('amount'))
    )

    acc_totals = {}
    for row in totals:
        aid = row['account_id']
        typ = row['type']
        acc_totals.setdefault(aid, {'in': Decimal('0'), 'out': Decimal('0')})
        if typ == 'income':
            acc_totals[aid]['in'] += row['total'] or 0
        else:
            acc_totals[aid]['out'] += row['total'] or 0

    for a in accounts:
        opening = Decimal(a.balance or 0)
        in_sum = acc_totals.get(a.id, {}).get('in', Decimal('0'))
        out_sum = acc_totals.get(a.id, {}).get('out', Decimal('0'))
        a.live_balance = opening + in_sum - out_sum

    # 3) Handle manual <input> form submit
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        balance_str = (request.POST.get('balance') or '').strip()

        if not name or not balance_str:
            messages.error(request, "Please fill in both account name and balance.")
        else:
            try:
                balance = Decimal(balance_str)
            except Exception:
                messages.error(request, "Invalid balance format.")
            else:
                Account.objects.create(
                    user=request.user,
                    name=name,
                    balance=balance,
                )
                messages.success(request, "Account created successfully.")
                return redirect('accounts')  # same as before

    # 4) Render template (no Django form object now)
    context = {
        'accounts': accounts,
        'type': 'account',  # so your template shows the account inputs
    }
    return render(request, 'budget_management/accounts/account_list.html', context)

@login_required
def account_create(request):
    return redirect('accounts')

@login_required
def account_edit(request, pk):
    obj = get_object_or_404(Account, pk=pk, user=request.user)

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        balance_str = (request.POST.get("balance") or "").strip()

        if not name or not balance_str:
            messages.error(request, "Please fill in both name and opening balance.")
        else:
            try:
                balance = Decimal(balance_str)
            except Exception:
                messages.error(request, "Invalid balance format.")
            else:
                obj.name = name
                obj.balance = balance
                obj.save()
                messages.success(request, "Account updated successfully.")
                return redirect("accounts")

    context = {
        "title": "Edit Account",
        "obj": obj,
    }
    return render(request, "budget_management/accounts/account_edit.html", context)

@login_required
def account_delete(request, pk):
    obj = get_object_or_404(Account, pk=pk, user=request.user)
    error = None

    if request.method == "POST":
        try:
            obj.delete()
            return redirect("accounts")
        except ProtectedError:
            error = "You can't delete this account because it is used by one or more transactions."

    context = {
        "obj": obj,
        "error": error,
    }
    return render(request, "budget_management/accounts/account_delete.html", context)


@login_required
def account_transfer(request):
    # All user accounts for the dropdowns
    accounts = Account.objects.filter(user=request.user).order_by("name")

    if request.method == "POST":
        from_id    = request.POST.get("from_account")
        to_id      = request.POST.get("to_account")
        amount_str = (request.POST.get("amount") or "").strip()
        date_str   = (request.POST.get("date") or "").strip()
        note       = (request.POST.get("note") or "").strip()

        # Basic validation
        if not from_id or not to_id or not amount_str or not date_str:
            messages.error(request, "Please fill in all required fields.")
        elif from_id == to_id:
            messages.error(request, "You must select two different accounts.")
        else:
            try:
                src = Account.objects.get(pk=from_id, user=request.user)
                dst = Account.objects.get(pk=to_id,   user=request.user)
            except Account.DoesNotExist:
                messages.error(request, "Invalid account selection.")
            else:
                # amount
                try:
                    amt = Decimal(amount_str)
                except InvalidOperation:
                    messages.error(request, "Invalid amount format.")
                else:
                    if amt <= 0:
                        messages.error(request, "Amount must be greater than zero.")
                    else:
                        # date from <input type="date">
                        try:
                            dt = date.fromisoformat(date_str)
                        except ValueError:
                            messages.error(request, "Invalid date format.")
                        else:
                            user = request.user

                            # ✅ Ensure there is enough money in source (optional but smart)
                            src_balance = src.balance or Decimal("0")
                            if src_balance < amt:
                                messages.error(request, "Insufficient balance in source account.")
                            else:
                                # Ensure transfer categories exist
                                cat_out, _ = Category.objects.get_or_create(
                                    user=user, name="Transfer", type="out-transfer"
                                )
                                cat_in, _ = Category.objects.get_or_create(
                                    user=user, name="Transfer", type="in-transfer"
                                )

                                # Outflow from source
                                Transaction.objects.create(
                                    user=user,
                                    account=src,
                                    category=cat_out,
                                    type="out-transfer",
                                    amount=amt,
                                    date=dt,
                                    note=f"Transfer to {dst.name}. {note}".strip(),
                                )

                                # Inflow to destination
                                Transaction.objects.create(
                                    user=user,
                                    account=dst,
                                    category=cat_in,
                                    type="in-transfer",
                                    amount=amt,
                                    date=dt,
                                    note=f"Transfer from {src.name}. {note}".strip(),
                                )

                                # ✅ UPDATE ACCOUNT BALANCES DIRECTLY
                                src.balance = (src.balance or Decimal("0")) - amt
                                dst.balance = (dst.balance or Decimal("0")) + amt
                                src.save()
                                dst.save()

                                messages.success(request, "Transfer recorded.")
                                return redirect("accounts")

    context = {
        "title": "Transfer Between Accounts",
        "accounts": accounts,
    }
    return render(request, "budget_management/accounts/account_transfer.html", context)



# ──────────────────────────────────────────────────────────────────────────────
# Management - Budgets
# ──────────────────────────────────────────────────────────────────────────────
@login_required
def budget_list(request):
    # All budgets for this user
    budgets = Budget.objects.filter(user=request.user).order_by("-month")

    # All categories for this user (for the <select>)
    categories = Category.objects.filter(user=request.user).order_by("name")

    if request.method == "POST":
        category_id = request.POST.get("category")
        month_str   = (request.POST.get("month") or "").strip()   # from <input type="date"> -> 'YYYY-MM-DD'
        amount_str  = (request.POST.get("amount") or "").strip()

        if not category_id or not month_str or not amount_str:
            messages.error(request, "Please fill in category, date and amount.")
        else:
           # Validate category (FK)
            category = get_object_or_404(Category, pk=category_id, user=request.user)

            # 🔧 Parse full date from type="date"
            try:
                dt = date.fromisoformat(month_str)
            except ValueError:
                messages.error(request, "Invalid date format.")
            else:
                # Parse amount
                try:
                    amount = Decimal(amount_str)
                except InvalidOperation:
                    messages.error(request, "Invalid amount format.")
                else:
                    if amount <= 0:
                        messages.error(request, "Amount must be greater than zero.")
                    else:
                        Budget.objects.create(
                            user=request.user,
                            category=category,
                            month=dt,   # DateField: store full date
                            amount=amount,
                        )
                        messages.success(request, "Budget created successfully.")
                        return redirect("budgets")

    context = {
        "budgets": budgets,
        "categories": categories,
        "type": "budget",
    }
    return render(request, "budget_management/budgets/budget_list.html", context)

@login_required
def budget_create(request):
    return redirect('budgets')

@login_required
def budget_edit(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    categories = Category.objects.filter(user=request.user).order_by("name")

    if request.method == "POST":
        category_id = request.POST.get("category")
        month_str   = (request.POST.get("month") or "").strip()   # from <input type="date">
        amount_str  = (request.POST.get("amount") or "").strip()

        if not category_id or not month_str or not amount_str:
            messages.error(request, "Please fill in category, date and amount.")
        else:
            # Validate category belongs to this user
            category = get_object_or_404(Category, pk=category_id, user=request.user)

            # Parse date from ISO string 'YYYY-MM-DD'
            try:
                month_date = date.fromisoformat(month_str)
            except ValueError:
                messages.error(request, "Invalid date format.")
            else:
                # Parse amount
                try:
                    amount = Decimal(amount_str)
                except InvalidOperation:
                    messages.error(request, "Invalid amount format.")
                else:
                    if amount <= 0:
                        messages.error(request, "Amount must be greater than zero.")
                    else:
                        # Update the existing budget
                        budget.category = category
                        budget.month = month_date
                        budget.amount = amount
                        budget.save()

                        messages.success(request, "Budget updated successfully.")
                        return redirect("budgets")

    context = {
        "title": "Edit Budget",
        "type": "budget",
        "budget": budget,
        "categories": categories,
    }
    return render(request, "budget_management/budgets/budget_edit.html", context)

@login_required
def budget_delete(request, pk):
    obj = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == 'POST':
        obj.delete()
        return redirect('budgets')
    return render(request, 'budget_management/budgets/budget_delete.html', {'obj': obj})



# ──────────────────────────────────────────────────────────────────────────────
# Management - Categories
# ──────────────────────────────────────────────────────────────────────────────
@login_required
def category_list(request):
    # List all categories for this user
    cats = Category.objects.filter(user=request.user).order_by("name")

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        cat_type = (request.POST.get("type") or "").strip()  # e.g. 'income' / 'expense'

        if not name or not cat_type:
            messages.error(request, "Please fill in both category name and type.")
        else:
            # Optional: normalise the type
            cat_type_norm = cat_type.lower().strip()

            # Optional: simple validation for type
            # if cat_type_norm not in ("income", "expense"):
            #     messages.error(request, "Type must be 'income' or 'expense'.")
            # else:
            Category.objects.create(
                user=request.user,
                name=name,
                type=cat_type_norm,  # or cat_type if you don't want to normalise
            )
            messages.success(request, "Category created successfully.")
            return redirect("categories")  # make sure this URL name exists

    context = {
        "cats": cats,
        "type": "category",
    }
    return render(request, "budget_management/categories/category_list.html", context)

@login_required
def category_create(request):
    return redirect('categories')

@login_required
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        cat_type = (request.POST.get("type") or "").strip()

        if not name or not cat_type:
            messages.error(request, "Please fill in both category name and type.")
        else:
            # Optional: normalise the type
            cat_type_norm = cat_type.lower().strip()

            category.name = name
            category.type = cat_type_norm   # or just cat_type
            category.save()

            messages.success(request, "Category updated successfully.")
            return redirect("categories")

    context = {
        "title": "Edit Category",
        "category": category,
        "type": "category",
    }
    # Adjust template path if needed
    return render(request, "budget_management/categories/category_edit.html", context)

@login_required
def category_delete(request, pk):
    obj = get_object_or_404(Category, pk=pk, user=request.user)
    error = None
    if request.method == 'POST':
        try:
            obj.delete()
            return redirect('categories')
        except ProtectedError:
            error = "You can't delete this category because it is used by one or more transactions."
        
    context = {
        'obj': obj, 
        'error': error
    }
    return render(request, 'budget_management/categories/category_delete.html', context)



# ──────────────────────────────────────────────────────────────────────────────
# Management - Transactions
# ──────────────────────────────────────────────────────────────────────────────
@login_required
def transaction_list(request):
    q          = (request.GET.get("q") or "").strip()
    account_id = (request.GET.get("account") or "").strip()
    year_str   = (request.GET.get("year") or "").strip()  # NEW

    # Base queryset for this user
    base_qs = Transaction.objects.filter(user=request.user)

    # Build year options (all years that have transactions for this user)
    year_qs = base_qs.dates("date", "year", order="DESC")
    years = [d.year for d in year_qs]

    # Apply filters
    tx = base_qs.select_related("account", "category")

    if q:
        tx = tx.filter(
            Q(note__icontains=q) |
            Q(category__name__icontains=q)
        )

    if account_id:
        tx = tx.filter(account_id=account_id)

    if year_str:
        try:
            year_int = int(year_str)
            tx = tx.filter(date__year=year_int)
        except ValueError:
            pass  # ignore invalid year

    # Order by date desc for grouping
    tx = tx.order_by("-date", "-id")

    # Group by month (YYYY-MM)
    months = []
    for key, group in groupby(tx, key=lambda t: t.date.strftime("%Y-%m")):
        group_list = list(group)
        if not group_list:
            continue
        label = group_list[0].date.strftime("%B %Y")  # e.g. "January 2025"
        months.append({
            "key": key,
            "label": label,
            "tx_list": group_list,
        })

    accounts = Account.objects.filter(user=request.user).order_by("name")

    context = {
        "months": months,
        "accounts": accounts,
        "q": q,
        "account_id": account_id,
        "years": years,        # list of years for dropdown
        "year": year_str,      # currently selected year
    }
    return render(request, "budget_management/transactions/transaction_list.html", context)

@login_required
def transaction_create(request):
    # For the dropdowns in the form
    accounts = Account.objects.filter(user=request.user).order_by("name")
    categories = Category.objects.filter(user=request.user).order_by("name")

    if request.method == "POST":
        account_id  = request.POST.get("account")
        category_id = request.POST.get("category")
        tx_type     = (request.POST.get("type") or "").strip().lower()
        amount_str  = (request.POST.get("amount") or "").strip()
        date_str    = (request.POST.get("date") or "").strip()
        note        = (request.POST.get("note") or "").strip()

        # Basic required validation
        if not account_id or not category_id or not tx_type or not amount_str or not date_str:
            messages.error(request, "Please fill in all required fields.")
        else:
            # Validate account + category belong to current user
            account = get_object_or_404(Account, pk=account_id, user=request.user)
            category = get_object_or_404(Category, pk=category_id, user=request.user)

            # Validate type
            if tx_type not in ("income", "expense"):
                messages.error(request, "Type must be income or expense.")
            else:
                # Parse amount
                try:
                    amount = Decimal(amount_str)
                except InvalidOperation:
                    messages.error(request, "Invalid amount format.")
                else:
                    if amount <= 0:
                        messages.error(request, "Amount must be greater than zero.")
                    else:
                        # Parse date from <input type="date">
                        try:
                            tx_date = date.fromisoformat(date_str)
                        except ValueError:
                            messages.error(request, "Invalid date format.")
                        else:
                            # Create transaction
                            Transaction.objects.create(
                                user=request.user,
                                account=account,
                                category=category,
                                type=tx_type,
                                amount=amount,
                                date=tx_date,
                                note=note,
                            )
                            messages.success(request, "Transaction added successfully.")
                            return redirect("transactions")

    # GET or failed POST → show form again
    context = {
        "title": "Add Transaction",
        "accounts": accounts,
        "categories": categories,
        "transaction": None,  # template can use this for create/edit reuse
    }
    return render(request, "budget_management/transactions/transaction_form.html", context)

@login_required
def transaction_edit(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk, user=request.user)
    accounts = Account.objects.filter(user=request.user).order_by("name")
    categories = Category.objects.filter(user=request.user).order_by("name")

    if request.method == "POST":
        account_id  = request.POST.get("account")
        category_id = request.POST.get("category")
        tx_type     = (request.POST.get("type") or "").strip().lower()
        amount_str  = (request.POST.get("amount") or "").strip()
        date_str    = (request.POST.get("date") or "").strip()
        note        = (request.POST.get("note") or "").strip()

        if not account_id or not category_id or not tx_type or not amount_str or not date_str:
            messages.error(request, "Please fill in all required fields.")
        else:
            account  = get_object_or_404(Account, pk=account_id, user=request.user)
            category = get_object_or_404(Category, pk=category_id, user=request.user)

            if tx_type not in ("income", "expense"):
                messages.error(request, "Type must be income or expense.")
            else:
                try:
                    amount = Decimal(amount_str)
                except InvalidOperation:
                    messages.error(request, "Invalid amount format.")
                else:
                    if amount <= 0:
                        messages.error(request, "Amount must be greater than zero.")
                    else:
                        try:
                            tx_date = date.fromisoformat(date_str)
                        except ValueError:
                            messages.error(request, "Invalid date format.")
                        else:
                            # 🔁 Update existing transaction
                            transaction.account = account
                            transaction.category = category
                            transaction.type = tx_type
                            transaction.amount = amount
                            transaction.date = tx_date
                            transaction.note = note
                            transaction.save()

                            messages.success(request, "Transaction updated successfully.")
                            return redirect("transactions")

    context = {
        "title": "Edit Transaction",
        "accounts": accounts,
        "categories": categories,
        "transaction": transaction,  # <-- edit mode: existing data passed in
    }
    return render(request, "budget_management/transactions/transaction_form.html", context)

@login_required
def transaction_delete(request, pk):
    obj = get_object_or_404(Transaction, pk=pk, user=request.user)

    if request.method == "POST":
        obj.delete()
        return redirect("transactions")

    context = {
        "obj": obj,
    }
    return render(request, "budget_management/transactions/transaction_delete.html", context)