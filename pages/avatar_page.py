# -*- coding: utf-8 -*-
"""
分身AIの意見予測・訂正画面 (Avatar Page)
- 画面①: 選択したニュースについての中心的な争点・意見候補の確認、および本人の意見選択
- 画面②: AIの予測と本人の回答の比較、意見の確定・修正、判断傾向の評価と保存
"""

import textwrap
import streamlit as st

from opinion_generator import (
    generate_opinion_candidates,
    predict_user_opinion,
)
from database import save_correction, save_value_feedback
from pinecone_client import save_memory
from review_generator import generate_review

from ui_common import (
    inject_custom_css,
    render_common_header,
    get_category_badge_html,
)


# 分身AI画面を表示する関数
def show_avatar_page():
    # 共通CSSを適用
    inject_custom_css()

    # ==========================================
    # 上部ナビゲーションバー
    # ==========================================
    nav_col1, nav_col2 = st.columns([1, 1])

    with nav_col1:
        if st.button("← ニュース選択に戻る", key="back_to_news_list"):
            st.session_state.avatar_mode = False
            st.session_state.pop("opinion_candidates", None)
            st.session_state.pop("opinion_prediction", None)
            st.session_state.pop("opinion_response", None)
            st.session_state.pop("review_mode", None)
            st.session_state.pop("review_result", None)
            st.rerun()

    with nav_col2:
        if st.button("← ログイン画面に戻る", key="back_to_login_from_avatar"):
            st.session_state.user_id = None
            st.session_state.register_mode = False
            st.session_state.edit_profile = False
            st.session_state.avatar_mode = False
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
    selected_news = st.session_state.get("selected_news")

    if selected_news is None:
        st.error("選択したニュースを取得できませんでした。")
        return

    news_id = selected_news.get("news_id")

    # 別の記事を選んだ場合は前回の情報をリセット
    if st.session_state.get("summary_news_id") != news_id:
        st.session_state.article_summary = None
        st.session_state.summary_news_id = news_id
        st.session_state.opinion_candidates = None
        st.session_state.opinion_prediction = None
        st.session_state.review_mode = False
        st.session_state.review_result = None
        st.session_state.pop("opinion_response", None)

    # ニュース一覧ページと同じ要約を保持
    article_summary = (
        selected_news.get("ai_summary")
        or selected_news.get("summary")
        or "要約を取得できませんでした。"
    )
    st.session_state.article_summary = article_summary

    in_review_mode = st.session_state.get("review_mode", False)

    # ==========================================
    # 共通ヘッダー（進捗ステップ表示）
    # ==========================================
    if in_review_mode:
        render_common_header(
            title="あなたの考えの確認・訂正",
            subtitle="AIの予測とあなたの回答を比較し、意見の下書きや判断傾向の推測を確認・訂正します。",
            current_step=3,
        )
    else:
        render_common_header(
            title="分身AIの意見分析",
            subtitle="記事の中心的な争点と意見候補を確認し、あなたの考えに最も近いものを選んでください。",
            current_step=2,
        )

    # ==========================================
    # 4-1. 選択ニュースのコンパクト表示カード
    # ==========================================
    news_title = selected_news.get("title", "タイトルなし")
    news_url = selected_news.get("url", "#")
    news_cat = selected_news.get("category", "")
    news_source = selected_news.get("source") or ""

    news_card_html = textwrap.dedent(
        f"""
        <div style="
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 14px;
            padding: 18px 20px;
            margin-bottom: 24px;
            box-shadow: 0 2px 8px rgba(31, 41, 55, 0.03);
        ">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; flex-wrap: wrap; gap: 8px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 12px; font-weight: 700; color: #4F46E5;">選択中のニュース</span>
                    {get_category_badge_html(news_cat)}
                </div>
                <span style="font-size: 12.5px; color: #475569;">配信元：{news_source}</span>
            </div>
            <div style="font-size: 17px; font-weight: 700; line-height: 1.45; margin-bottom: 10px;">
                <a href="{news_url}" target="_blank" style="color: #1F2937; text-decoration: none;">
                    「{news_title}」
                </a>
            </div>
            <div style="
                background: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13.5px;
                color: #374151;
                line-height: 1.6;
            ">
                <strong style="color: #1F2937;">記事の要約：</strong>{article_summary}
            </div>
        </div>
        """
    ).strip()
    st.markdown(news_card_html, unsafe_allow_html=True)

    # =========================================================================
    # 画面②：本人の意見とAIの予測を確認・訂正 (review_mode == True)
    # =========================================================================
    if in_review_mode:
        review_result = st.session_state.get("review_result")
        pending_response = st.session_state.get("pending_opinion_response")
        prediction = st.session_state.get("opinion_prediction")
        opinion_candidates = st.session_state.get("opinion_candidates")

        if not review_result or not pending_response or not prediction:
            st.error("確認画面に必要な情報を取得できませんでした。")
            return

        # ---------------------------------------------------------------------
        # 4-3. STEP 1｜AIの予測を確認（比較カード ＆ 一致判定）
        # ---------------------------------------------------------------------
        step1_title_html = textwrap.dedent(
            """
            <div style="margin: 28px 0 16px 0;">
                <h2 style="font-size: 20px; font-weight: 700; color: #1F2937; margin: 0 0 4px 0;">
                    STEP 1 ｜ AIの予測を確認
                </h2>
                <p style="font-size: 13.5px; color: #475569; margin: 0;">
                    分身AIが事前に予測した意見と、あなたが実際に選択した回答を比較します。
                </p>
            </div>
            """
        ).strip()
        st.markdown(step1_title_html, unsafe_allow_html=True)

        ai_predicted_index = str(prediction.get("predicted_opinion_id", ""))
        user_selected_index = str(pending_response.get("selected_opinion_id", ""))
        is_matched = (
            ai_predicted_index == user_selected_index
            and user_selected_index != "none"
        )

        # 一致・不一致バッジの表示
        if is_matched:
            matched_badge_html = textwrap.dedent(
                """
                <div style="
                    display: inline-flex;
                    align-items: center;
                    gap: 8px;
                    background: #ECFDF5;
                    border: 1px solid #A7F3D0;
                    color: #065F46;
                    padding: 8px 16px;
                    border-radius: 20px;
                    font-size: 14px;
                    font-weight: 700;
                    margin-bottom: 16px;
                ">
                    <span>✅</span> 予測が一致しました
                </div>
                """
            ).strip()
            st.markdown(matched_badge_html, unsafe_allow_html=True)
        else:
            unmatched_badge_html = textwrap.dedent(
                """
                <div style="
                    display: inline-flex;
                    align-items: center;
                    gap: 8px;
                    background: #FFF7ED;
                    border: 1px solid #FED7AA;
                    color: #9A3412;
                    padding: 8px 16px;
                    border-radius: 20px;
                    font-size: 14px;
                    font-weight: 700;
                    margin-bottom: 16px;
                ">
                    <span>⚡</span> 予測と回答が異なりました
                </div>
                """
            ).strip()
            st.markdown(unmatched_badge_html, unsafe_allow_html=True)

        # 2つのカードを横並びで表示
        step1_col1, step1_col2 = st.columns(2)

        predicted_text = prediction.get("predicted_opinion_text", "")
        selected_text = pending_response.get("selected_opinion_text", "") or "該当する意見がない"
        user_correction = pending_response.get("correction_text", "")

        with step1_col1:
            step1_card1_html = textwrap.dedent(
                f"""
                <div style="
                    background: #EEF2FF;
                    border: 1px solid #C7D2FE;
                    border-radius: 14px;
                    padding: 18px 20px;
                    height: 100%;
                    box-sizing: border-box;
                ">
                    <div style="
                        display: flex;
                        align-items: center;
                        gap: 6px;
                        font-size: 14.5px;
                        font-weight: 700;
                        color: #3730A3;
                        margin-bottom: 10px;
                    ">
                        🤖 分身AIの予測
                    </div>
                    <div style="font-size: 14px; line-height: 1.65; color: #1F2937;">
                        {predicted_text}
                    </div>
                </div>
                """
            ).strip()
            st.markdown(step1_card1_html, unsafe_allow_html=True)

        with step1_col2:
            correction_html = ""
            if user_correction:
                correction_html = f"""
                <div style="margin-top: 10px; padding-top: 8px; border-top: 1px dashed #CBD5E1; font-size: 12.5px; color: #475569;">
                    <strong style="color: #1F2937;">入力した補足・訂正：</strong><br>{user_correction}
                </div>
                """

            step1_card2_html = textwrap.dedent(
                f"""
                <div style="
                    background: #F0FDF4;
                    border: 1px solid #BBF7D0;
                    border-radius: 14px;
                    padding: 18px 20px;
                    height: 100%;
                    box-sizing: border-box;
                ">
                    <div style="
                        display: flex;
                        align-items: center;
                        gap: 6px;
                        font-size: 14.5px;
                        font-weight: 700;
                        color: #166534;
                        margin-bottom: 10px;
                    ">
                        👤 あなたの回答
                    </div>
                    <div style="font-size: 14px; line-height: 1.65; color: #1F2937;">
                        {selected_text}
                    </div>
                    {correction_html}
                </div>
                """
            ).strip()
            st.markdown(step1_card2_html, unsafe_allow_html=True)

        # ---------------------------------------------------------------------
        # 4-4. STEP 2｜あなたの意見を確定する
        # ---------------------------------------------------------------------
        step2_title_html = textwrap.dedent(
            """
            <div style="margin: 36px 0 14px 0;">
                <h2 style="font-size: 20px; font-weight: 700; color: #1F2937; margin: 0 0 4px 0;">
                    STEP 2 ｜ あなたの意見を確定する
                </h2>
                <p style="font-size: 13.5px; color: #475569; margin: 0;">
                    AIがあなたの回答を文章にまとめました。自分の考えと違う部分があれば修正してください。
                </p>
            </div>
            """
        ).strip()
        st.markdown(step2_title_html, unsafe_allow_html=True)

        st.text_area(
            "AIが整理したあなたの意見",
            value=review_result["user_opinion"],
            height=120,
            key=f"review_user_opinion_{news_id}",
            help="必要に応じて修正できます",
        )
        st.caption("※修正する必要がなければ、そのままで構いません。")

        # ---------------------------------------------------------------------
        # 4-5. AIが推測した予測のずれの理由
        # ---------------------------------------------------------------------
        if is_matched:
            matched_reason_html = textwrap.dedent(
                """
                <div style="
                    background: #F0FDF4;
                    border: 1px solid #BBF7D0;
                    border-radius: 12px;
                    padding: 16px 20px;
                    margin-top: 24px;
                    margin-bottom: 12px;
                ">
                    <div style="font-size: 14px; font-weight: 700; color: #166534; margin-bottom: 4px;">
                        🎯 予測と選択の一致
                    </div>
                    <div style="font-size: 13.5px; color: #1F2937;">
                        今回、AIの予測とあなたの選択は一致しました。
                    </div>
                </div>
                """
            ).strip()
            st.markdown(matched_reason_html, unsafe_allow_html=True)
            # 既存の保存処理で必要な値を保持（折りたたみで確認可能にする）
            with st.expander("AIによる分析理由を確認する", expanded=False):
                st.text_area(
                    "予測とあなたの考えについての分析",
                    value=review_result["difference_reason"],
                    height=100,
                    key=f"review_difference_reason_{news_id}",
                )
        else:
            diff_title_html = textwrap.dedent(
                """
                <div style="margin-top: 24px; margin-bottom: 8px;">
                    <span style="font-size: 14.5px; font-weight: 700; color: #1F2937;">
                        予測がずれた理由についてのAIの推測
                    </span>
                    <p style="font-size: 13px; color: #475569; margin: 2px 0 8px 0;">
                        AIが予測を外した理由について、次のように推測しています。違う部分があれば修正してください。
                    </p>
                </div>
                """
            ).strip()
            st.markdown(diff_title_html, unsafe_allow_html=True)
            st.text_area(
                "予測とあなたの考えに違いが生じた理由",
                value=review_result["difference_reason"],
                height=120,
                key=f"review_difference_reason_{news_id}",
            )
            st.caption("※修正する必要がなければ、そのままで構いません。")

        # ---------------------------------------------------------------------
        # 4-6. STEP 3｜AIが推測したあなたの価値観・判断傾向
        # ---------------------------------------------------------------------
        step3_title_html = textwrap.dedent(
            """
            <div style="margin: 36px 0 14px 0;">
                <h2 style="font-size: 20px; font-weight: 700; color: #1F2937; margin: 0 0 4px 0;">
                    STEP 3 ｜ AIが推測したあなたの価値観・判断傾向
                </h2>
                <p style="font-size: 13.5px; color: #475569; margin: 0;">
                    今回の回答から、AIがあなたの考え方の傾向を推測しました。内容が当てはまるか評価してください。
                </p>
            </div>
            """
        ).strip()
        st.markdown(step3_title_html, unsafe_allow_html=True)

        tendencies = prediction.get("inferred_tendencies", [])

        if not tendencies:
            st.info("現時点では、評価する判断傾向の仮説がありません。")

        for index, tendency in enumerate(tendencies):
            tendency_text = str(tendency)

            with st.container(border=True):
                # 上段：仮説ラベルと推測テキスト
                tendency_box_html = textwrap.dedent(
                    f"""
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                        <span style="
                            background: #EEF2FF;
                            color: #4338CA;
                            border: 1px solid #C7D2FE;
                            padding: 3px 10px;
                            border-radius: 12px;
                            font-size: 12px;
                            font-weight: 700;
                        ">💡 仮説 {index + 1}</span>
                    </div>
                    <div style="font-size: 15px; font-weight: 600; color: #1F2937; line-height: 1.5; margin-bottom: 12px;">
                        {tendency_text}
                    </div>
                    """
                ).strip()
                st.markdown(tendency_box_html, unsafe_allow_html=True)

                # 下段：評価ラジオボタン
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
                    horizontal=True,
                )

                if rating in ["一部合っている", "違う"]:
                    st.text_area(
                        "どこが違うか、あなたの考えを教えてください",
                        height=90,
                        key=f"tendency_correction_{news_id}_{index}",
                        placeholder="例：〇〇という観点よりも、△△を重視しているため。",
                    )

        # ---------------------------------------------------------------------
        # 4-7. 最終確定・保存エリア
        # ---------------------------------------------------------------------
        st.markdown("<hr style='margin: 36px 0 20px 0;'>", unsafe_allow_html=True)

        footer_col1, footer_col2 = st.columns([1, 2])

        with footer_col1:
            if st.button(
                "← 意見選択に戻る",
                key=f"back_to_opinion_{news_id}",
                use_container_width=True,
            ):
                st.session_state.review_mode = False
                st.rerun()

        with footer_col2:
            saved_response = st.session_state.get("opinion_response") or {}
            correction_id = (
                saved_response.get("correction_id")
                if saved_response.get("news_id") == news_id
                else None
            )
            feedback_saved = (
                saved_response.get("feedback_saved", False)
                if correction_id
                else False
            )

            save_clicked = st.button(
                "保存済み" if feedback_saved else "この内容で確定して保存する ✨",
                type="primary",
                disabled=feedback_saved,
                key=f"final_save_{news_id}",
                use_container_width=True,
            )

        # 保存処理の実行（既存ロジック100%維持）
        if save_clicked:
            final_opinion = st.session_state.get(
                f"review_user_opinion_{news_id}", ""
            ).strip()

            final_difference_reason = st.session_state.get(
                f"review_difference_reason_{news_id}", ""
            ).strip()

            # 仮説評価データの取得
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

            if not final_opinion:
                st.warning("あなたの意見を入力してください。")
            elif missing_ratings:
                st.warning("すべての価値観・判断傾向を評価してください。")
            elif not st.session_state.get("current_session_id"):
                st.error("セッションIDを取得できませんでした。")
            else:
                try:
                    # 回答本体の保存
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

                        st.session_state.opinion_response = {
                            "correction_id": correction_id,
                            "news_id": news_id,
                            "feedback_saved": False,
                        }

                    # 価値観評価の保存
                    save_value_feedback(
                        correction_id=correction_id,
                        user_id=st.session_state.user_id,
                        feedback_items=feedback_items,
                    )

                    # Pineconeへ意見記憶の保存
                    article_title = selected_news.get("title", "")
                    article_category = selected_news.get("category", "")

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
                        save_memory(
                            memory_id=f"correction-{correction_id}",
                            user_id=st.session_state.user_id,
                            memory_type="correction",
                            text=memory_text,
                            metadata=memory_metadata,
                        )

                        # 価値観評価をPineconeに保存
                        for item in feedback_items:
                            f_rating = item["user_rating"]
                            if f_rating == "判断できない":
                                continue

                            value_memory_text = (
                                "【本人による価値観・判断傾向の評価】\n"
                                f"AIの仮説：{item['ai_hypothesis']}\n"
                                f"本人の評価：{f_rating}\n"
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
                                    "user_rating": f_rating,
                                },
                            )

                        st.success("Pineconeへの保存が完了しました。")

                    except Exception as e:
                        st.warning(
                            "Google Sheetsへの保存は成功しましたが、"
                            f"Pineconeへの保存に失敗しました：{e}"
                        )

                    st.session_state.opinion_response["feedback_saved"] = True
                    st.success("回答と価値観の評価をGoogle Sheetsに保存しました。")
                    st.rerun()

                except Exception as e:
                    st.error(f"Google Sheetsへの保存に失敗しました：{e}")

        if feedback_saved:
            st.success("回答と価値観の評価は保存済みです。")

        return

    # =========================================================================
    # 画面①：意見候補の生成と選択
    # =========================================================================
    opinion_candidates = st.session_state.get("opinion_candidates")

    # 意見候補がまだ生成されていない場合
    if opinion_candidates is None:
        init_avatar_box_html = textwrap.dedent(
            """
            <div style="
                background: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 16px;
                padding: 40px 30px;
                text-align: center;
                margin: 20px 0;
                box-shadow: 0 4px 16px rgba(79, 70, 229, 0.05);
            ">
                <div style="font-size: 42px; margin-bottom: 12px;">🤔</div>
                <h2 style="font-size: 21px; font-weight: 700; color: #1F2937; margin-bottom: 8px;">
                    この記事について分身AIと一緒に考えましょう
                </h2>
                <p style="font-size: 14.5px; color: #475569; max-width: 560px; margin: 0 auto 24px auto;">
                    AIが記事の中心的な争点を抽出し、10個の意見候補を作成します。
                    また、過去の回答傾向をもとにあなたの意見を予測します。
                </p>
            </div>
            """
        ).strip()
        st.markdown(init_avatar_box_html, unsafe_allow_html=True)

        if st.button("分身AIの意見を生成する ✨", type="primary", use_container_width=True):
            try:
                with st.spinner("この記事の中心的な争点と意見候補を考えています..."):
                    opinion_candidates = generate_opinion_candidates(selected_news)

                st.session_state.opinion_candidates = opinion_candidates
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
                        f"意見候補は生成できましたが、分身AIの予測に失敗しました：{prediction_error}"
                    )

                st.rerun()

            except Exception as e:
                st.error(f"意見候補の生成に失敗しました：{e}")

        return

    # -------------------------------------------------------------------------
    # 4-2. 意見候補の表示（中心的な争点 ＆ 10個の意見）
    # -------------------------------------------------------------------------

    # 1. 中心的な争点（薄いブルーのカード）
    main_issue = opinion_candidates.get("main_issue", "")
    if main_issue:
        main_issue_html = textwrap.dedent(
            f"""
            <div style="
                background: #EFF6FF;
                border: 1px solid #BFDBFE;
                border-radius: 14px;
                padding: 18px 22px;
                margin-bottom: 24px;
            ">
                <div style="
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    font-size: 14.5px;
                    font-weight: 700;
                    color: #1D4ED8;
                    margin-bottom: 8px;
                ">
                    🎯 中心的な争点
                </div>
                <div style="font-size: 15px; font-weight: 600; line-height: 1.6; color: #1F2937;">
                    {main_issue}
                </div>
            </div>
            """
        ).strip()
        st.markdown(main_issue_html, unsafe_allow_html=True)

    # 2. 意見1〜7：中心争点についての意見
    gradient_opinions = opinion_candidates.get("gradient_opinions", [])
    if gradient_opinions:
        grad_header_html = textwrap.dedent(
            """
            <div style="margin: 24px 0 12px 0;">
                <h3 style="font-size: 17px; font-weight: 700; color: #1F2937; margin: 0 0 4px 0;">
                    ⚖️ 中心争点についての7つの意見
                </h3>
                <p style="font-size: 13px; color: #475569; margin: 0;">
                    賛成から反対まで、グラデーション状の意見候補です。
                </p>
            </div>
            """
        ).strip()
        st.markdown(grad_header_html, unsafe_allow_html=True)

        for idx, op in enumerate(gradient_opinions, start=1):
            op_html = textwrap.dedent(
                f"""
                <div style="
                    background: #FFFFFF;
                    border: 1px solid #E2E8F0;
                    border-radius: 10px;
                    padding: 12px 16px;
                    margin-bottom: 8px;
                    display: flex;
                    gap: 12px;
                    align-items: flex-start;
                ">
                    <span style="
                        background: #EEF2FF;
                        color: #4338CA;
                        font-weight: 700;
                        font-size: 12px;
                        padding: 2px 8px;
                        border-radius: 6px;
                        flex-shrink: 0;
                    ">意見 {idx}</span>
                    <span style="font-size: 14px; line-height: 1.55; color: #1F2937;">
                        {op}
                    </span>
                </div>
                """
            ).strip()
            st.markdown(op_html, unsafe_allow_html=True)

    # 3. 意見8〜10：その他の視点からの意見
    alt_perspectives = opinion_candidates.get("alternative_perspectives", [])
    if alt_perspectives:
        alt_header_html = textwrap.dedent(
            """
            <div style="margin: 24px 0 12px 0;">
                <h3 style="font-size: 17px; font-weight: 700; color: #1F2937; margin: 0 0 4px 0;">
                    💡 その他の視点からの3つの意見
                </h3>
                <p style="font-size: 13px; color: #475569; margin: 0;">
                    別の角度や長期的な視点からの意見候補です。
                </p>
            </div>
            """
        ).strip()
        st.markdown(alt_header_html, unsafe_allow_html=True)

        for idx, item in enumerate(alt_perspectives, start=8):
            persp = item.get("perspective", "別視点")
            op = item.get("opinion", "")
            alt_op_html = textwrap.dedent(
                f"""
                <div style="
                    background: #FFFFFF;
                    border: 1px solid #E2E8F0;
                    border-radius: 10px;
                    padding: 12px 16px;
                    margin-bottom: 8px;
                    display: flex;
                    gap: 12px;
                    align-items: flex-start;
                ">
                    <span style="
                        background: #EFF6FF;
                        color: #1D4ED8;
                        font-weight: 700;
                        font-size: 12px;
                        padding: 2px 8px;
                        border-radius: 6px;
                        flex-shrink: 0;
                    ">意見 {idx}【{persp}】</span>
                    <span style="font-size: 14px; line-height: 1.55; color: #1F2937;">
                        {op}
                    </span>
                </div>
                """
            ).strip()
            st.markdown(alt_op_html, unsafe_allow_html=True)

    # 4. 分身AIによる意見予測の事前表示
    prediction = st.session_state.get("opinion_prediction")
    if prediction is not None:
        pred_box_html = textwrap.dedent(
            f"""
            <div style="
                background: linear-gradient(180deg, #EEF2FF 0%, #F8FAFF 100%);
                border: 1px solid #C7D2FE;
                border-radius: 14px;
                padding: 20px 22px;
                margin: 28px 0;
            ">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
                    <span style="font-size: 18px;">🤖</span>
                    <span style="font-size: 16px; font-weight: 700; color: #3730A3;">分身AIによるあなたの意見予測</span>
                </div>
                <div style="
                    background: #FFFFFF;
                    border: 1px solid #C7D2FE;
                    border-radius: 10px;
                    padding: 14px 16px;
                    margin-bottom: 12px;
                ">
                    <div style="font-size: 12.5px; font-weight: 700; color: #4F46E5; margin-bottom: 4px;">
                        あなたが選ぶと予測した意見（意見 {prediction.get('predicted_opinion_id')}）
                    </div>
                    <div style="font-size: 14.5px; font-weight: 600; color: #1F2937; line-height: 1.6;">
                        {prediction.get('predicted_opinion_text')}
                    </div>
                </div>
                <div style="font-size: 13.5px; color: #374151; line-height: 1.6;">
                    <strong style="color: #1F2937;">予測理由：</strong>{prediction.get('prediction_reason')}
                </div>
                <div style="font-size: 12px; color: #64748B; margin-top: 8px;">
                    ※過去の回答から推測した仮説です。次のフォームであなたの実際の考えを自由に選んでください。
                </div>
            </div>
            """
        ).strip()
        st.markdown(pred_box_html, unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 5. あなたの考えを教えてください（選択フォーム）
    # -------------------------------------------------------------------------
    opinion_form_title_html = textwrap.dedent(
        """
        <div style="margin: 36px 0 16px 0;">
            <h2 style="font-size: 20px; font-weight: 700; color: #1F2937; margin: 0 0 4px 0;">
                あなたの考えを教えてください
            </h2>
            <p style="font-size: 13.5px; color: #475569; margin: 0;">
                10個の意見の中から、最も自分の考えに近いものを1つ選んでください。
            </p>
        </div>
        """
    ).strip()
    st.markdown(opinion_form_title_html, unsafe_allow_html=True)

    # 選択肢の組み立て
    opinion_options = {}
    for idx, opinion in enumerate(gradient_opinions, start=1):
        opinion_options[str(idx)] = str(opinion)

    for idx, item in enumerate(alt_perspectives, start=8):
        opinion_options[str(idx)] = (
            f"【{item.get('perspective')}】{item.get('opinion')}"
        )

    opinion_options["none"] = "該当する意見がない"

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
            "選択した意見への訂正・補足、または自分の考え（任意）",
            placeholder=(
                "例：基本的には賛成だが、費用面については慎重に考えるべきだと思う。"
            ),
            height=120,
            key=correction_key,
        )

        already_saved = (
            st.session_state.get("opinion_response", {}).get("correction_id") is not None
            and st.session_state.get("opinion_response", {}).get("news_id") == news_id
        )

        submitted = st.form_submit_button(
            "次へ進む（確認・訂正へ） →",
            type="primary",
            disabled=already_saved,
            use_container_width=True,
        )

    if submitted:
        if selected_opinion_id is None:
            st.warning("意見を1つ選択してください。")
        elif selected_opinion_id == "none" and not correction_text.strip():
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
                    review_result = generate_review(
                        news=selected_news,
                        selected_opinion_id=selected_opinion_id,
                        selected_opinion_text=selected_opinion_text,
                        correction_text=correction_text,
                        prediction=st.session_state.opinion_prediction,
                    )

                st.session_state.pending_opinion_response = {
                    "news_id": news_id,
                    "selected_opinion_id": selected_opinion_id,
                    "selected_opinion_text": selected_opinion_text,
                    "correction_text": correction_text.strip(),
                }
                st.session_state.review_result = review_result
                st.session_state.review_mode = True
                st.rerun()

            except Exception as e:
                st.error(f"確認用の文章生成に失敗しました：{e}")
