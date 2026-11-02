import random
import streamlit as st

from database import (
    get_user,
    get_seen_news_ids,
    save_news_history,
    generate_session_id,
    save_session,
    get_daily_news,
)

from news_recommender import (
    recommend_from_saved_news,
    RecommendationError,
)

from pinecone_client import save_memory

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


# ==========================================
# 保存済みニュースから偏りを抑えて10件抽出する関数
# ==========================================
def select_balanced_10_news(
    daily_news: list[dict],
    seen_news_ids: set[str],
) -> list[dict]:
    """
    保存済みニュース群から10件を抽出する。
    - ユーザーが過去に表示された記事は優先的に除外
    - 原則として9カテゴリから各1件ずつ選出（計9件）
    - 残り1件を未選出記事からランダムに選出（計10件）
    - 未表示記事が不足する場合のみ、表示済み記事から補填する
    """
    # カテゴリごとに記事を分類
    news_by_category: dict[str, list[dict]] = {}
    for news in daily_news:
        cat = str(news.get("category", "")).strip() or "その他"
        news_by_category.setdefault(cat, []).append(news)

    selected: list[dict] = []
    selected_ids: set[str] = set()

    # 1. 9カテゴリから各1件ずつ選出（未表示優先）
    for cat in TARGET_CATEGORIES:
        cat_items = news_by_category.get(cat, [])
        if not cat_items:
            continue

        unseen_items = [
            n for n in cat_items
            if str(n.get("news_id")) not in seen_news_ids
        ]
        seen_items = [
            n for n in cat_items
            if str(n.get("news_id")) in seen_news_ids
        ]

        # 未表示があれば優先、なければ表示済みから選出
        candidates = unseen_items if unseen_items else seen_items
        available = [
            n for n in candidates
            if str(n.get("news_id")) not in selected_ids
        ]
        if not available:
            available = [
                n for n in cat_items
                if str(n.get("news_id")) not in selected_ids
            ]

        if available:
            picked = random.choice(available)
            selected.append(picked)
            selected_ids.add(str(picked.get("news_id")))

    # 2. 残り（10件に達するまで）を未選出の全記事から選出（未表示優先）
    remaining_all = [
        n for n in daily_news
        if str(n.get("news_id")) not in selected_ids
    ]

    while len(selected) < 10 and remaining_all:
        unseen_remaining = [
            n for n in remaining_all
            if str(n.get("news_id")) not in seen_news_ids
        ]
        if unseen_remaining:
            picked = random.choice(unseen_remaining)
        else:
            picked = random.choice(remaining_all)

        selected.append(picked)
        selected_ids.add(str(picked.get("news_id")))
        remaining_all = [
            n for n in daily_news
            if str(n.get("news_id")) not in selected_ids
        ]

    # 順序をランダムにシャッフル
    random.shuffle(selected)
    return selected


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
    # ニュース推薦ボタン
    # ==========================================
    if st.button(
        "ニュースを取得・推薦する",
        type="primary",
    ):

        try:
            with st.spinner(
                "保存済みのニュースから候補を選び、"
                "あなたに合いそうな記事を分析しています..."
            ):

                # 1. daily_news シートから保存済み最新ニュースを取得
                daily_news_records = get_daily_news()

                # 10件未満の場合はエラー表示
                if len(daily_news_records) < 10:
                    st.error(
                        f"表示可能なニュースが不足しています（取得件数: {len(daily_news_records)}件、必要件数: 10件）。"
                        "毎朝の事前バッチ処理が正常に完了しているか確認してください。"
                    )
                    return

                # 2. このユーザーが過去に表示されたニュースIDを取得
                seen_news_ids = get_seen_news_ids(
                    st.session_state.user_id
                )

                # 3. 9カテゴリ各1件 + ランダム1件（計10件、未表示優先）を抽出
                candidate_10_news = select_balanced_10_news(
                    daily_news=daily_news_records,
                    seen_news_ids=seen_news_ids,
                )

                if len(candidate_10_news) < 10:
                    st.error("10件のニュースを抽出できませんでした。")
                    return

                # 4. 抽出した10件について、既存のAI推薦ロジック（Pinecone RAG + LLM）を実行
                # ※ ニュース取得・本文取得・AI要約は実行せず、保存済みの内容を入力
                result = recommend_from_saved_news(
                    news_list=candidate_10_news,
                    user_profile=current_user,
                    user_id=st.session_state.user_id,
                )

                # 5. 今回ユーザーに表示するニュース10件をまとめる
                displayed_news = [
                    result["recommended_news"],
                    *result["other_news"],
                ]

                # 6. 今回の推薦を識別するセッションIDを生成する
                session_id = generate_session_id()
                st.session_state.current_session_id = session_id

                # 7. 今回表示する10件をニュース履歴（news_history）に保存する
                save_news_history(
                    st.session_state.user_id,
                    displayed_news,
                    session_id,
                )

            # 推薦結果を画面表示用に保存
            st.session_state.recommendation_result = result
            st.success("推薦が完了しました。")

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
    result = st.session_state.get(
        "recommendation_result"
    )

    # 推薦結果がまだなければ、ここでホーム画面の描画を終了
    if result is None:
        return


    # ==========================================
    # 最推薦ニュース（画面上部）
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
        recommended.get("ai_summary")
        or recommended.get("summary")
        or "要約を取得できませんでした。"
    )


    # ==========================================
    # その他のニュース（3列×3行のカード形式）
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

                    card_title = news.get(
                        "title"
                    )

                    card_url = news.get(
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
                                href="{card_url}"
                                target="_blank"
                                style="
                                    color: inherit;
                                    text-decoration: none;
                                "
                            >
                                {index}. 「{card_title}」
                            </a>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    summary = (
                        news.get("ai_summary")
                        or news.get("summary")
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
    # ユーザーが最も興味を持ったニュースを選択する処理
    # ==========================================
    st.divider()

    st.subheader(
        "最も興味を持ったニュースを選んでください"
    )

    # おすすめ1件とその他のニュースをまとめる（計10件）
    all_news = [
        recommended,
        *other_news,
    ]

    st.write(
        f"上の{len(all_news)}件のニュースの中から、"
        "あなたが実際に最も興味を持ったニュースを1つ選んでください。"
    )

    # ==========================================
    # ニュースまたは「該当なし」を選択するフォーム
    # ==========================================
    NONE_SELECTED_VALUE = "__NONE__"

    selection_options = [
        news["news_id"]
        for news in all_news
    ] + [NONE_SELECTED_VALUE]

    with st.form(
        "news_selection_form"
    ):
        selected_value = st.radio(
            "ニュースを選択",
            options=selection_options,
            format_func=lambda value: (
                "興味を持ったニュースはない"
                if value == NONE_SELECTED_VALUE
                else next(
                    f"「{news['title']}」"
                    for news in all_news
                    if news["news_id"] == value
                )
            ),
            index=None,
        )

        submitted = st.form_submit_button(
            "選択を確定",
            type="primary",
        )


    # ==========================================
    # 選択結果をsessionsシートおよびPineconeに保存する
    # ==========================================
    if submitted:

        # 何も選択されていない場合
        if selected_value is None:
            st.error(
                "ニュースまたは「興味を持ったニュースはない」を選択してください。"
            )

        # セッションIDが取得できない場合
        elif "current_session_id" not in st.session_state:
            st.error(
                "セッション情報を取得できませんでした。"
            )

        else:
            # 「興味を持ったニュースはない」が選択されたか判定する
            none_selected = (
                selected_value == NONE_SELECTED_VALUE
            )

            # 記事を選択した場合だけnews_idを保存する
            selected_news_id = (
                ""
                if none_selected
                else selected_value
            )

            # AIが推薦したニュースIDを取得する
            recommended_news_id = recommended.get(
                "news_id"
            )

            # 今回の推薦・選択結果をsessionsシートに保存する
            save_session(
                session_id=st.session_state.current_session_id,
                user_id=st.session_state.user_id,
                recommended_news_id=recommended_news_id,
                selected_news_id=selected_news_id,
                none_selected=none_selected,
            )

            st.success(
                "選択結果を保存しました。"
            )

            # 提示された10件のニュースのタイトルを取得する
            presented_titles = [
                str(news.get("title", ""))
                for news in all_news
            ]

            # Pineconeに保存するメタデータを作成する
            memory_metadata = {
                "session_id": st.session_state.current_session_id,
                "recommended_news_id": recommended_news_id or "",
                "selected_news_id": selected_news_id,
                "none_selected": none_selected,
                "presented_titles": presented_titles,
            }

            if none_selected:
                # どのニュースも選ばなかった事実を記憶する
                memory_text = (
                    "【ユーザーの選択行動】\n"
                    f"提示された{len(all_news)}件のニュースの中から、"
                    "ユーザーはどの記事も選択しなかった。\n"
                    "これは今回の提示記事群に対する非選択であり、"
                    "各記事への興味がないと断定するものではない。\n\n"
                    "【提示されたニュース】\n"
                    + "\n".join(
                        f"{i}. {title}"
                        for i, title in enumerate(
                            presented_titles, start=1
                        )
                    )
                )

            else:
                # ユーザーが選択したニュースを取得する
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

                # 選択行動と記事内容を記憶する
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
                # ニュース選択履歴をPineconeに登録する
                save_memory(
                    memory_id=f"selection-{st.session_state.current_session_id}",
                    user_id=st.session_state.user_id,
                    memory_type="selection",
                    text=memory_text,
                    metadata=memory_metadata,
                )

            except Exception as e:
                st.warning(
                    f"Pineconeへの記憶登録に失敗しました：{e}"
                )

            # ニュースを選択した場合は分身AI画面に進む
            if not none_selected:
                st.session_state.selected_news = selected_news
                st.session_state.avatar_mode = True
                st.rerun()
