import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
import datetime
import os
from dotenv import load_dotenv
import json


try:
    SHEET_URL = st.secrets["SHEET_URL"]
    data = json.loads(st.secrets["COLUMN_LIST"])
    data = json.loads(st.secrets["COLUMN_LIST"])
    credentials=json.loads(st.secrets["CREDENTIALS"])
except:
    load_dotenv('../.env')
    SHEET_URL = os.environ["SHEET_URL"]
    data = json.loads(os.environ["COLUMN_LIST"])
    credentials=json.loads(os.environ["CREDENTIALS"])


# ---------------- Google Sheets Setup ----------------
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials, scope)
client = gspread.authorize(creds)

sheet = client.open_by_url(SHEET_URL).sheet1

# ---------------- Load Data ----------------
@st.cache_data
def load_data():
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    return df

df = load_data()

st.title("📊 Аналитика финансов")

# ---------------- Time Filter ----------------
period = st.selectbox(
    "Выберите период",
    ["День", "Неделя", "Месяц", "Квартал", "Год", "Все время"]
)

today = datetime.date.today()

if period == "День":
    df_period = df[df["date"].dt.date == today]
elif period == "Неделя":
    week_start = today - datetime.timedelta(days=today.weekday())
    df_period = df[(df["date"].dt.date >= week_start) & (df["date"].dt.date <= today)]
elif period == "Месяц":
    df_period = df[(df["date"].dt.month == today.month) & (df["date"].dt.year == today.year)]
elif period == "Квартал":
    df_period = df[(df["date"].dt.to_period("Q") == pd.Period(today, freq="Q"))]
elif period == "Год":
    df_period = df[df["date"].dt.year == today.year]
else:
    df_period = df

if df_period.empty:
    st.warning("Нет данных за выбранный период.")
    st.stop()

# ---------------- Income / Expenses Aggregation ----------------
income_cols = [col for col in df.columns if col.startswith("Доходы")]
expense_cols = [col for col in df.columns if col.startswith("Расходы")]

df_period["Доходы"] = df_period[income_cols].sum(axis=1)
df_period["Расходы"] = df_period[expense_cols].sum(axis=1)

total_income = df_period["Доходы"].sum()
total_expenses = df_period["Расходы"].sum()
balance = total_income - total_expenses

col1, col2, col3 = st.columns(3)
col1.metric("💰 Текущий баланс", f"{balance:,.0f} ₸")
col2.metric("📈 Доходы", f"{total_income:,.0f} ₸")
col3.metric("📉 Расходы", f"{total_expenses:,.0f} ₸")

st.write("---")

# ---------------- Expenses Distribution ----------------
expenses_long = df_period.melt(
    id_vars=["date"], value_vars=expense_cols,
    var_name="Категория", value_name="Сумма"
)
expenses_long = expenses_long[expenses_long["Сумма"] > 0]

if not expenses_long.empty:
    expenses_long[["Тип", "Категория", "Подкатегория"]] = expenses_long["Категория"].str.split("-", 2, expand=True)

    category_summary = expenses_long.groupby("Категория")["Сумма"].sum().reset_index()
    fig_cat = px.pie(category_summary, names="Категория", values="Сумма", title="📊 Расходы по категориям")
    st.plotly_chart(fig_cat, use_container_width=True)

    selected_category = st.selectbox("Выберите категорию для детализации", category_summary["Категория"].unique())
    subcat_summary = expenses_long[expenses_long["Категория"] == selected_category]
    subcat_summary = subcat_summary.groupby("Подкатегория")["Сумма"].sum().reset_index()

    fig_subcat = px.bar(subcat_summary, x="Подкатегория", y="Сумма", title=f"📂 Подкатегории: {selected_category}")
    st.plotly_chart(fig_subcat, use_container_width=True)
else:
    st.info("Нет расходов за выбранный период.")

# ---------------- Income Distribution (Выручка ЦУМ / Галерея) ----------------
income_long = df_period.melt(
    id_vars=["date"], value_vars=income_cols,
    var_name="Категория", value_name="Сумма"
)
income_long = income_long[income_long["Сумма"] > 0]
income_long[["Тип", "Магазин", "Подкатегория"]] = (
    income_long["Категория"].str.split("-", n=2, expand=True)
)


# Filter only "Выручка"
income_vyruchka = income_long[income_long["Подкатегория"] == "Выручка"]
if not income_vyruchka.empty:
    vyruchka_summary = income_vyruchka.groupby("Магазин")["Сумма"].sum().reset_index()
    fig_income_pie = px.pie(vyruchka_summary, names="Магазин", values="Сумма", title="🏪 Доходы (Выручка: ЦУМ vs Галерея)")
    st.plotly_chart(fig_income_pie, use_container_width=True)

st.write("---")

# ---------------- Income Trend ----------------
income_trend = df_period.groupby("date")[income_cols].sum().sum(axis=1).reset_index(name="Доходы")
if not income_trend.empty:
    fig_income = px.line(income_trend, x="date", y="Доходы", title="📈 Динамика доходов")
    st.plotly_chart(fig_income, use_container_width=True)

# ---------------- Expenses Trend ----------------
expense_trend = df_period.groupby("date")[expense_cols].sum().sum(axis=1).reset_index(name="Расходы")
if not expense_trend.empty:
    fig_expense = px.line(expense_trend, x="date", y="Расходы", title="📉 Динамика расходов")
    st.plotly_chart(fig_expense, use_container_width=True)

# ---------------- Cumulative Balance Trend ----------------
balance_trend = (
    df_period.groupby("date")[income_cols + expense_cols]
    .sum()
    .reset_index()
)
balance_trend["Доходы"] = balance_trend[income_cols].sum(axis=1)
balance_trend["Расходы"] = balance_trend[expense_cols].sum(axis=1)
balance_trend["Баланс"] = (balance_trend["Доходы"] - balance_trend["Расходы"]).cumsum()

fig_balance = px.line(
    balance_trend, x="date", y="Баланс", title="💹 Кумулятивный баланс"
)
st.plotly_chart(fig_balance, use_container_width=True)
