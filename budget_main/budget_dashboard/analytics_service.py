# budget_dashboard/analytics_service.py

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum, Count

import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
from math import sqrt

from budget_core.models import Transaction, Account


def build_advanced_analytics(user, months=6):
    """
    Core analytics helper used by:
      - advanced_analytics page
      - finance_assistant_api (AI chatbot)

    Returns a dict with:
      - has_any_data, months
      - hist/future expense series + RMSE
      - income model RMSE
      - current_balance, predicted_30d_expense, predicted_30d_income
      - net_30, expected_balance_30, rec_budget, saved_if_reduce_10
      - cat_labels, cat_values, top_categories
      - type_labels, type_counts
    """
    today = date.today()
    start_date = today - timedelta(days=30 * int(months))

    base_qs = Transaction.objects.filter(
        user=user,
        date__gte=start_date,
        date__lte=today,
    )

    exp_qs = (
        base_qs.filter(type="expense")
        .values("date")
        .annotate(total=Sum("amount"))
        .order_by("date")
    )
    inc_qs = (
        base_qs.filter(type="income")
        .values("date")
        .annotate(total=Sum("amount"))
        .order_by("date")
    )

    def build_time_series(qs):
        """
        Given a queryset grouped by date with 'date' and 'total',
        train a LinearRegression on day_index -> total,
        return historical series, 30-day forecast, and RMSE.
        """
        if not qs:
            return None

        df = pd.DataFrame(list(qs))
        df["date"] = pd.to_datetime(df["date"])
        df["total"] = df["total"].astype(float)
        df = df.sort_values("date")
        df["day_index"] = range(len(df))

        n = len(df)
        if n < 10:
            train_df = df.copy()
            test_df = None
        else:
            split_idx = int(n * 0.8)
            train_df = df.iloc[:split_idx].copy()
            test_df = df.iloc[split_idx:].copy()

        X_train = train_df[["day_index"]].values
        y_train = train_df["total"].values

        model = LinearRegression()
        model.fit(X_train, y_train)

        rmse = None
        if test_df is not None and len(test_df) > 0:
            X_test = test_df[["day_index"]].values
            y_test = test_df["total"].values
            y_pred = model.predict(X_test)
            mse = mean_squared_error(y_test, y_pred)
            rmse = float(sqrt(mse))

        # Predict next 30 days
        last_index = int(df["day_index"].max())
        future_indices = list(range(last_index + 1, last_index + 31))
        X_future = pd.DataFrame({"day_index": future_indices})[["day_index"]].values
        future_pred = model.predict(X_future)
        future_pred = [max(0.0, float(v)) for v in future_pred]  # no negatives

        hist_labels = [d.strftime("%Y-%m-%d") for d in df["date"]]
        hist_values = [float(v) for v in df["total"]]

        future_dates = [today + timedelta(days=i) for i in range(1, 31)]
        future_labels = [d.strftime("%Y-%m-%d") for d in future_dates]

        return {
            "hist_labels": hist_labels,
            "hist_values": hist_values,
            "future_labels": future_labels,
            "future_values": future_pred,
            "rmse": rmse,
        }

    expense_series = build_time_series(exp_qs) if exp_qs else None
    income_series = build_time_series(inc_qs) if inc_qs else None

    has_any_data = bool(expense_series or income_series)

    # Current overall balance
    accounts = Account.objects.filter(user=user)
    opening_total = sum(Decimal(a.balance or 0) for a in accounts)

    totals_by_type = base_qs.values("type").annotate(total=Sum("amount"))

    income_total = Decimal("0")
    expense_total = Decimal("0")
    for row in totals_by_type:
        if row["type"] == "income":
            income_total += Decimal(row["total"] or 0)
        elif row["type"] == "expense":
            expense_total += Decimal(row["total"] or 0)

    current_balance = opening_total + income_total - expense_total

    # 30-day forecasts
    predicted_30d_expense = None
    predicted_30d_income = None

    if expense_series:
        predicted_30d_expense = Decimal(str(sum(expense_series["future_values"])))
    if income_series:
        predicted_30d_income = Decimal(str(sum(income_series["future_values"])))

    net_30 = expected_balance_30 = rec_budget = saved_if_reduce_10 = None

    if predicted_30d_expense is not None or predicted_30d_income is not None:
        e = predicted_30d_expense if predicted_30d_expense is not None else Decimal("0")
        i = predicted_30d_income if predicted_30d_income is not None else Decimal("0")

        net_30 = i - e
        expected_balance_30 = current_balance + net_30

        if predicted_30d_expense is not None:
            rec_budget = e * Decimal("0.90")
            saved_if_reduce_10 = e - rec_budget

    # Category analytics (expenses only)
    cat_agg = (
        base_qs.filter(type="expense")
        .values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )

    cat_labels = []
    cat_values = []
    for row in cat_agg:
        label = row["category__name"] or "Uncategorised"
        cat_labels.append(label)
        cat_values.append(float(row["total"] or 0))

    top_categories = list(cat_agg[:3])

    # Transaction type analytics
    type_agg = (
        base_qs.values("type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    type_labels = []
    type_counts = []
    for row in type_agg:
        t_label = (row["type"] or "").title() or "Unknown"
        type_labels.append(t_label)
        type_counts.append(int(row["count"] or 0))

    return {
        "has_any_data": has_any_data,
        "months": months,

        "hist_labels": expense_series["hist_labels"] if expense_series else [],
        "hist_values": expense_series["hist_values"] if expense_series else [],
        "future_labels": expense_series["future_labels"] if expense_series else [],
        "future_values": expense_series["future_values"] if expense_series else [],
        "rmse_expense": expense_series["rmse"] if expense_series else None,

        "has_income_data": bool(income_series),
        "rmse_income": income_series["rmse"] if income_series else None,

        "current_balance": current_balance,
        "predicted_30d_expense": predicted_30d_expense,
        "predicted_30d_income": predicted_30d_income,
        "net_30": net_30,
        "expected_balance_30": expected_balance_30,
        "rec_budget": rec_budget,
        "saved_if_reduce_10": saved_if_reduce_10,

        "cat_labels": cat_labels,
        "cat_values": cat_values,
        "top_categories": top_categories,

        "type_labels": type_labels,
        "type_counts": type_counts,
    }
