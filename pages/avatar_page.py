import streamlit as st

from opinion_generator import (
    generate_article_summary,
    generate_opinion_candidates,
)


# ==========================================
# 分身AI画面を表示する関数
# ==========================================
def show_avatar_page():

    st.subheader(
        "分身AI"
    )

    # ==========================================
    # 選択したニュースを取得
    # ==========================================
    selected_news = st.session_state.get(
        "selected_news"
    )

    if selected_news is None:
        st.error(
            "選択したニュースを取得できませんでした。"
        )
        return


    # ==========================================
    # 選択したニュースを表示
    # ==========================================
    st.write(
        "**あなたが選択したニュース**"
    )

    title = selected_news.get(
        "title",
        "タイトルなし",
    )

    url = selected_news.get(
        "url",
        "",
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
        f"{selected_news.get('category', '不明')}"
    )

    if selected_news.get(
        "source"
    ):
        st.write(
            f"配信元："
            f"{selected_news.get('source')}"
        )


    # ==========================================
    # 記事要約を生成
    # ==========================================
    news_id = selected_news.get(
        "news_id"
    )

    # 別の記事を選んだ場合は、
    # 前の記事の要約を使用しない
    if (
        st.session_state.get(
            "summary_news_id"
        )
        != news_id
    ):

        st.session_state.article_summary = None
        st.session_state.summary_news_id = news_id
        st.session_state.opinion_candidates = None


    # 要約がまだ生成されていなければ生成する
    if not st.session_state.get(
        "article_summary"
    ):

        try:

            with st.spinner(
                "記事本文を読み込んでいます..."
            ):

                article_summary = (
                    generate_article_summary(
                        selected_news
                    )
                )

            st.session_state.article_summary = (
                article_summary
            )

        except Exception as e:

            st.error(
                f"記事要約の生成に失敗しました：{e}"
            )
            return


    # ==========================================
    # 記事要約を表示
    # ==========================================
    st.write(
        "**記事の要約**"
    )

    st.write(
        st.session_state.article_summary
    )


    # ==========================================
    # 分身AIによる意見分析
    # ==========================================
    st.divider()

    st.subheader(
        "分身AIによる意見分析"
    )

    if st.button(
        "分身AIの意見を生成",
        type="primary",
    ):

        try:

            with st.spinner(
                "この記事について考えています..."
            ):

                opinion_candidates = (
                    generate_opinion_candidates(
                        selected_news
                    )
                )

            st.session_state.opinion_candidates = (
                opinion_candidates
            )

        except Exception as e:

            st.error(
                f"意見候補の生成に失敗しました：{e}"
            )


    # ==========================================
    # 生成された意見候補を取得
    # ==========================================
    opinion_candidates = st.session_state.get(
        "opinion_candidates"
    )

    if opinion_candidates is None:
        return


    # ==========================================
    # 中心的な争点を表示
    # ==========================================
    st.write(
        "**中心的な争点**"
    )

    st.write(
        opinion_candidates.get(
            "main_issue"
        )
    )


    # ==========================================
    # 中心争点についての7つの意見を表示
    # ==========================================
    st.write(
        "**中心争点についての7つの意見**"
    )

    for index, opinion in enumerate(
        opinion_candidates.get(
            "gradient_opinions",
            [],
        ),
        start=1,
    ):

        st.write(
            f"{index}. {opinion}"
        )


    # ==========================================
    # その他の視点からの3つの意見を表示
    # ==========================================
    st.write(
        "**その他の視点からの3つの意見**"
    )

    for index, item in enumerate(
        opinion_candidates.get(
            "alternative_perspectives",
            [],
        ),
        start=8,
    ):

        st.write(
            f"{index}. "
            f"【{item.get('perspective')}】"
            f"{item.get('opinion')}"
        )