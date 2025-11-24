# budget_auth/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.contrib.auth import authenticate, get_user_model, login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.db.models import Sum, Value, DecimalField
from django.db.models.deletion import ProtectedError
from django.db.models.functions import TruncDate, Coalesce, Cast
from django.utils import timezone
from django.contrib.auth import login

from datetime import date
from calendar import monthrange
from decimal import Decimal

from budget_core.models import Transaction, Category, Account, Budget

User = get_user_model()

# ──────────────────────────────────────────────────────────────────────────────
# Auth - Login
# ──────────────────────────────────────────────────────────────────────────────
def login_view(request):
    """
    Show login form on GET.
    Handle username/password login on POST.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        if not username or not password:
            messages.error(request, "Please fill in both username and password.")
            return render(request, "budget_auth/pages/login.html")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            # ✅ Log this user in (creates/attaches session)
            auth_login(request, user)

            # Make sure we have a session_key
            if not request.session.session_key:
                request.session.save()

            current_key = request.session.session_key
            user_id_str = str(user.id)

            # ✅ ONE SESSION PER USER:
            # Delete other sessions that belong to this same user
            sessions = Session.objects.filter(
                expire_date__gte=timezone.now()
            )

            for s in sessions:
                data = s.get_decoded()
                if data.get('_auth_user_id') == user_id_str and s.session_key != current_key:
                    s.delete()

            messages.success(request, f"Welcome back, {user.username}!")

            # Support ?next=/some/url
            next_url = request.GET.get("next") or request.POST.get("next")
            if next_url:
                return redirect(next_url)
            return redirect("dashboard")
        else:
            messages.error(request, "Invalid username or password.")
            return render(request, "budget_auth/pages/login.html")

    # GET request → show form
    return render(request, "budget_auth/pages/login.html")



# ──────────────────────────────────────────────────────────────────────────────
# Auth - Sing Up
# ──────────────────────────────────────────────────────────────────────────────
def signup_view(request):
    """
    Show signup form on GET.
    Handle manual username/email/password signup on POST.
    """
    if request.user.is_authenticated:
        # Already logged in – send to your main page
        return redirect('dashboard')  # change 'dashboard' to your url name

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        # Basic validation
        if not username or not email or not password or not confirm_password:
            messages.error(request, "Please fill in all fields.")
            return render(request, "budget_auth/pages/signup.html")

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, "budget_auth/pages/signup.html")

        # Check if username already exists
        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, "This username is already taken.")
            return render(request, "budget_auth/pages/signup.html")

        # Optional: check if email already used
        if email and User.objects.filter(email__iexact=email).exists():
            messages.error(request, "This email is already registered.")
            return render(request, "budget_auth/pages/signup.html")

        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
        )

        messages.success(request, "Account created successfully. You are now logged in.")

        # Auto-login after signup (you can remove this if you prefer redirect to login page)
        auth_login(request, user)

        return redirect("dashboard")  # change to your home/dashboard url name

    # GET request → show empty form
    return render(request, "budget_auth/pages/signup.html")



# ──────────────────────────────────────────────────────────────────────────────
# Auth - Logout
# ──────────────────────────────────────────────────────────────────────────────
def Logout_View(request):
    """
    Log the user out and redirect to login page.
    """
    if request.user.is_authenticated:
        logout(request)
        messages.success(request, "You have been logged out.")

    # Change 'login' if your login url name is different
    return redirect('login')