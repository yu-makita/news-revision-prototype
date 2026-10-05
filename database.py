import gspread
import uuid
import streamlit as st
from google.oauth2.service_account import Credentials
from datetime import datetime


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Googleスプレッドシートへの接続を再利用する関数
@st.cache_resource
def get_spreadsheet():

    # Streamlit CloudではSecretsに保存した認証情報を使う
    if "google_service_account" in st.secrets:
        credentials = Credentials.from_service_account_info(
            dict(st.secrets["google_service_account"]),
            scopes=SCOPES,
        )

    # ローカルでは今まで通りJSONファイルを使う
    else:
        credentials = Credentials.from_service_account_file(
            "google_credentials.json",
            scopes=SCOPES,
        )

    client = gspread.authorize(credentials)

    spreadsheet = client.open("news_revision_database")

    return spreadsheet


def save_user(user_id, user_profile):
    spreadsheet = get_spreadsheet()
    sheet = spreadsheet.worksheet("users")

    big5 = user_profile.get("big5", {})

    row = [
        user_id,
        datetime.now().isoformat(timespec="seconds"),
        user_profile.get("age"),
        user_profile.get("gender"),
        user_profile.get("occupation"),
        user_profile.get("prefecture"),
        ",".join(user_profile.get("interests", [])),
        big5.get("extraversion"),
        big5.get("agreeableness"),
        big5.get("conscientiousness"),
        big5.get("emotionality"),
        big5.get("creativity"),
    ]

    sheet.append_row(row)

    return user_id

def user_exists(user_id):
    spreadsheet = get_spreadsheet()
    sheet = spreadsheet.worksheet("users")

    user_ids = sheet.col_values(1)

    # 1行目は "user_id" という見出し
    return user_id in user_ids[1:]

def generate_user_id():
    spreadsheet = get_spreadsheet()
    sheet = spreadsheet.worksheet("users")

    # usersシートのA列（user_id）を取得
    user_ids = sheet.col_values(1)[1:]

    numbers = []

    for user_id in user_ids:
        user_id = str(user_id).strip().upper()

        if user_id.startswith("P") and user_id[1:].isdigit():
            numbers.append(int(user_id[1:]))

    # 登録者がまだいなければP0001から開始
    if not numbers:
        next_number = 1
    else:
        next_number = max(numbers) + 1

    return f"P{next_number:04d}"

def get_user(user_id):
    spreadsheet = get_spreadsheet()
    sheet = spreadsheet.worksheet("users")

    records = sheet.get_all_records()

    for record in records:
        if str(record["user_id"]).strip().upper() == user_id.strip().upper():

            interests = record.get("interests", "")

            if isinstance(interests, str):
                interests = [
                    item.strip()
                    for item in interests.split(",")
                    if item.strip()
                ]

            return {
                "age": record.get("age"),
                "gender": record.get("gender"),
                "occupation": record.get("occupation"),
                "prefecture": record.get("prefecture"),
                "interests": interests,
                "big5": {
                    "extraversion": record.get("extraversion"),
                    "agreeableness": record.get("agreeableness"),
                    "conscientiousness": record.get("conscientiousness"),
                    "emotionality": record.get("emotionality"),
                    "creativity": record.get("creativity"),
                },
            }

    return None


def update_user(user_id, user_profile):
    spreadsheet = get_spreadsheet()
    sheet = spreadsheet.worksheet("users")

    user_ids = sheet.col_values(1)

    target_row = None

    for row_number, saved_user_id in enumerate(user_ids[1:], start=2):
        if str(saved_user_id).strip().upper() == user_id.strip().upper():
            target_row = row_number
            break

    if target_row is None:
        return False

    big5 = user_profile.get("big5", {})

    # created_at と user_id は変更しない
    values = [
        user_profile.get("age"),
        user_profile.get("gender"),
        user_profile.get("occupation"),
        user_profile.get("prefecture"),
        ",".join(user_profile.get("interests", [])),
        big5.get("extraversion"),
        big5.get("agreeableness"),
        big5.get("conscientiousness"),
        big5.get("emotionality"),
        big5.get("creativity"),
    ]

    # C列(age) ～ L列(creativity)を更新
    sheet.update(
        range_name=f"C{target_row}:L{target_row}",
        values=[values],
    )

    return True

# 1回の推薦で表示したニュース履歴を保存する関数
def save_news_history(
    user_id,
    news_list,
    session_id,
):
    spreadsheet = get_spreadsheet()
    sheet = spreadsheet.worksheet("news_history")

    # 9件すべてに同じ表示日時を記録する
    shown_at = datetime.now().isoformat(
        timespec="seconds"
    )

    rows = []

    for news in news_list:
        rows.append([
            user_id,                 # A: user_id
            news.get("news_id"),     # B: news_id
            shown_at,                # C: shown_at
            session_id,              # D: session_id
            news.get("title"),       # E: title
            news.get("category"),    # F: category
            news.get("source"),      # G: source
            news.get("url"),         # H: url
        ])

    if rows:
        sheet.append_rows(
            rows,
            value_input_option="RAW",
        )

# ユーザーが過去に見たニュースIDを取得する関数
def get_seen_news_ids(user_id):
    spreadsheet = get_spreadsheet()
    sheet = spreadsheet.worksheet("news_history")

    records = sheet.get_all_records()

    seen_news_ids = set()

    for record in records:
        if str(record.get("user_id")).strip().upper() == user_id.strip().upper():

            news_id = str(record.get("news_id")).strip()

            if news_id:
                seen_news_ids.add(news_id)

    return seen_news_ids

# 1回のニュース推薦を識別するセッションIDを生成する関数
def generate_session_id():
    return f"S-{uuid.uuid4().hex[:8].upper()}"

# 1回のニュース推薦に対するユーザーの選択結果を保存する関数
def save_session(
    session_id,
    user_id,
    recommended_news_id,
    selected_news_id,
    none_selected,
):
    spreadsheet = get_spreadsheet()
    sheet = spreadsheet.worksheet("sessions")

    # ユーザーが選択を確定した時刻を記録する
    created_at = datetime.now().isoformat(
        timespec="seconds"
    )

    row = [
        session_id,              # A: session_id
        user_id,                 # B: user_id
        created_at,              # C: created_at
        recommended_news_id,     # D: recommended_news_id
        selected_news_id,        # E: selected_news_id
        none_selected,           # F: none_selected
    ]

    sheet.append_row(
        row,
        value_input_option="RAW",
    )