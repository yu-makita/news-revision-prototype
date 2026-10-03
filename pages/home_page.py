import streamlit as st

from database import (
    get_user,
    get_seen_news_ids,
    save_news_history,
    generate_session_id,
)

from news_recommender import (
    recommend_news,
    RecommendationError,
)


# ==========================================
# ログイン後のホーム画面を表示する関数
# ==========================================
def show_home_page():

    # ==========================================
    # 現在のユーザー情報を取得
    # ==========================================
    current_user = get_user(
        st.session_state.user_id
    )

    if current_user is None:
        st.error(
            "ユーザー情報を取得できませんでした。"
        )
        st.stop()


    # ==========================================
    # 登録情報変更後のメッセージ
    # ==========================================
    if st.session_state.get(
        "profile_updated",
        False,
    ):
        st.success(
            "登録情報を変更しました。"
        )

        del st.session_state.profile_updated


    # ==========================================
    # 新規登録直後のメッセージ
    # ==========================================
    if "new_user_id" in st.session_state:

        new_user_id = (
            st.session_state.new_user_id
        )

        st.success(
            f"登録が完了しました。"
            f"あなたの参加者IDは「{new_user_id}」です。"
        )

        st.info(
            "次回利用時に必要になるため、"
            "この参加者IDを控えてください。"
        )

        del st.session_state.new_user_id


    # ==========================================
    # ログイン画面に戻る
    # ==========================================
    if st.button(
        "← ログイン画面に戻る",
        key="back_to_login_from_home",
    ):
        st.session_state.user_id = None
        st.session_state.edit_profile = False
        st.session_state.recommendation_result = None

        st.rerun()


    # ==========================================
    # ユーザー情報
    # ==========================================
    st.subheader(
        "ユーザー情報"
    )

    st.write(
        f"参加者ID：{st.session_state.user_id}"
    )

    interests = current_user.get(
        "interests",
        [],
    )

    if interests:
        st.write(
            f"興味のある分野：{', '.join(interests)}"
        )

    else:
        st.write(
            "興味のある分野：未登録"
        )


    # ==========================================
    # Big Five
    # ==========================================
    st.write(
        "**Big Five**"
    )

    big5 = current_user.get(
        "big5",
        {},
    )

    col1, col2, col3, col4, col5 = (
        st.columns(5)
    )

    with col1:
        st.metric(
            "外向性",
            big5.get(
                "extraversion",
                "-",
            ),
        )

    with col2:
        st.metric(
            "協調性",
            big5.get(
                "agreeableness",
                "-",
            ),
        )

    with col3:
        st.metric(
            "勤勉性",
            big5.get(
                "conscientiousness",
                "-",
            ),
        )

    with col4:
        st.metric(
            "情動性",
            big5.get(
                "emotionality",
                "-",
            ),
        )

    with col5:
        st.metric(
            "創造性",
            big5.get(
                "creativity",
                "-",
            ),
        )


    # ==========================================
    # 登録情報変更
    # ==========================================
    if st.button(
        "登録情報を変更"
    ):
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

        try:

            with st.spinner(
                "ニュースを取得して、"
                "あなたに合いそうな記事を選んでいます..."
            ):

                # このユーザーが過去に表示された
                # ニュースIDを取得
                seen_news_ids = (
                    get_seen_news_ids(
                        st.session_state.user_id
                    )
                )

                # 既出ニュースを除外して
                # ニュース推薦を実行
                result = recommend_news(
                    user_profile=current_user,
                    seen_news_ids=seen_news_ids,
                )

                # 今回ユーザーに表示する
                # ニュース10件をまとめる
                displayed_news = [
                    result[
                        "recommended_news"
                    ],
                    *result[
                        "other_news"
                    ],
                ]

                # 今回の推薦を識別するセッションIDを生成する
                session_id = generate_session_id()

                # 今回表示する9件をニュース履歴に保存する
                save_news_history(
                    st.session_state.user_id,
                    displayed_news,
                    session_id,
)

            # 推薦結果を画面表示用に保存
            st.session_state.recommendation_result = (
                result
            )

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


    # ==========================================
    # 保存されている推薦結果を取得
    # ==========================================
    result = (
        st.session_state.recommendation_result
    )

    # 推薦結果がまだなければ、
    # ここでホーム画面の描画を終了
    if result is None:
        return


    # ==========================================
    # 最推薦ニュース
    # ==========================================
    recommended = result[
        "recommended_news"
    ]

    st.subheader(
        "あなたへのおすすめ"
    )

    title = recommended.get(
        "title"
    )

    url = recommended.get(
        "url"
    )

    st.markdown(
        f"""
        <div style="
            font-size: 21px;
            font-weight: 700;
            line-height: 1.5;
            margin-bottom: 14px;
        ">
            <a
                href="{url}"
                target="_blank"
                style="
                    color: inherit;
                    text-decoration: none;
                "
            >
                「{title}」
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write(
        f"カテゴリ："
        f"{recommended.get('category')}"
    )

    if recommended.get(
        "source"
    ):
        st.write(
            f"配信元："
            f"{recommended.get('source')}"
        )

    st.write(
        "**推薦理由**"
    )

    st.write(
        result[
            "recommendation_reason"
        ]
    )

    st.write(
        "**記事の要約**"
    )

    st.write(
        result[
            "article_summary"
        ]
    )


    # ==========================================
    # その他のニュース
    # ==========================================
    st.divider()

    st.subheader(
        "他にはこんなニュースがありました"
    )

    other_news = result[
        "other_news"
    ]

    for row_start in range(
        0,
        len(other_news),
        3,
    ):

        cols = st.columns(3)

        for col_index, news in enumerate(
            other_news[
                row_start:row_start + 3
            ]
        ):

            index = (
                row_start
                + col_index
                + 1
            )

            with cols[col_index]:

                with st.container(
                    border=True
                ):

                    st.caption(
                        news.get(
                            "category"
                        )
                        or "カテゴリ不明"
                    )

                    title = news.get(
                        "title"
                    )

                    url = news.get(
                        "url"
                    )

                    st.markdown(
                        f"""
                        <div style="
                            font-size: 18px;
                            font-weight: 700;
                            line-height: 1.5;
                            margin-bottom: 12px;
                        ">
                            <a
                                href="{url}"
                                target="_blank"
                                style="
                                    color: inherit;
                                    text-decoration: none;
                                "
                            >
                                {index}. 「{title}」
                            </a>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    summary = news.get(
                        "summary"
                    )

                    if summary:

                        st.write(
                            summary
                        )

                    else:

                        st.caption(
                            "概要を取得できませんでした。"
                        )


    # ==========================================
    # 最も興味を持ったニュースの選択
    # ==========================================
    st.divider()

    st.subheader(
        "最も興味を持ったニュースを選んでください"
    )

    st.write(
        "上の9件のニュースの中から、"
        "あなたが実際に最も興味を持った"
        "ニュースを1つ選んでください。"
    )

    # おすすめ1件とその他9件をまとめる
    all_news = [
        recommended,
        *other_news,
    ]

    selected_news_id = st.radio(
        "ニュースを選択",
        options=[
            news["news_id"]
            for news in all_news
        ],
        format_func=lambda news_id: next(
            f"「{news['title']}」"
            for news in all_news
            if news["news_id"]
            == news_id
        ),
        index=None,
        key="selected_news",
    )

    # ニュースが選択された場合に
    # 選択内容を表示
    if selected_news_id is not None:

        selected_news = next(
            news
            for news in all_news
            if news["news_id"]
            == selected_news_id
        )

        st.success(
            "選択したニュース："
            f"『{selected_news['title']}』"
        )