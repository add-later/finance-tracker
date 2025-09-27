import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
import plotly.graph_objects as go
import os
import json
from dotenv import load_dotenv

# ---------------- Config & Setup ----------------
st.set_page_config(page_title="📊 Аналитика финансов", layout="wide")

try:
    SHEET_URL = st.secrets["SHEET_URL"]
    credentials = json.loads(st.secrets["CREDENTIALS"])
    column_list = json.loads(st.secrets["COLUMN_LIST"])
except Exception:
    load_dotenv("../.env")
    SHEET_URL = os.environ["SHEET_URL"]
    credentials = json.loads(os.environ["CREDENTIALS"])
    column_list = json.loads(os.environ["COLUMN_LIST"])

# ---------------- Google Sheets ----------------
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials, scope)
client = gspread.authorize(creds)
sheet = client.open_by_url(SHEET_URL).sheet1

# ---------------- Data Loader ----------------
@st.cache_data(ttl=600)
def load_data():
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    if "date" not in df.columns:
        st.error("В таблице отсутствует колонка 'date'")
        return pd.DataFrame()

    df["date"] = pd.to_datetime(df["date"])
    return df

df = load_data()

st.title("📊 Аналитика финансов")

if df.empty:
    st.warning("Нет данных для отображения")
    st.stop()

# ---------------- Cashflow per Shop ----------------
def calc_cash(df, shop):
    """Расчет налички и кассы для заданного магазина"""
    shop_df = df[["date"] + [c for c in df.columns if f"Доходы-{shop}" in c or "Расходы" in c]].copy()
    shop_df = shop_df.sort_values("date").reset_index(drop=True)

    def safe_sum(subdf):
        return subdf.apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)

    shop_df["Выручка"] = safe_sum(shop_df.filter(like=f"Доходы-{shop}-Выручка"))
    shop_df["Терминалы"] = safe_sum(shop_df.filter(like=f"Доходы-{shop}-Терминал"))
    shop_df["Перевод на Gold"] = safe_sum(shop_df.filter(like=f"Доходы-{shop}-Перевод на Gold"))
    shop_df["Расходы"] = safe_sum(shop_df.filter(like=f"Расходы-{shop}"))
    shop_df["Наличка"] = 0.0
    shop_df["В кассе"] = 0.0

    for i in range(len(shop_df)):
        dt = {"ЦУМ": 214628, "Галерея": 252181}
        prev_cash = shop_df.loc[i - 1, "В кассе"] if i > 0 else dt[shop]
        shop_df.loc[i, "Наличка"] = (
            prev_cash
            + shop_df.loc[i, "Выручка"]
            - shop_df.loc[i, "Терминалы"]
            - shop_df.loc[i, "Перевод на Gold"]
        )
        shop_df.loc[i, "В кассе"] = shop_df.loc[i, "Наличка"] - shop_df.loc[i, "Расходы"]
    return shop_df[["date", "Наличка", "В кассе"]]

cash_cum = calc_cash(df, "ЦУМ")
cash_gal = calc_cash(df, "Галерея")

# ---------------- Metrics by Shop ----------------
latest_date = df["date"].max()
val_cum = cash_cum[cash_cum["date"] == latest_date].iloc[0]
val_gal = cash_gal[cash_gal["date"] == latest_date].iloc[0]

col1, col2 = st.columns(2)

with col1:
    st.subheader("ЦУМ")
    if "Факт-ЦУМ" in df.columns and val_cum["В кассе"] < df[df["date"] == latest_date]["Факт-ЦУМ"].iloc[0]:
        st.error(f"В кассе: {val_gal['В кассе']:.0f} Факт: {df[df["date"] == latest_date]["Факт-ЦУМ"].iloc[0]}")
    else:
        st.success(f"В кассе: {val_cum['В кассе']:.0f}")
    st.metric("Наличка", f"{val_cum['Наличка']:.0f}")

with col2:
    st.subheader("Галерея")
    if "Факт-Галерея" in df.columns and val_gal["В кассе"] < df[df["date"] == latest_date]["Факт-Галерея"].iloc[0]:
        st.error(f"В кассе: {val_gal['В кассе']:.0f} Факт: {df[df["date"] == latest_date]["Факт-Галерея"].iloc[0]}")
    else:
        st.success(f"В кассе: {val_gal['В кассе']:.0f}")
    st.metric("Наличка", f"{val_gal['Наличка']:.0f}")

st.write("---")

# ---------------- Cash Dynamics ----------------
st.subheader("Динамика кассы")
fig1 = go.Figure()
fig1.add_trace(go.Scatter(x=cash_cum["date"], y=cash_cum["В кассе"], mode="lines+markers", name="ЦУМ В кассе"))
fig1.add_trace(go.Scatter(x=cash_gal["date"], y=cash_gal["В кассе"], mode="lines+markers", name="Галерея В кассе"))
st.plotly_chart(fig1, use_container_width=True)

st.subheader("Наличка")
fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=cash_cum["date"], y=cash_cum["Наличка"], mode="lines+markers", name="ЦУМ Наличка"))
fig2.add_trace(go.Scatter(x=cash_gal["date"], y=cash_gal["Наличка"], mode="lines+markers", name="Галерея Наличка"))
st.plotly_chart(fig2, use_container_width=True)

st.write("---")

# ---------------- Доход ----------------
# ---------------- Percentage Dynamics ----------------
st.subheader("Доля дохода от выручки")

def calc_percentage(df, shop):
    col_income = f"Доходы-{shop}-Доход за день"
    col_revenue = f"Доходы-{shop}-Выручка"
    if col_income in df.columns and col_revenue in df.columns:
        temp = df[["date", col_income, col_revenue]].copy()
        temp["%"] = (pd.to_numeric(temp[col_income], errors="coerce") /
                     pd.to_numeric(temp[col_revenue], errors="coerce")) * 100
        return temp[["date", "%"]]
    return pd.DataFrame(columns=["date", "%"])

perc_cum = calc_percentage(df, "ЦУМ")
perc_gal = calc_percentage(df, "Галерея")

fig_perc = go.Figure()
if not perc_cum.empty:
    fig_perc.add_trace(go.Scatter(
        x=perc_cum["date"], y=perc_cum["%"],
        mode="lines+markers", name="ЦУМ %"
    ))
if not perc_gal.empty:
    fig_perc.add_trace(go.Scatter(
        x=perc_gal["date"], y=perc_gal["%"],
        mode="lines+markers", name="Галерея %"
    ))

fig_perc.update_layout(yaxis_title="%", xaxis_title="Дата")
st.plotly_chart(fig_perc, use_container_width=True)



# ---------------- Period Analysis ----------------
period = st.selectbox("Период анализа", ["День", "Неделя", "Месяц", "Квартал", "Год"])

if period == "День":
    df_grouped = df.groupby(df["date"].dt.date).sum(numeric_only=True)
elif period == "Неделя":
    df_grouped = df.groupby(df["date"].dt.to_period("W")).sum(numeric_only=True)
elif period == "Месяц":
    df_grouped = df.groupby(df["date"].dt.to_period("M")).sum(numeric_only=True)
elif period == "Квартал":
    df_grouped = df.groupby(df["date"].dt.to_period("Q")).sum(numeric_only=True)
elif period == "Год":
    df_grouped = df.groupby(df["date"].dt.to_period("Y")).sum(numeric_only=True)

df_grouped.index = df_grouped.index.astype(str)

# Available numeric columns after grouping
available_cols = df_grouped.columns.tolist()

income_cols = [c for c in df.columns if c.startswith("Доходы")]
expense_cols = [c for c in df.columns if c.startswith("Расходы")]

# Only keep existing ones
income_cols = [c for c in income_cols if c in available_cols]
expense_cols = [c for c in expense_cols if c in available_cols]

# Compute totals safely
total_income = df_grouped[income_cols].sum(axis=1) if income_cols else pd.Series(0, index=df_grouped.index)
total_expense = df_grouped[expense_cols].sum(axis=1) if expense_cols else pd.Series(0, index=df_grouped.index)
balance = total_income - total_expense


total_income = df_grouped[income_cols].sum(axis=1)
total_expense = df_grouped[expense_cols].sum(axis=1)
balance = total_income - total_expense

c1, c2, c3 = st.columns(3)
c1.metric("💰 Доходы (всего)", f"{total_income.sum():,.0f}")
c2.metric("💸 Расходы (всего)", f"{total_expense.sum():,.0f}")
c3.metric("📌 Баланс", f"{balance.sum():,.0f}")

st.write("---")

st.subheader("Структура доходов и расходов")

def aggregate_by_category(cols, df):
    """Group columns by the 2nd part of their name (after '-')"""
    category_totals = {}
    for col in cols:
        parts = col.split("-")
        if len(parts) >= 2:
            cat = parts[1]  # take the second token
            category_totals[cat] = category_totals.get(cat, 0) + df[col].sum()
    return category_totals

# --- Income pie by category ---
col1, col2 = st.columns(2)

with col1:
    income_cats = aggregate_by_category(income_cols, df)
    fig_income = px.pie(values=list(income_cats.values()), names=list(income_cats.keys()), 
                        title="Доходы по категориям")
    st.plotly_chart(fig_income, use_container_width=True)

    # Optional drilldown
    selected_income_cat = st.selectbox("Показать детали доходов", ["Нет"] + list(income_cats.keys()))
    if selected_income_cat != "Нет":
        subcols = [c for c in income_cols if c.split("-")[1] == selected_income_cat]
        if subcols:
            subdata = df[subcols].sum()
            fig_sub_income = px.pie(values=subdata.values, names=subdata.index, 
                                    title=f"Доходы: {selected_income_cat} по подкатегориям")
            st.plotly_chart(fig_sub_income, use_container_width=True)

with col2:
    expense_cats = aggregate_by_category(expense_cols, df)
    fig_expense = px.pie(values=list(expense_cats.values()), names=list(expense_cats.keys()), 
                         title="Расходы по категориям")
    st.plotly_chart(fig_expense, use_container_width=True)

    # Optional drilldown
    selected_expense_cat = st.selectbox("Показать детали расходов", ["Нет"] + list(expense_cats.keys()))
    if selected_expense_cat != "Нет":
        subcols = [c for c in expense_cols if c.split("-")[1] == selected_expense_cat]
        if subcols:
            subdata = df[subcols].sum()
            fig_sub_expense = px.pie(values=subdata.values, names=subdata.index, 
                                     title=f"Расходы: {selected_expense_cat} по подкатегориям")
            st.plotly_chart(fig_sub_expense, use_container_width=True)

# --- Balance trend ---
st.subheader("Баланс во времени")
fig_balance = px.line(x=df_grouped.index, y=balance, title="Изменение баланса")
st.plotly_chart(fig_balance, use_container_width=True)


