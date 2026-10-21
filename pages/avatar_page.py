import streamlit as st

from opinion_generator import (
    generate_article_summary,
    generate_opinion_candidates,
    predict_user_opinion,
)
from database import save_correction, save_value_feedback
from pinecone_client import save_memory
from review_generator import generate_review

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
        st.session_state.pop("review_mode", None)
        st.session_state.pop("review_result", None)

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
        st.session_state.opinion_prediction = None
        st.session_state.review_mode = False
        st.session_state.review_result = None
        st.session_state.pop("opinion_response", None)


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

    # 画面①で生成した意見候補を取得する
    opinion_candidates = st.session_state.get("opinion_candidates")


    # ==========================================
    # 画面②：本人の意見とAIの予測を確認・訂正
    # ==========================================
    if st.session_state.get("review_mode", False):

        review_result = st.session_state.get("review_result")
        pending_response = st.session_state.get("pending_opinion_response")
        prediction = st.session_state.get("opinion_prediction")

        if not review_result or not pending_response or not prediction:
            st.error("確認画面に必要な情報を取得できませんでした。")
            return

        st.divider()
        st.header("あなたの考えの確認・訂正")

        st.write(
            "以下はAIが作成した下書きです。"
            "内容を確認し、違う部分があれば修正してください。"
        )

        # ==========================================
        # 1. 本人の意見を確認・訂正
        # ==========================================
        st.subheader("① あなたの意見")

        st.text_area(
            "AIが整理したあなたの意見",
            value=review_result["user_opinion"],
            height=160,
            key=f"review_user_opinion_{news_id}",
        )

        st.divider()

        # ==========================================
        # 2. 分身AIの予測と本人の回答を比較
        # ==========================================
        st.subheader("② 分身AIの予測との比較")

        st.write("**分身AIが予測した意見**")
        st.info(
            prediction.get("predicted_opinion_text", "")
        )

        st.write("**あなたが選択した意見**")

        selected_text = pending_response.get(
            "selected_opinion_text", ""
        )

        if selected_text:
            st.write(selected_text)
        else:
            st.write("該当する意見がない")

        if pending_response.get("correction_text"):
            st.write(
                "**あなたが入力した補足・訂正**"
            )
            st.write(pending_response["correction_text"])

        st.write("**予測がずれた理由についてのAIの推測**")

        st.caption(
            "AIが理由を推測して入力しています。"
            "合っていない部分は自由に修正してください。"
        )

        st.text_area(
            "予測とあなたの考えに違いが生じた理由",
            value=review_result["difference_reason"],
            height=160,
            key=f"review_difference_reason_{news_id}",
        )

        st.divider()

        # ==========================================
        # 3. 判断傾向の仮説を評価・訂正
        # ==========================================
        st.subheader("③ 価値観・判断傾向の確認")

        st.write(
            "分身AIがあなたについて推測した"
            "判断傾向を評価してください。"
        )

        tendencies = prediction.get(
            "inferred_tendencies", []
        )

        if not tendencies:
            st.info(
                "現時点では、評価する判断傾向の仮説がありません。"
            )

        for index, tendency in enumerate(tendencies):

            # 文字列・辞書のどちらでも表示できるようにする
            if isinstance(tendency, dict):
                tendency_text = str(tendency)
            else:
                tendency_text = str(tendency)

            st.write(
                f"**仮説{index + 1}：{tendency_text}**"
            )

            rating = st.radio(
                "この推測はあなたに当てはまりますか？",
                options=[
                    "合っている",
                    "一部合っている",
                    "違う",
                    "判断できない",
                ],
                index=None,
                key=f"tendency_rating_{news_id}_{index}",
            )

            if rating in ["一部合っている", "違う"]:
                st.text_area(
                    "どこが違うか、あなたの考えを教えてください",
                    height=100,
                    key=f"tendency_correction_{news_id}_{index}",
                )

            st.divider()

        # ==========================================
        # 4. 戻る・保存
        # ==========================================
        if st.button(
            "← 意見選択に戻る",
            key=f"back_to_opinion_{news_id}",
        ):
            st.session_state.review_mode = False
            st.rerun()

        
        # ==========================================
        # 5. 最終確認した内容をGoogle Sheetsに保存
        # ==========================================

        # すべての仮説の評価・訂正を取得する
        feedback_items = []
        missing_ratings = False

        for index, tendency in enumerate(tendencies):

            rating = st.session_state.get(
                f"tendency_rating_{news_id}_{index}"
            )

            if rating is None:
                missing_ratings = True

            correction = st.session_state.get(
                f"tendency_correction_{news_id}_{index}", ""
            )

            feedback_items.append({
                "hypothesis_index": index + 1,
                "ai_hypothesis": str(tendency),
                "user_rating": rating or "",
                "user_correction": (
                    correction.strip()
                    if rating in ["一部合っている", "違う"]
                    else ""
                ),
            })

        # 本人が確認・修正した意見と理由を取得する
        final_opinion = st.session_state.get(
            f"review_user_opinion_{news_id}", ""
        ).strip()

        final_difference_reason = st.session_state.get(
            f"review_difference_reason_{news_id}", ""
        ).strip()

        # 保存済みの回答IDを確認する
        saved_response = st.session_state.get(
            "opinion_response"
        ) or {}

        correction_id = (
            saved_response.get("correction_id")
            if saved_response.get("news_id") == news_id
            else None
        )

        feedback_saved = saved_response.get(
            "feedback_saved", False
        ) if correction_id else False

        # 保存ボタン
        save_clicked = st.button(
            "保存済み" if feedback_saved else "最終確定して保存",
            type="primary",
            disabled=feedback_saved,
            key=f"final_save_{news_id}",
        )

        if save_clicked:

            if not final_opinion:
                st.warning("あなたの意見を入力してください。")

            elif missing_ratings:
                st.warning(
                    "すべての価値観・判断傾向を評価してください。"
                )

            elif not st.session_state.get("current_session_id"):
                st.error("セッションIDを取得できませんでした。")

            else:
                try:
                    # 回答本体が未保存の場合だけ保存する
                    if correction_id is None:

                        correction_id = save_correction(
                            session_id=st.session_state.current_session_id,
                            user_id=st.session_state.user_id,
                            news_id=news_id,
                            opinion_candidates=opinion_candidates,
                            prediction=prediction,
                            selected_opinion_id=pending_response[
                                "selected_opinion_id"
                            ],
                            selected_opinion_text=pending_response[
                                "selected_opinion_text"
                            ],
                            correction_text=pending_response[
                                "correction_text"
                            ],
                            ai_generated_opinion=review_result[
                                "user_opinion"
                            ],
                            user_final_opinion=final_opinion,
                            ai_difference_reason=review_result[
                                "difference_reason"
                            ],
                            user_final_difference_reason=final_difference_reason,
                        )

                        # 回答IDを保持し、重複保存を防ぐ
                        st.session_state.opinion_response = {
                            "correction_id": correction_id,
                            "news_id": news_id,
                            "feedback_saved": False,
                        }

                    # 価値観・判断傾向の評価を保存する
                    save_value_feedback(
                        correction_id=correction_id,
                        user_id=st.session_state.user_id,
                        feedback_items=feedback_items,
                    )


                    
                    # ==========================================
                    # 本人の確定した意見をPineconeに保存
                    # ==========================================
                    article_title = selected_news.get("title", "")
                    article_category = selected_news.get("category", "")
                    article_summary = st.session_state.get(
                        "article_summary", ""
                    )

                    memory_text = (
                        "【記事の話題】\n"
                        f"タイトル：{article_title}\n"
                        f"カテゴリ：{article_category}\n\n"
                        "【記事の中心争点】\n"
                        f"{opinion_candidates.get('main_issue', '')}\n\n"
                        "【記事の詳細要約】\n"
                        f"{article_summary}\n\n"
                        "【本人が最終確認した意見】\n"
                        f"{final_opinion}\n\n"
                        "【本人が確認した予測のずれの理由】\n"
                        f"{final_difference_reason}"
                    )

                    memory_metadata = {
                        "correction_id": correction_id,
                        "session_id": st.session_state.current_session_id,
                        "news_id": news_id,
                        "selected_opinion_id": str(
                            pending_response["selected_opinion_id"]
                        ),
                    }

                    try:
                        # 本人の確定した意見を保存する
                        save_memory(
                            memory_id=f"correction-{correction_id}",
                            user_id=st.session_state.user_id,
                            memory_type="correction",
                            text=memory_text,
                            metadata=memory_metadata,
                        )

                        # ==========================================
                        # 価値観の評価・訂正をPineconeに保存
                        # ==========================================
                        for item in feedback_items:

                            rating = item["user_rating"]

                            # 判断できない仮説は学習用の記憶にしない
                            if rating == "判断できない":
                                continue

                            value_memory_text = (
                                "【本人による価値観・判断傾向の評価】\n"
                                f"AIの仮説：{item['ai_hypothesis']}\n"
                                f"本人の評価：{rating}\n"
                                "【本人による訂正・補足】\n"
                                f"{item['user_correction'] or '訂正なし'}\n\n"
                                "【評価したニュース】\n"
                                f"{article_title}"
                            )

                            save_memory(
                                memory_id=(
                                    f"value-feedback-{correction_id}-"
                                    f"{item['hypothesis_index']}"
                                ),
                                user_id=st.session_state.user_id,
                                memory_type="value_feedback",
                                text=value_memory_text,
                                metadata={
                                    "correction_id": correction_id,
                                    "session_id": st.session_state.current_session_id,
                                    "news_id": news_id,
                                    "hypothesis_index": str(
                                        item["hypothesis_index"]
                                    ),
                                    "user_rating": rating,
                                },
                            )

                        st.success("Pineconeへの保存が完了しました。")

                    except Exception as e:
                        st.warning(
                            "Google Sheetsへの保存は成功しましたが、"
                            f"Pineconeへの保存に失敗しました：{e}"
                        )

                    
                    # 保存完了を記録する
                    st.session_state.opinion_response[
                        "feedback_saved"
                    ] = True

                    st.success(
                        "回答と価値観の評価をGoogle Sheetsに保存しました。"
                    )

                    st.rerun()

                except Exception as e:
                    st.error(
                        f"Google Sheetsへの保存に失敗しました：{e}"
                    )

        if feedback_saved:
            st.success(
                "回答と価値観の評価は保存済みです。"
            )


        # 画面②では、画面①の入力フォームを表示しない
        return


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
            "次へ進む",
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

        elif not st.session_state.get("opinion_prediction"):
            st.error("分身AIの意見予測を取得できませんでした。")

        else:
            selected_opinion_text = (
                opinion_options.get(selected_opinion_id, "")
                if selected_opinion_id != "none"
                else ""
            )

            try:
                with st.spinner("あなたの意見と予測のずれを分析しています..."):

                    # 本人の意見文と予測のずれの理由を生成する
                    review_result = generate_review(
                        news=selected_news,
                        selected_opinion_id=selected_opinion_id,
                        selected_opinion_text=selected_opinion_text,
                        correction_text=correction_text,
                        prediction=st.session_state.opinion_prediction,
                    )

                # 画面①で入力した元の回答を一時保存する
                st.session_state.pending_opinion_response = {
                    "news_id": news_id,
                    "selected_opinion_id": selected_opinion_id,
                    "selected_opinion_text": selected_opinion_text,
                    "correction_text": correction_text.strip(),
                }

                # AIが生成した確認用の文章を保持する
                st.session_state.review_result = review_result

                # 確認・訂正画面へ進む状態にする
                st.session_state.review_mode = True

                st.rerun()

            except Exception as e:
                st.error(f"確認用の文章生成に失敗しました：{e}")
