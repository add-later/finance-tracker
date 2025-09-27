import streamlit as st
import json
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
import os


try:
    SHEET_URL = st.secrets["SHEET_URL"]
    data = json.loads(st.secrets["COLUMN_LIST"])
    data = json.loads(st.secrets["COLUMN_LIST"])
    credentials=json.loads(st.secrets["CREDENTIALS"])
except:
    load_dotenv('.env')
    SHEET_URL = os.environ["SHEET_URL"]
    data = json.loads(os.environ["COLUMN_LIST"])
    credentials=json.loads(os.environ["CREDENTIALS"])


scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials, scope)
client = gspread.authorize(creds)


sheet = client.open_by_url(SHEET_URL).sheet1


st.title("Финансовый трекер 📝")

# Date field
today = datetime.date.today()
selected_date = st.date_input("Дата", value=today)
st.write("---")

# Store user inputs in a dictionary
inputs = {}

# ---------------- Доходы ----------------
st.header("Доходы 💰💰💰")
income_tabs = st.tabs(list(data["Доходы"].keys()))

for i, subpage in enumerate(data["Доходы"].keys()):
    with income_tabs[i]:
        st.subheader(subpage)
        for field in data["Доходы"][subpage]:
            value = st.number_input(f"{subpage} → {field}", min_value=0.0, step=100.0, value=None,
                                    key=f"income_{subpage}_{field}")
            inputs[f"Доходы-{subpage}-{field}"] = value
        value = st.number_input(f"Факт → {subpage}", min_value=0.0, step=100.0, value=None,
                                    key=f"income_факт_{subpage}")
        inputs[f"Факт-{subpage}"] = value

# ---------------- Расходы ----------------
st.header("Расходы 💸💸💸")

# Split categories and subcategories
categories = {}
for item in data["Расходы"]:
    category, subcategory = item.split("_", 1)
    if category not in categories:
        categories[category] = []
    categories[category].append(subcategory)

expense_tabs = st.tabs(list(categories.keys()))

for i, category in enumerate(categories.keys()):
    with expense_tabs[i]:
        st.subheader(category)
        for subcat in categories[category]:
            value = st.number_input(f"{category} → {subcat}", min_value=0.0, step=100.0, value=None,
                                    key=f"expense_{category}_{subcat}")
            inputs[f"Расходы-{category}-{subcat}"] = value

st.write("---")

# ---------------- Save to Google Sheets ----------------
if st.button("Сохранить в Google Sheets", ):
    row_data = {"date": str(selected_date)}
    row_data.update(inputs)

    # Ensure headers exist
    existing_headers = sheet.row_values(1)
    new_headers = list(row_data.keys())

    if existing_headers != new_headers:
        sheet.resize(1)  # reset
        sheet.insert_row(new_headers, 1)

    # Append data
    sheet.append_row(list(row_data.values()))
    st.success("Данные успешно сохранены в Google Sheets!")
