import streamlit as st

from database import get_user, update_user
from user_form import show_user_edit_form


def show_edit_profile_page():

    # 現在のユーザー情報を取得
    current_user = get_user(
        st.session_state.user_id
    )

    if current_user is None:
        st.error(
            "ユーザー情報を取得できませんでした。"
        )
        st.stop()


    # ==========================================
    # ユーザー情報画面に戻る
    # ==========================================
    if st.button(
        "← ユーザー情報に戻る",
        key="back_to_home_from_edit",
    ):
        st.session_state.edit_profile = False
        st.rerun()


    # ==========================================
    # 編集フォーム
    # ==========================================
    edited_profile = show_user_edit_form(
        current_user
    )

    st.write("")


    # ==========================================
    # 保存ボタン
    # ==========================================
    left, center, right = st.columns([2, 1, 2])

    with center:

        if st.button(
            "変更を保存",
            type="primary",
            use_container_width=True,
        ):

            success = update_user(
                st.session_state.user_id,
                edited_profile,
            )

            if success:

                # プロフィール変更前の推薦結果は消す
                st.session_state.recommendation_result = None

                # 編集モード終了
                st.session_state.edit_profile = False

                # 保存完了メッセージ用
                st.session_state.profile_updated = True

                st.rerun()

            else:
                st.error(
                    "登録情報を変更できませんでした。"
                )