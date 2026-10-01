import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_spreadsheet():
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