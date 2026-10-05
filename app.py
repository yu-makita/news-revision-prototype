import streamlit as st


# ==========================================
# ページ設定
# ==========================================
st.set_page_config(
    page_title="ニュース推薦・分身AI",
    page_icon="📰",
    layout="wide",
)

# Streamlit Cloudでapp.pyが起動しているか確認する
st.write("起動確認")


from pages.login_page import show_login_page
from pages.register_page import show_register_page
from pages.home_page import show_home_page
from pages.edit_profile_page import show_edit_profile_page

# ==========================================
# アプリ全体のアクセントカラー
# ==========================================
st.markdown(
    """
    <style>
    :root {
        --primary-color: #1f77d0;
    }

    /* 入力中のフォーム枠 */
    div[data-baseweb="input"]:focus-within,
    div[data-baseweb="select"]:focus-within {
        border-color: #1f77d0 !important;
        box-shadow: 0 0 0 1px #1f77d0 !important;
    }

    /* multiselectで選択した項目 */
    span[data-baseweb="tag"] {
        background-color: #1f77d0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ==========================================
# session_state 初期設定
# ==========================================
if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "register_mode" not in st.session_state:
    st.session_state.register_mode = False

if "edit_profile" not in st.session_state:
    st.session_state.edit_profile = False

if "recommendation_result" not in st.session_state:
    st.session_state.recommendation_result = None


# ==========================================
# アプリタイトル
# ==========================================
st.title("ニュース推薦・分身AI")

st.write(
    "ユーザー情報をもとに、興味を持ちそうなニュースを推薦します。"
)


# ==========================================
# 画面切り替え
# ==========================================

# 未ログイン
if st.session_state.user_id is None:

    # 新規登録画面
    if st.session_state.register_mode:
        show_register_page()

    # ログイン画面
    else:
        show_login_page()


# ログイン済み
else:

    # 登録情報変更画面
    if st.session_state.edit_profile:
        show_edit_profile_page()

    # ホーム画面
    else:
        show_home_page()