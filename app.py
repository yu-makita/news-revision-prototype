import streamlit as st
from news_recommender import recommend_news, RecommendationError
from database import (
    save_user,
    user_exists,
    generate_user_id,
    get_user,
    update_user,
)
from user_form import (
    show_user_registration_form,
    show_user_edit_form,
)

st.set_page_config(
    page_title="ニュース推薦・分身AI",
    page_icon="📰",
    layout="wide",
)

# アプリ全体のアクセントカラーを青に変更
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

st.title("ニュース推薦・分身AI")
st.write("ユーザー情報をもとに、興味を持ちそうなニュースを推薦します。")


# ログイン状態の初期設定
if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "register_mode" not in st.session_state:
    st.session_state.register_mode = False

if "edit_profile" not in st.session_state:
    st.session_state.edit_profile = False


# -------------------------
# 未ログイン時
# -------------------------
if st.session_state.user_id is None:

    # 新規登録モードではない場合 → ログイン画面
    if not st.session_state.register_mode:

        st.subheader("ログイン")

        login_user_id = st.text_input(
            "参加者ID",
            placeholder="例：P0001",
        ).strip().upper()

        if st.button("ログイン"):

            if not login_user_id:
                st.error("参加者IDを入力してください。")

            elif user_exists(login_user_id):
                st.session_state.user_id = login_user_id
                st.rerun()

            else:
                st.error("参加者IDが見つかりません。")

        st.write("初めて利用する方")

        if st.button("新規登録"):
            st.session_state.register_mode = True
            st.rerun()

    # 新規登録モードの場合
    else:

        if st.button(
            "← ログイン画面に戻る",
            key="back_to_login_from_register"
        ):
            st.session_state.register_mode = False
            st.rerun()

        user_profile = show_user_registration_form()

        st.write("")

        left, center, right = st.columns([2, 1, 2])

        with center:
            if st.button(
                "登録する",
                type="primary",
                use_container_width=True,
            ):
                new_user_id = generate_user_id()

                save_user(
                    new_user_id,
                    user_profile,
                )

                st.session_state.user_id = new_user_id
                st.session_state.register_mode = False

                st.success(
                    f"登録が完了しました。あなたの参加者IDは「{new_user_id}」です。"
                )

                st.info(
                    "次回利用時に必要になるため、この参加者IDを控えてください。"
                )


# 推薦結果を保存するための初期設定
if "recommendation_result" not in st.session_state:
    st.session_state.recommendation_result = None


# ログイン済みの場合だけ表示
if st.session_state.user_id is not None:

    # DBから現在のユーザー情報を取得
    current_user = get_user(st.session_state.user_id)

    if current_user is None:
        st.error("ユーザー情報を取得できませんでした。")
        st.stop()


    # ==========================================
    # 登録情報の変更画面
    # ==========================================
    if st.session_state.edit_profile:

        # 左上に戻るボタン
        if st.button(
            "← ログイン画面に戻る",
            key="back_to_login_from_user"
        ):
            st.session_state.user_id = None
            st.session_state.edit_profile = False
            st.session_state.recommendation_result = None
            st.rerun()

        edited_profile = show_user_edit_form(current_user)

        # 保存ボタンを中央に配置
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
                    st.session_state.edit_profile = False
                    st.session_state.recommendation_result = None
                    st.rerun()

                else:
                    st.error("登録情報を変更できませんでした。")


    # ==========================================
    # 通常のログイン後画面
    # ==========================================
    else:

        # 左上にログイン画面へ戻るボタン
        if st.button("← ログイン画面に戻る"):
            st.session_state.user_id = None
            st.session_state.edit_profile = False
            st.session_state.recommendation_result = None
            st.rerun()

        st.subheader("ユーザー情報")

        st.write(
            f"参加者ID：{st.session_state.user_id}"
        )

        # 興味のある分野
        interests = current_user.get("interests", [])

        if interests:
            st.write(
                f"興味のある分野：{', '.join(interests)}"
            )
        else:
            st.write(
                "興味のある分野：未登録"
            )

        # Big Five
        st.write("**Big Five**")

        big5 = current_user.get("big5", {})

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.metric(
                "外向性",
                big5.get("extraversion", "-"),
            )

        with col2:
            st.metric(
                "協調性",
                big5.get("agreeableness", "-"),
            )

        with col3:
            st.metric(
                "勤勉性",
                big5.get("conscientiousness", "-"),
            )

        with col4:
            st.metric(
                "情動性",
                big5.get("emotionality", "-"),
            )

        with col5:
            st.metric(
                "創造性",
                big5.get("creativity", "-"),
            )

        # 登録情報変更
        if st.button("登録情報を変更"):
            st.session_state.edit_profile = True
            st.rerun()

        st.divider()

        # ==========================================
        # ニュース推薦
        # ==========================================
        if st.button(
            "ニュースを取得・推薦する",
            type="primary",
        ):

            user_profile = current_user

            try:
                with st.spinner(
                    "ニュースを取得して、あなたに合いそうな記事を選んでいます..."
                ):
                    result = recommend_news(
                        user_profile=user_profile
                    )

                st.session_state.recommendation_result = result

                st.success(
                    "推薦が完了しました。"
                )

            except RecommendationError as e:
                st.error(
                    f"推薦処理でエラーが発生しました：{e}"
                )

            except Exception as e:
                st.error(
                    f"予期せぬエラーが発生しました：{e}"
                )



# 保存されている推薦結果を取得
result = st.session_state.recommendation_result

if result is not None:

    recommended = result["recommended_news"]

    st.subheader("あなたへのおすすめ")

    title = recommended.get("title")
    url = recommended.get("url")

    st.markdown(
        f"""
        <div style="
            font-size: 21px;
            font-weight: 700;
            line-height: 1.5;
            margin-bottom: 14px;
        ">
            <a href="{url}" target="_blank" style="
                color: inherit;
                text-decoration: none;
            ">
                「{title}」
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write(f"カテゴリ：{recommended.get('category')}")

    if recommended.get("source"):
        st.write(f"配信元：{recommended.get('source')}")

    st.write("**推薦理由**")
    st.write(result["recommendation_reason"])

    st.write("**記事の要約**")
    st.write(result["article_summary"])

    st.divider()

    st.subheader("他にはこんなニュースがありました")

    other_news = result["other_news"]

    for row_start in range(0, len(other_news), 3):

        cols = st.columns(3)

        for col_index, news in enumerate(
            other_news[row_start:row_start + 3]
        ):

            index = row_start + col_index + 1

            with cols[col_index]:

                with st.container(border=True):

                    st.caption(
                        news.get("category") or "カテゴリ不明"
                    )

                    title = news.get("title")
                    url = news.get("url")

                    st.markdown(
                        f"""
                        <div style="
                            font-size: 18px;
                            font-weight: 700;
                            line-height: 1.5;
                            margin-bottom: 12px;
                        ">
                            <a href="{url}" target="_blank" style="
                                color: inherit;
                                text-decoration: none;
                            ">
                                {index}. 「{title}」
                            </a>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    summary = news.get("summary")

                    if summary:
                        st.write(summary)
                    else:
                        st.caption(
                            "概要を取得できませんでした。"
                        )

    st.divider()

    st.subheader("最も興味を持ったニュースを選んでください")
    st.write(
        "上の10件のニュースの中から、あなたが実際に最も興味を持ったニュースを1つ選んでください。"
    )

    # おすすめ1件 + その他9件をまとめる
    all_news = [recommended] + other_news

    selected_news_id = st.radio(
        "ニュースを選択",
        options=[news["news_id"] for news in all_news],
        format_func=lambda news_id: next(
            f"「{news['title']}」"
            for news in all_news
            if news["news_id"] == news_id
        ),
        index=None,
    )

    if selected_news_id is not None:
        selected_news = next(
            news
            for news in all_news
            if news["news_id"] == selected_news_id
        )

        st.success(
            f"選択したニュース：『{selected_news['title']}』"
        )