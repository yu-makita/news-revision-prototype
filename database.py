import gspread
import json
import uuid
import streamlit as st
import os
from google.oauth2.service_account import Credentials
from datetime import datetime


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Googleスプレッドシートへの接続を再利用する関数
@st.cache_resource
def get_spreadsheet():

    # ローカルに認証ファイルがある場合はそれを使う
    if os.path.exists("google_credentials.json"):
        credentials = Credentials.from_service_account_file(
            "google_credentials.json",
            scopes=SCOPES,
        )

    # Streamlit CloudではSecretsを使う
    else:
        credentials = Credentials.from_service_account_info(
            dict(st.secrets["google_service_account"]),
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

# ユーザーが過去に実際に選択したニュースを取得する関数
def get_selected_news_history(user_id):
    spreadsheet = get_spreadsheet()

    sessions_sheet = spreadsheet.worksheet("sessions")
    news_history_sheet = spreadsheet.worksheet("news_history")

    # sessionsシートから、このユーザーが実際に選択したnews_idを取得する
    session_records = sessions_sheet.get_all_records()

    selected_records = []

    for record in session_records:

        saved_user_id = str(
            record.get("user_id", "")
        ).strip().upper()

        if saved_user_id != user_id.strip().upper():
            continue

        # 「興味を持ったニュースはない」を選んだ回は除外する
        none_selected = str(
            record.get("none_selected", "")
        ).strip().upper()

        if none_selected == "TRUE":
            continue

        selected_news_id = str(
            record.get("selected_news_id", "")
        ).strip()

        if not selected_news_id:
            continue

        selected_records.append({
            "news_id": selected_news_id,
            "selected_at": record.get("created_at"),
            "session_id": record.get("session_id"),
        })

    # news_historyシートから記事情報を取得する
    news_records = news_history_sheet.get_all_records()

    news_by_id = {}

    for record in news_records:

        news_id = str(
            record.get("news_id", "")
        ).strip()

        if news_id:
            news_by_id[news_id] = record

    # 選択履歴と記事情報を結合する
    history = []

    for selected in selected_records:

        news = news_by_id.get(
            selected["news_id"],
            {},
        )

        history.append({
            "news_id": selected["news_id"],
            "selected_at": selected["selected_at"],
            "session_id": selected["session_id"],
            "title": news.get("title"),
            "category": news.get("category"),
            "source": news.get("source"),
            "url": news.get("url"),
        })

    return history

# ユーザーの意見選択・訂正履歴をGoogle Sheetsに保存する関数
def save_correction(
    session_id,
    user_id,
    news_id,
    opinion_candidates,
    selected_opinion_id,
    selected_opinion_text,
    correction_text,
):
    spreadsheet = get_spreadsheet()
    sheet = spreadsheet.worksheet("corrections")

    # 回答ごとに一意なIDを生成する
    correction_id = str(uuid.uuid4())

    # 回答日時を取得する
    created_at = datetime.now().isoformat(
        timespec="seconds"
    )

    # 意見候補をJSON文字列に変換する
    opinion_candidates_json = json.dumps(
        opinion_candidates,
        ensure_ascii=False,
    )

    # 選択結果に応じて保存先の列を分ける
    if selected_opinion_id == "none":
        user_selected_index = ""
        user_selected_opinion = ""
        user_free_opinion = correction_text
        correction_reason = ""
    else:
        user_selected_index = selected_opinion_id
        user_selected_opinion = selected_opinion_text
        user_free_opinion = ""
        correction_reason = correction_text

    row = [
        correction_id,             # A
        user_id,                   # B
        session_id,                # C
        news_id,                   # D
        created_at,                # E
        "",                        # F: ai_statement
        opinion_candidates_json,   # G
        "",                        # H: ai_predicted_index
        "",                        # I: ai_predicted_opinion
        "",                        # J: ai_styled_statement
        user_selected_index,       # K
        user_selected_opinion,     # L
        user_free_opinion,         # M
        correction_reason,         # N
        "",                        # O: user_own_expression
    ]

    # Google Sheetsに1行追加する
    sheet.append_row(
        row,
        value_input_option="RAW",
    )

    return correction_id