import gspread
from google.oauth2.service_account import Credentials


# Google APIで使用する権限
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


if __name__ == "__main__":
    spreadsheet = get_spreadsheet()

    print("接続成功")
    print("スプレッドシート名:", spreadsheet.title)

    users_sheet = spreadsheet.worksheet("users")

    print("usersシート接続成功")