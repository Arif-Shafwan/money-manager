from django.shortcuts import render
from datetime import date, timedelta
from calendar import monthrange
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Value, DecimalField
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from budget_core.models import Transaction, Category, Account, Budget
from django.db.models.functions import Coalesce, Cast
from openai import OpenAI
from django.conf import settings
from django.views.decorators.http import require_POST
import pandas as pd
from sklearn.linear_model import LinearRegression
from math import sqrt
from sklearn.metrics import mean_squared_error
from django.http import JsonResponse
from budget_dashboard.analytics_service import build_advanced_analytics

client = OpenAI(api_key=settings.OPENAI_API_KEY)

@login_required
def dashboard(request):
    user = request.user
    today = date.today()
    first_day = today.replace(day=1)
    last_day = today.replace(day=monthrange(today.year, today.month)[1])

    month_tx = Transaction.objects.filter(user=user, date__range=[first_day, last_day])
    income = month_tx.filter(type='income').aggregate(total=Sum('amount'))['total'] or 0
    expense = month_tx.filter(type='expense').aggregate(total=Sum('amount'))['total'] or 0
    net = income - expense
    spent = expense

    # NEW: Live Money = opening balances + all-time income - all-time expense
    opening_sum = Account.objects.filter(user=user).aggregate(total=Sum('balance'))['total'] or Decimal('0')
    all_tx = (
        Transaction.objects
        .filter(user=user)
        .values('type')
        .annotate(total=Sum('amount'))
    )
    in_total = Decimal('0'); out_total = Decimal('0')
    for row in all_tx:
        if row['type'] == 'income':
            in_total += row['total'] or 0
        else:
            out_total += row['total'] or 0
    live_total = Decimal(opening_sum) + in_total - out_total

    # --- Daily expenses for current month ---
    # Month bounds: [start, next_month_start)
    start = date(today.year, today.month, 1)
    next_month_start = date(today.year + (1 if today.month == 12 else 0),
                            1 if today.month == 12 else today.month + 1, 1)

    # Pull only what we need (no DB functions)
    qs = (
        Transaction.objects
        .filter(
            user=user,                      # remove if you don't filter per-user
            type__iexact='expense',
            date__gte=start,
            date__lt=next_month_start,
            date__isnull=False,
        )
        .values_list('date', 'amount')
    )

    # Sum per day in Python (works for DateField or DateTimeField)
    totals_by_day = {}
    for d, amt in qs:
        if d is None:
            continue
        day_num = (d.day if hasattr(d, "day") else int(str(d)[8:10]))  # super defensive
        totals_by_day[day_num] = totals_by_day.get(day_num, 0) + float(amt or 0)

    last_day = (next_month_start - start).days
    exp_daily_labels = [f"{i:02d}" for i in range(1, last_day + 1)]
    exp_daily_values = [totals_by_day.get(i, 0.0) for i in range(1, last_day + 1)]

    # Chart data: last 6 months expense by month
    chart_labels = []
    chart_values = []
    m, y = today.month, today.year
    for _ in range(6):
        chart_labels.append(f"{y}-{m:02d}")
        start = date(y, m, 1)
        end = date(y, m, monthrange(y, m)[1])
        total = Transaction.objects.filter(user=user, type='expense', date__range=[start, end]).aggregate(Sum('amount'))['amount__sum'] or 0
        chart_values.append(float(total))
        # prev month
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    chart_labels.reverse(); chart_values.reverse()

    # Budgets status for this month
    budgets = Budget.objects.filter(user=user, month__year=today.year, month__month=today.month).select_related('category')
    spent_by_cat = (
        month_tx.filter(type='expense')
        .values('category__id', 'category__name')
        .annotate(total=Sum('amount'))
    )
    spent_map = {row['category__id']: row['total'] for row in spent_by_cat}

    live_after_month_expense = Decimal(live_total) - Decimal(expense or 0)
    live_money = live_after_month_expense + income

    budget_labels = [b.category.name for b in budgets]
    budget_values = [float(b.amount or 0) for b in budgets]
    spent_values = [float(spent_map.get(b.category_id, 0) or 0) for b in budgets]
    total=Coalesce(Sum('amount'), Cast(Value(0), DecimalField(max_digits=12, decimal_places=2)))

    accounts = Account.objects.filter(user=request.user).order_by('name')
    # Compute live balances: opening + income - expense per account
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
        a.live_balance = (opening + in_sum) - out_sum

    context = {
        'income': income, 
        'expense': expense, 
        'net': net, 
        'spent':spent,
        'live_total': live_total, 
        'live_money':live_money,
        'exp_daily_labels': exp_daily_labels, 
        'exp_daily_values': exp_daily_values,
        'live_after_month_expense': live_after_month_expense, 
        'chart_labels': chart_labels, 
        'chart_values': chart_values,
        'budgets': budgets, 
        'spent_map': spent_map,
        'budget_labels': budget_labels, 
        'budget_values': budget_values, 
        'spent_values': spent_values,
        'accounts':accounts,
    }
    return render(request, 'budget_dashboard/pages/dashboard.html', context)

@login_required
def advanced_analytics(request):
    """
    Render the Advanced Analytics page using the shared helper.
    """
    try:
        months = int(request.GET.get("months", 6))
    except ValueError:
        months = 6

    analytics_ctx = build_advanced_analytics(request.user, months=months)

    # analytics_ctx already has months, but we override just in case
    analytics_ctx["months"] = months

    return render(
        request,
        "budget_dashboard/pages/advanced_analytics.html",
        analytics_ctx,
    )

@login_required
@require_POST
def finance_assistant_api(request):
    """
    POST: { message: "question text", months: "6" (optional) }
    Returns: { answer: "AI reply" } OR { error: "..." }
    """
    user = request.user
    message = (request.POST.get("message") or "").strip()

    try:
        months = int(request.POST.get("months") or 6)
    except ValueError:
        months = 6

    if not message:
        return JsonResponse({"error": "Empty message."}, status=400)

    # 1) Get analytics snapshot for this user
    analytics = build_advanced_analytics(user, months=months)

    current_balance       = analytics.get("current_balance")
    predicted_30d_expense = analytics.get("predicted_30d_expense")
    predicted_30d_income  = analytics.get("predicted_30d_income")
    expected_balance_30   = analytics.get("expected_balance_30")
    net_30                = analytics.get("net_30")
    top_categories        = analytics.get("top_categories") or []
    rmse_expense          = analytics.get("rmse_expense")
    rmse_income           = analytics.get("rmse_income")
    has_income_data       = analytics.get("has_income_data", False)

    # Top categories text
    if top_categories:
        cat_bits = []
        for row in top_categories:
            name = row.get("category__name") or "Uncategorised"
            total = row.get("total") or 0
            cat_bits.append(f"{name} (RM {float(total):.2f})")
        top_cat_text = ", ".join(cat_bits)
    else:
        top_cat_text = "No strong spending categories yet."

    analytics_text = f"""
User: {user.username} | History window: last {months} month(s).

Current balance (all accounts combined): RM {float(current_balance or 0):.2f}

Predicted next 30 days:
- Expenses: {('RM %.2f' % float(predicted_30d_expense)) if predicted_30d_expense is not None else 'N/A'}
- Income:   {('RM %.2f' % float(predicted_30d_income)) if predicted_30d_income is not None else 'N/A'}

Expected balance in 30 days: {('RM %.2f' % float(expected_balance_30)) if expected_balance_30 is not None else 'N/A'}
Net 30-day cash flow (income - expense): {('RM %.2f' % float(net_30)) if net_30 is not None else 'N/A'}

Top spending categories recently:
{top_cat_text}

Model quality (approximate):
- Expense model RMSE: {('RM %.2f' % rmse_expense) if rmse_expense is not None else 'N/A'}
- Income model RMSE:  {('RM %.2f' % rmse_income) if (has_income_data and rmse_income is not None) else 'N/A or no income data'}
""".strip()

    system_prompt = """
You are a helpful, cautious personal finance assistant for an app called "Money Manager".

You are given a summary of the user's real financial analytics (balances, predicted expenses/income,
top spending categories, and model quality). Use ONLY this data and general money management
knowledge to answer questions.

Constraints:
- Do NOT give investment or trading recommendations for specific stocks, crypto, or complex products.
- Instead, focus on budgeting, spending control, emergency funds, saving habits, and general advice.
- Highlight risky behaviours gently (e.g. overspending, negative cashflow).
- Keep answers short and clear (3–6 short paragraphs or bullet points).
- If something is uncertain because the data is missing, say so.
- Always remind that this is not professional financial advice.
"""

    user_prompt = f"""
Here is my analytics summary:

{analytics_text}

Now my question is:
{message}
"""

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",   # or other model
            temperature=0.3,
            max_tokens=400,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        answer = completion.choices[0].message.content.strip()
        return JsonResponse({"answer": answer})
    except Exception as e:
        return JsonResponse({"error": f"AI error: {e}"}, status=500)