import streamlit as st

from database import save_user, generate_user_id
from user_form import show_user_registration_form


def show_register_page():

    # 左上の戻るボタン
    if st.button(
        "← ログイン画面に戻る",
        key="back_to_login_from_register",
    ):
        st.session_state.register_mode = False
        st.rerun()

    # 新規登録フォーム
    user_profile = show_user_registration_form()

    st.write("")

    # 登録ボタンを中央に配置
    left, center, right = st.columns([2, 1, 2])

    with center:
        if st.button(
            "登録する",
            type="primary",
            use_container_width=True,
        ):
            # 新しい参加者IDを発行
            new_user_id = generate_user_id()

            # Googleスプレッドシートに保存
            save_user(
                new_user_id,
                user_profile,
            )

            # ログイン状態にする
            st.session_state.user_id = new_user_id
            st.session_state.register_mode = False
            st.session_state.edit_profile = False

            # 登録完了画面を表示するために保存
            st.session_state.new_user_id = new_user_id

            st.rerun()