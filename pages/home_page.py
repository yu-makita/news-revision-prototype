# -*- coding: utf-8 -*-
"""
ニュース推薦・選択画面 (Home Page)
AIが推薦したニュース1件と、その他の候補ニュース9件を表示し、
ユーザーが興味のある記事を1件選択（または該当なしを選択）する。
"""

import random
import textwrap
import streamlit as st

from database import (
    get_user,
    get_seen_news_ids,
    save_news_history,
    generate_session_id,
    save_session,
    get_daily_news,
    get_all_daily_news,
    get_selected_news_ids,
)

from news_recommender import (
    recommend_from_saved_news,
    RecommendationError,
)

from pinecone_client import save_memory

from ui_common import (
    inject_custom_css,
    render_common_header,
    get_category_badge_html,
)

TARGET_CATEGORIES = [
    "国内",
    "国際",
    "経済",
    "エンタメ",
    "スポーツ",
    "IT",
    "科学",
    "ライフ",
    "地域",
]


# 保存済みニュースから最新日優先・過去日補充・偏りを抑えて10件抽出する関数
def select_balanced_10_news(
    all_daily_news: list[dict],
    read_news_ids: set[str],
) -> list[dict]:
    """
    daily_news に保存されている最新日付の未読記事を最優先し、10件を抽出する。
    - 最新日付の未読記事が不足する場合、1つ前の日付、さらに過去の日付へとさかのぼって補充する
    - 既読判定にはログイン中ユーザーのニュース選択履歴（read_news_ids）を使用
    - 同じ記事が複数日付に存在する場合は news_id で重複を除外（最新日付を優先）
    - 原則として9カテゴリから各1件を選出し、残り1件も最新日付優先の未読から選出
    """
    if not all_daily_news:
        return []

    # 1. 保存されている日付を抽出し、新しい順（降順）にソート
    dates = sorted(
        list({
            str(r.get("batch_date", "")).strip()
            for r in all_daily_news
            if str(r.get("batch_date", "")).strip()
        }),
        reverse=True,
    )

    if not dates:
        return []

    # 2. 日付降順に未読記事を分類（同一news_idが複数日付にあれば最新日付優先で重複除外）
    seen_in_pool: set[str] = set()
    unread_by_date: dict[str, list[dict]] = {}
    unread_by_date_cat: dict[str, dict[str, list[dict]]] = {}

    for d in dates:
        unread_by_date[d] = []
        unread_by_date_cat[d] = {cat: [] for cat in TARGET_CATEGORIES}

    for d in dates:
        day_records = [
            r for r in all_daily_news
            if str(r.get("batch_date", "")).strip() == d
        ]
        for news in day_records:
            nid = str(news.get("news_id", "")).strip()
            if not nid:
                continue

            # 既読記事（過去の選択履歴に存在）は除外
            if nid in read_news_ids:
                continue

            # すでに新しい日付で登録済みの同一記事は重複除外
            if nid in seen_in_pool:
                continue

            seen_in_pool.add(nid)
            unread_by_date[d].append(news)

            cat = str(news.get("category", "")).strip()
            if cat in unread_by_date_cat[d]:
                unread_by_date_cat[d][cat].append(news)

    # 3. 候補選出
    selected: list[dict] = []
    selected_ids: set[str] = set()

    # (A) 原則9カテゴリから各1件選出（最新日付の未読から順に探索）
    for cat in TARGET_CATEGORIES:
        for d in dates:
            candidates = [
                n for n in unread_by_date_cat[d].get(cat, [])
                if str(n.get("news_id")) not in selected_ids
            ]
            if candidates:
                picked = random.choice(candidates)
                selected.append(picked)
                selected_ids.add(str(picked.get("news_id")))
                break  # このカテゴリは選出完了、次のカテゴリへ

    # (B) 残り（10件に達するまで）を未読記事から選出（最新日付から順に補充）
    for d in dates:
        if len(selected) >= 10:
            break
        candidates = [
            n for n in unread_by_date[d]
            if str(n.get("news_id")) not in selected_ids
        ]
        # シャッフルして選出
        random.shuffle(candidates)
        for n in candidates:
            if len(selected) >= 10:
                break
            selected.append(n)
            selected_ids.add(str(n.get("news_id")))

    # 順序をランダムにシャッフル
    random.shuffle(selected)
    return selected


# ユーザーのニュース選択を確定して保存し分身AIへ遷移する関数
def handle_news_selection(
    selected_value: str,
    all_news: list[dict],
    recommended: dict,
):
    """
    ユーザーが記事（または「読みたいニュースがない」）を選択した際の保存・遷移処理。
    既存の保存ロジック（sessions, Pinecone）および画面遷移を完全維持する。
    """
    NONE_SELECTED_VALUE = "__NONE__"

    if "current_session_id" not in st.session_state:
        st.error("セッション情報を取得できませんでした。")
        return

    none_selected = (selected_value == NONE_SELECTED_VALUE)
    selected_news_id = "" if none_selected else selected_value
    recommended_news_id = recommended.get("news_id", "")

    # sessions シートに保存
    save_session(
        session_id=st.session_state.current_session_id,
        user_id=st.session_state.user_id,
        recommended_news_id=recommended_news_id,
        selected_news_id=selected_news_id,
        none_selected=none_selected,
    )

    # 提示された全ニュースのタイトル一覧
    presented_titles = [
        str(news.get("title", ""))
        for news in all_news
    ]

    # Pineconeに保存するメタデータ
    memory_metadata = {
        "session_id": st.session_state.current_session_id,
        "recommended_news_id": recommended_news_id or "",
        "selected_news_id": selected_news_id,
        "none_selected": none_selected,
        "presented_titles": presented_titles,
    }

    if none_selected:
        memory_text = (
            "【ユーザーの選択行動】\n"
            f"提示された{len(all_news)}件のニュースの中から、"
            "ユーザーはどの記事も選択しなかった。\n"
            "これは今回の提示記事群に対する非選択であり、"
            "各記事への興味がないと断定するものではない。\n\n"
            "【提示されたニュース】\n"
            + "\n".join(
                f"{i}. {title}"
                for i, title in enumerate(presented_titles, start=1)
            )
        )
    else:
        selected_news = next(
            news
            for news in all_news
            if news["news_id"] == selected_news_id
        )

        summary_text = (
            selected_news.get("ai_summary")
            or selected_news.get("summary")
            or ""
        )

        memory_text = (
            "【ユーザーの選択行動】\n"
            f"提示された{len(all_news)}件のニュースの中から、"
            "ユーザーがこの記事を選択した。\n"
            "ただし、1回の選択だけで継続的な興味があるとは断定できない。\n\n"
            "【選択したニュース】\n"
            f"タイトル：{selected_news.get('title', '')}\n"
            f"カテゴリ：{selected_news.get('category', '')}\n"
            f"記事概要：{summary_text}"
        )

    try:
        # Pineconeへ記憶保存
        save_memory(
            memory_id=f"selection-{st.session_state.current_session_id}",
            user_id=st.session_state.user_id,
            memory_type="selection",
            text=memory_text,
            metadata=memory_metadata,
        )
    except Exception as e:
        st.warning(f"Pineconeへの記憶登録に失敗しました：{e}")

    # ニュースを選択した場合は分身AI画面に進む
    if not none_selected:
        st.session_state.selected_news = selected_news
        st.session_state.avatar_mode = True
        st.rerun()
    else:
        st.success("「読みたいニュースがない」を選択しました。今回の選択履歴を保存しました。")


# ログイン後のホーム画面を表示する関数
def show_home_page():
    # 共通CSSを適用
    inject_custom_css()

    # ==========================================
    # 現在のユーザー情報を取得
    # ==========================================
    current_user = get_user(st.session_state.user_id)

    if current_user is None:
        st.error("ユーザー情報を取得できませんでした。")
        st.stop()

    # ==========================================
    # メッセージ表示
    # ==========================================
    if st.session_state.get("profile_updated", False):
        st.success("登録情報を変更しました。")
        del st.session_state.profile_updated

    if "new_user_id" in st.session_state:
        new_user_id = st.session_state.new_user_id
        st.success(
            f"登録が完了しました。あなたの参加者IDは「{new_user_id}」です。"
        )
        st.info("次回利用時に必要になるため、この参加者IDを控えてください。")
        del st.session_state.new_user_id

    # ==========================================
    # 上部ナビゲーション＆ユーザープロファイルバー
    # ==========================================
    nav_col1, nav_col2 = st.columns([1, 2])

    with nav_col1:
        if st.button("← ログイン画面に戻る", key="back_to_login_from_home"):
            st.session_state.user_id = None
            st.session_state.edit_profile = False
            st.session_state.recommendation_result = None
            st.rerun()

    with nav_col2:
        interests_list = current_user.get("interests", [])
        interests_str = ", ".join(interests_list) if interests_list else "未登録"
        big5 = current_user.get("big5", {})

        with st.expander(f"👤 参加者情報: {st.session_state.user_id} (クリックで確認)", expanded=False):
            st.write(f"**興味のある分野**：{interests_str}")
            b_cols = st.columns(5)
            b_cols[0].metric("外向性", big5.get("extraversion", "-"))
            b_cols[1].metric("協調性", big5.get("agreeableness", "-"))
            b_cols[2].metric("勤勉性", big5.get("conscientiousness", "-"))
            b_cols[3].metric("情動性", big5.get("emotionality", "-"))
            b_cols[4].metric("創造性", big5.get("creativity", "-"))

            if st.button("登録情報を変更", key="edit_profile_btn"):
                st.session_state.edit_profile = True
                st.rerun()

    # ==========================================
    # 共通ヘッダー（ステップ1: ニュース選択）
    # ==========================================
    render_common_header(
        title="今日のニュースを選ぶ",
        subtitle="AIがあなたにおすすめのニュースを提案します。気になる記事を1つ選んでください。",
        current_step=1,
    )

    # ==========================================
    # 推薦処理の実行ボタン（まだ推薦結果がない場合）
    # ==========================================
    result = st.session_state.get("recommendation_result")

    if result is None:
        initial_box_html = textwrap.dedent(
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
                <div style="font-size: 42px; margin-bottom: 12px;">📰</div>
                <h2 style="font-size: 22px; font-weight: 700; color: #1F2937; margin-bottom: 8px;">
                    本日のニュースを分析・推薦します
                </h2>
                <p style="font-size: 14.5px; color: #475569; max-width: 540px; margin: 0 auto 24px auto;">
                    保存済みの最新ニュースから、あなたの興味や過去の選択傾向に合わせておすすめ記事を選定します。
                </p>
            </div>
            """
        ).strip()
        st.markdown(initial_box_html, unsafe_allow_html=True)

        if st.button("ニュースを取得・推薦する", type="primary", use_container_width=True):
            try:
                with st.spinner("保存済みのニュースから候補を選び、あなたに合いそうな記事を分析しています..."):
                    all_daily_news = get_all_daily_news()

                    if not all_daily_news:
                        st.error("daily_news シートにニュースが存在しません。")
                        return

                    read_news_ids = get_selected_news_ids(st.session_state.user_id)

                    candidate_10_news = select_balanced_10_news(
                        all_daily_news=all_daily_news,
                        read_news_ids=read_news_ids,
                    )

                    if len(candidate_10_news) < 10:
                        st.error(
                            f"表示可能な未読ニュースが不足しています（抽出件数: {len(candidate_10_news)}件、必要件数: 10件）。"
                            "未読記事が不足しているため、管理者に確認してください。"
                        )
                        return

                    result = recommend_from_saved_news(
                        news_list=candidate_10_news,
                        user_profile=current_user,
                        user_id=st.session_state.user_id,
                    )

                    displayed_news = [
                        result["recommended_news"],
                        *result["other_news"],
                    ]

                    session_id = generate_session_id()
                    st.session_state.current_session_id = session_id

                    save_news_history(
                        st.session_state.user_id,
                        displayed_news,
                        session_id,
                    )

                st.session_state.recommendation_result = result
                st.rerun()

            except RecommendationError as e:
                st.error(f"推薦処理でエラーが発生しました：{e}")
            except Exception as e:
                st.error(f"予期せぬエラーが発生しました：{e}")

        return

    # ==========================================
    # 推薦結果の取得・整理
    # ==========================================
    recommended = result["recommended_news"]
    other_news = result["other_news"]
    all_news = [recommended, *other_news]

    # ==========================================
    # 3-2. AIおすすめ記事（ヒーローカード）
    # ==========================================
    rec_title = recommended.get("title", "タイトルなし")
    rec_url = recommended.get("url", "#")
    rec_category = recommended.get("category", "国内")
    rec_source = recommended.get("source") or "配信元不明"
    rec_reason = result.get("recommendation_reason", "")
    rec_summary = (
        recommended.get("ai_summary")
        or recommended.get("summary")
        or "要約を取得できませんでした。"
    )

    with st.container(border=True):
        # カード上部ラベル
        hero_header_html = textwrap.dedent(
            f"""
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; flex-wrap: wrap; gap: 8px;">
                <div style="
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    background: #EEF2FF;
                    color: #4338CA;
                    border: 1px solid #C7D2FE;
                    padding: 5px 14px;
                    border-radius: 20px;
                    font-size: 13px;
                    font-weight: 700;
                ">
                    ✨ あなたへのおすすめ
                </div>
                <div>{get_category_badge_html(rec_category)}</div>
            </div>
            """
        ).strip()
        st.markdown(hero_header_html, unsafe_allow_html=True)

        # 【上段】タイトル、配信元、選択ボタン
        top_col1, top_col2 = st.columns([3, 1])

        with top_col1:
            hero_title_html = textwrap.dedent(
                f"""
                <h2 style="
                    font-size: 20px;
                    font-weight: 700;
                    line-height: 1.5;
                    margin: 0 0 6px 0;
                    color: #1F2937;
                ">
                    <a href="{rec_url}" target="_blank" style="color: #1F2937; text-decoration: none;">
                        {rec_title}
                    </a>
                </h2>
                <div style="font-size: 13px; color: #475569; margin-bottom: 16px;">
                    配信元：{rec_source}
                </div>
                """
            ).strip()
            st.markdown(hero_title_html, unsafe_allow_html=True)

        with top_col2:
            st.write("")
            if st.button(
                "この記事を選ぶ →",
                key="select_recommended_news",
                type="primary",
                use_container_width=True,
            ):
                handle_news_selection(
                    recommended["news_id"], all_news, recommended
                )

        # 【下段】左側：AIの推薦理由、右側：記事の要約
        bot_col1, bot_col2 = st.columns([1, 1])

        with bot_col1:
            reason_box_html = textwrap.dedent(
                f"""
                <div style="
                    background-color: #EEF2FF;
                    border: 1px solid #C7D2FE;
                    border-radius: 12px;
                    padding: 16px 18px;
                    height: 100%;
                    box-sizing: border-box;
                ">
                    <div style="
                        display: flex;
                        align-items: center;
                        gap: 6px;
                        font-size: 14px;
                        font-weight: 700;
                        color: #3730A3;
                        margin-bottom: 8px;
                    ">
                        🤖 AIの推薦理由
                    </div>
                    <div style="font-size: 13.5px; line-height: 1.65; color: #1F2937;">
                        {rec_reason}
                    </div>
                </div>
                """
            ).strip()
            st.markdown(reason_box_html, unsafe_allow_html=True)

        with bot_col2:
            summary_box_html = textwrap.dedent(
                f"""
                <div style="
                    background-color: #F8FAFC;
                    border: 1px solid #E2E8F0;
                    border-radius: 12px;
                    padding: 16px 18px;
                    height: 100%;
                    box-sizing: border-box;
                ">
                    <div style="
                        display: flex;
                        align-items: center;
                        gap: 6px;
                        font-size: 14px;
                        font-weight: 700;
                        color: #1E293B;
                        margin-bottom: 8px;
                    ">
                        📄 記事の要約
                    </div>
                    <div style="font-size: 13.5px; line-height: 1.65; color: #374151;">
                        {rec_summary}
                    </div>
                </div>
                """
            ).strip()
            st.markdown(summary_box_html, unsafe_allow_html=True)

    # ==========================================
    # 3-3. その他のニュース9件（3列×3行）
    # ==========================================
    other_header_html = textwrap.dedent(
        """
        <div style="margin: 36px 0 16px 0;">
            <h3 style="font-size: 20px; font-weight: 700; color: #1F2937; margin: 0 0 4px 0;">
                他にはこんなニュースがありました
            </h3>
            <p style="font-size: 13.5px; color: #475569; margin: 0;">
                気になる記事を1つ選んでください。
            </p>
        </div>
        """
    ).strip()
    st.markdown(other_header_html, unsafe_allow_html=True)

    for row_start in range(0, len(other_news), 3):
        cols = st.columns(3)

        for col_index, news in enumerate(other_news[row_start : row_start + 3]):
            index = row_start + col_index + 1
            card_title = news.get("title", "タイトルなし")
            card_url = news.get("url", "#")
            card_cat = news.get("category", "")
            card_source = news.get("source") or ""
            card_summary = (
                news.get("ai_summary")
                or news.get("summary")
                or "概要を取得できませんでした。"
            )

            with cols[col_index]:
                with st.container(border=True):
                    # カテゴリバッジと配信元、タイトル、要約
                    card_content_html = textwrap.dedent(
                        f"""
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; gap: 6px;">
                            {get_category_badge_html(card_cat)}
                            <span style="font-size: 12px; color: #475569; white-space: nowrap;">{card_source}</span>
                        </div>
                        <div style="
                            font-size: 15.5px;
                            font-weight: 700;
                            line-height: 1.45;
                            min-height: 46px;
                            margin-bottom: 10px;
                        ">
                            <a href="{card_url}" target="_blank" style="color: #1F2937; text-decoration: none;">
                                {index}. {card_title}
                            </a>
                        </div>
                        <div style="
                            font-size: 13px;
                            color: #374151;
                            line-height: 1.6;
                            min-height: 68px;
                            margin-bottom: 16px;
                        ">
                            {card_summary}
                        </div>
                        """
                    ).strip()
                    st.markdown(card_content_html, unsafe_allow_html=True)

                    # 各カード下部の「この記事を選ぶ」ボタン
                    if st.button(
                        "この記事を選ぶ",
                        key=f"select_other_news_{news['news_id']}_{index}",
                        use_container_width=True,
                    ):
                        handle_news_selection(
                            news["news_id"], all_news, recommended
                        )

    # ==========================================
    # 3-5. 「読みたいニュースがない」独立エリア
    # ==========================================
    none_box_html = textwrap.dedent(
        """
        <div style="
            background: #F8FAFC;
            border: 1px dashed #CBD5E1;
            border-radius: 14px;
            padding: 20px 24px;
            margin-top: 28px;
            margin-bottom: 12px;
        ">
            <div style="font-size: 16px; font-weight: 700; color: #1F2937; margin-bottom: 4px;">
                読みたいニュースがない
            </div>
            <div style="font-size: 13.5px; color: #475569;">
                今回の10件の中に、興味を持てるニュースがない場合はこちらを選んでください。
            </div>
        </div>
        """
    ).strip()
    st.markdown(none_box_html, unsafe_allow_html=True)

    if st.button(
        "「読みたいニュースがない」を選択する",
        key="select_none_news_btn",
        use_container_width=True,
    ):
        handle_news_selection("__NONE__", all_news, recommended)
