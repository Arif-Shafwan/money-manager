# 💸 Money Manager

Money Manager is a simple personal finance web app built with **Django** that helps you track:

- Multiple **accounts** (cash, bank, e-wallet, etc.)
- **Transactions** (income & expense)
- Monthly **budgets** by category
- Custom **categories** (income / expense)
- A clean, responsive **dashboard** with charts
- **Advanced analytics** (machine-learning forecasts)
- An **AI finance assistant** powered by OpenAI

The UI uses **Tailwind CSS (CDN)** and a light/dark theme toggle, and all pages (dashboard, lists, forms, delete confirmations) are optimized for both desktop and mobile.

---

## ✨ Features

### Authentication
- Username & password login
- Simple signup page
- **One active session per user** (user A & user B can both log in, but each only on one device)
- Dark / light theme toggle stored in `localStorage`

### Dashboard
- Current total **live balance** across all accounts
- **This month income** & **spent** summary
- Per-account **live balance** cards
- Line chart for **expenses (last 6 months)**
- Line chart for **daily expenses (current month)**
- Doughnut chart for **budgets vs spent** (current month)

### Accounts
- List of all accounts for logged-in user
- Opening balance + computed **live balance**
- Create / edit / delete account
- Transfer money between accounts (creates 2 linked transactions: outflow & inflow)

### Categories
- Custom categories with `name` and `type` (income / expense)
- Create / edit / delete category
- Used in transactions & budgets

### Budgets
- Monthly budget **per category**
- Create / edit / delete budget
- Used to show **Budget vs Spent** in dashboard charts

### Transactions
- List view with:
  - Filters (search, account, month, year)
  - Responsive table (desktop)
  - Mobile-friendly collapsible rows with “View / Edit / Delete”
- Add / edit transaction form
- Delete confirmation page

---

## 📊 Advanced Analytics (Machine Learning)

Available on the **Advanced Analytics** page.

The app uses simple **machine learning** (scikit-learn `LinearRegression`) on your historical transactions to:

- Forecast **daily expenses** for the next 30 days
- Forecast **daily income** (if income data exists) for the next 30 days
- Show:
  - Predicted total **30-day expenses**
  - Predicted total **30-day income**
  - **Net 30-day cash flow** (income − expense)
  - **Expected balance in 30 days** (current balance + net cash flow)
- Compute model quality using **RMSE** (root mean squared error) for:
  - Expense model
  - Income model

Additional analytics:

- **Expense by category** (pie/doughnut chart)
- **Transaction type usage** (bar chart: income vs expense)
- Highlight **top spending categories** so users can identify non-essential spending.

---

## 🤖 AI Finance Assistant

On the Advanced Analytics page there is a floating **chat bubble** (bottom-right).  
When the user clicks it:

- A small **chatbot panel** opens (website-style bubble chat).
- The bot reads a **summary** of the user’s analytics:
  - Current balance
  - 30-day expense & income forecasts
  - Expected balance in 30 days
  - Top spending categories
  - Model quality info
- Uses **OpenAI** (e.g. `gpt-4o-mini`) to answer questions like:
  - “Am I overspending this month?”
  - “Which categories should I cut first?”
  - “How much should I budget for next month?”
- Focuses on:
  - Budgeting
  - Spending control
  - Saving habits
  - Reducing non-essential purchases
- Does **not** give specific stock/crypto/investment picks.
- Always reminds that it is **not professional financial advice**.

Chat UI:

- Bubble chat layout (AI on left, user on right)
- Responses:
  - Paragraphs are **justified**
  - Lists are rendered as bullet points + justified text
- Scrollbar visually hidden for a cleaner look.

---

## 🧱 Tech Stack

- **Backend:** Django (Python)
- **Database:** SQLite (default) or any Django-supported DB (MySQL/PostgreSQL/etc.)
- **Frontend:** Tailwind CSS via CDN, vanilla JS
- **Charts:** [Chart.js CDN](https://www.chartjs.org/) for visualizations
- **Machine Learning / Analytics:**
  - `pandas`
  - `scikit-learn` (`LinearRegression`, `mean_squared_error`)
- **AI Assistant:**
  - OpenAI API (`gpt-4o-mini` or similar chat model)

Main apps (names based on this project):

- `budget_core` – base layout, dashboard, shared utilities
- `budget_auth` – login / signup / logout, session logic
- `budget_management` – accounts, categories, budgets, transactions
- `budget_dashboard` – dashboard and advanced analytics views + AI assistant API

---

## 🛠 Requirements

- Python **3.10+** (recommended)
- pip install uv
- A database:
  - SQLite (default dev)
  - Or MySQL/PostgreSQL (with appropriate drivers)
- **OpenAI API key** (for the AI assistant)

---

## 🚀 Installation & Setup

1. **Clone the repo**

```bash
git clone https://github.com/Arif-Shafwan/money-manager.git
cd money-manager
