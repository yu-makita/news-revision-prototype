import streamlit as st

from database import user_exists


def show_login_page():

    st.subheader("ログイン")

    login_user_id = st.text_input(
        "参加者ID",
        placeholder="例：P0001",
    ).strip().upper()

    if st.button(
        "ログイン",
        type="primary",
    ):
        if not login_user_id:
            st.error("参加者IDを入力してください。")

        elif user_exists(login_user_id):
            st.session_state.user_id = login_user_id
            st.session_state.register_mode = False
            st.session_state.edit_profile = False
            st.rerun()

        else:
            st.error("参加者IDが見つかりません。")

    st.write("初めて利用する方")

    if st.button("新規登録"):
        st.session_state.register_mode = True
        st.rerun()