import streamlit as st

from opinion_generator import (
    generate_article_summary,
    generate_opinion_candidates,
    predict_user_opinion,
)
from database import save_correction
from pinecone_client import save_memory

# ==========================================
# 分身AI画面を表示する関数
# ==========================================
def show_avatar_page():

    st.subheader(
        "分身AI"
    )

    # ==========================================
    # ログイン画面に戻る
    # ==========================================
    if st.button("← ログイン画面に戻る"):
        st.session_state.user_id = None
        st.session_state.register_mode = False
        st.session_state.edit_profile = False
        st.session_state.avatar_mode = False

        # 前回のユーザーの情報をクリアする
        st.session_state.recommendation_result = None
        st.session_state.selected_news = None
        st.session_state.article_summary = None
        st.session_state.summary_news_id = None
        st.session_state.opinion_candidates = None
        st.session_state.opinion_prediction = None
        st.session_state.pop("opinion_response", None)

        st.rerun()

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


    # 選択した記事の詳細要約を生成する
    if not st.session_state.get("article_summary"):
        try:
            with st.spinner("記事の詳細要約を生成しています..."):
                article_summary = generate_article_summary(selected_news)

            st.session_state.article_summary = article_summary

        except Exception as e:
            st.error(f"記事要約の生成に失敗しました：{e}")
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

            # 過去の意見履歴から判断傾向と意見を予測する
            st.session_state.opinion_prediction = None

            try:
                with st.spinner("分身AIがあなたの価値観と意見を予測しています..."):
                    prediction = predict_user_opinion(
                        user_id=st.session_state.user_id,
                        news=selected_news,
                        opinion_candidates=opinion_candidates,
                    )

                st.session_state.opinion_prediction = prediction

            except Exception as prediction_error:
                st.warning(
                    f"意見候補は生成できましたが、"
                    f"分身AIの予測に失敗しました：{prediction_error}"
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


    
    # ==========================================
    # 分身AIが推測した価値観と予測意見を表示
    # ==========================================
    prediction = st.session_state.get("opinion_prediction")

    if prediction is not None:
        st.divider()
        st.subheader("分身AIによるあなたの意見の予測")

        st.write("**推測した価値観・判断傾向（仮説）**")

        tendencies = prediction.get("inferred_tendencies", [])

        if tendencies:
            for index, tendency in enumerate(tendencies, start=1):
                st.write(f"{index}. {tendency}")
        else:
            st.info("過去の意見履歴がないため、価値観を推測できませんでした。")

        st.write("**あなたが選ぶと予測した意見**")
        st.write(
            f"**意見{prediction['predicted_opinion_id']}：**"
            f"{prediction['predicted_opinion_text']}"
        )

        st.write("**予測理由**")
        st.write(prediction["prediction_reason"])

        st.caption(
            "これらは過去の回答から推測した仮説であり、"
            "あなたの実際の価値観や意見を確定したものではありません。"
        )



    # ==========================================
    # 意見の選択・訂正
    # ==========================================
    st.divider()
    st.subheader("あなたの考えを教えてください")

    # 選択肢を作成する
    opinion_options = {}

    for index, opinion in enumerate(
        opinion_candidates.get("gradient_opinions", []),
        start=1,
    ):
        opinion_options[str(index)] = str(opinion)

    for index, item in enumerate(
        opinion_candidates.get("alternative_perspectives", []),
        start=8,
    ):
        opinion_options[str(index)] = (
            f"【{item.get('perspective')}】{item.get('opinion')}"
        )

    opinion_options["none"] = "該当する意見がない"

    # 記事が変わったときに入力状態を引き継がないようにする
    selection_key = f"opinion_selection_{news_id}"
    correction_key = f"opinion_correction_{news_id}"

    with st.form(key=f"opinion_form_{news_id}"):

        selected_opinion_id = st.radio(
            "自分の考えに最も近い意見を選択してください",
            options=list(opinion_options.keys()),
            format_func=lambda key: (
                f"{key}. {opinion_options[key]}"
                if key != "none"
                else opinion_options[key]
            ),
            index=None,
            key=selection_key,
        )

        correction_text = st.text_area(
            "選択した意見への訂正・補足、または自分の考え",
            placeholder=(
                "例：基本的には賛成だが、"
                "費用面については慎重に考えるべきだと思う。"
            ),
            height=150,
            key=correction_key,
        )

        # 現在の記事について回答が保存済みか確認する
        already_saved = (
            st.session_state.get("opinion_response", {}).get("correction_id") is not None
            and st.session_state.get("opinion_response", {}).get("news_id") == news_id
        )

        submitted = st.form_submit_button(
            "保存済み" if already_saved else "回答を確定する",
            type="primary",
            disabled=already_saved,
        )

    if submitted:

        if selected_opinion_id is None:
            st.warning("意見を1つ選択してください。")

        elif (
            selected_opinion_id == "none"
            and not correction_text.strip()
        ):
            st.warning(
                "該当する意見がない場合は、自分の考えを入力してください。"
            )

        elif not st.session_state.get("current_session_id"):
            st.error("セッションIDを取得できませんでした。")

        else:
            selected_opinion_text = (
                opinion_options.get(selected_opinion_id, "")
                if selected_opinion_id != "none"
                else ""
            )


  
            try:
                # 意見選択・訂正履歴をGoogle Sheetsに保存する
                correction_id = save_correction(
                    session_id=st.session_state.current_session_id,
                    user_id=st.session_state.user_id,
                    news_id=news_id,
                    opinion_candidates=opinion_candidates,
                    selected_opinion_id=selected_opinion_id,
                    selected_opinion_text=selected_opinion_text,
                    correction_text=correction_text.strip(),
                )

                # 保存に成功した回答をSession Stateに保持する
                st.session_state.opinion_response = {
                    "correction_id": correction_id,
                    "news_id": news_id,
                    "selected_opinion_id": selected_opinion_id,
                    "selected_opinion_text": selected_opinion_text,
                    "correction_text": correction_text.strip(),
                }

                st.success("回答をGoogle Sheetsに保存しました。")

                # 記事情報を取得する
                article_title = selected_news.get("title", "")
                article_summary = st.session_state.get("article_summary", "")
                article_category = selected_news.get("category", "")

                # Pineconeに保存する検索用テキストを作成する
                memory_text = (
                    "【記事の話題】\n"
                    f"タイトル：{article_title}\n"
                    f"カテゴリ：{article_category}\n\n"
                    "【記事の中心争点】\n"
                    f"{opinion_candidates.get('main_issue', '')}\n\n"
                    "【記事の詳細要約】\n"
                    f"{article_summary}\n\n"
                    "【ユーザーが選択した意見】\n"
                    f"{selected_opinion_text if selected_opinion_id != 'none' else '提示された意見に該当なし'}\n\n"
                    "【ユーザーが入力した訂正・自由意見】\n"
                    f"{correction_text.strip() if correction_text.strip() else '入力なし'}"
                )

                # Pineconeに保存するメタデータ
                memory_metadata = {
                    "correction_id": correction_id,
                    "session_id": st.session_state.current_session_id,
                    "news_id": news_id,
                    "selected_opinion_id": str(selected_opinion_id),
                }

                try:
                    # ログインユーザー専用Namespaceに保存する
                    save_memory(
                        memory_id=f"correction-{correction_id}",
                        user_id=st.session_state.user_id,
                        memory_type="correction",
                        text=memory_text,
                        metadata=memory_metadata,
                    )

                    st.success("回答をPineconeにも保存しました。")

                except Exception as e:
                    st.warning(
                        f"Google Sheetsへの保存は成功しましたが、"
                        f"Pineconeへの保存に失敗しました：{e}"
                    )

            except Exception as e:
                st.error(f"回答の保存に失敗しました：{e}")
