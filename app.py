import streamlit as st
from news_recommender import recommend_news, RecommendationError

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

st.subheader("ユーザー情報")

age = st.selectbox(
    "年齢",
    options=list(range(0, 101)) + [None],
    format_func=lambda x: "回答しない" if x is None else f"{x}歳",
)

gender = st.selectbox(
    "性別",
    ["未選択", "男性", "女性", "その他"],
)

occupation_choice = st.selectbox(
    "職業",
    options=[
        "未選択",
        "製造業",
        "建設業",
        "情報通信（IT・通信・マスコミ）",
        "卸売・小売・流通",
        "金融・保険・不動産",
        "医療・福祉",
        "飲食・宿泊・サービス",
        "教育・公務・団体",
        "学生",
        "専業主婦・主夫",
        "無職・求職中",
        "その他",
        None,
    ],
    format_func=lambda x: "回答しない" if x is None else x,
)

if occupation_choice == "その他":
    occupation = st.text_input(
        "職業を入力してください",
        placeholder="例：フリーランス、農業など",
    )
else:
    occupation = occupation_choice

prefectures = [
    "未選択",
    "北海道",
    "青森県",
    "岩手県",
    "宮城県",
    "秋田県",
    "山形県",
    "福島県",
    "茨城県",
    "栃木県",
    "群馬県",
    "埼玉県",
    "千葉県",
    "東京都",
    "神奈川県",
    "新潟県",
    "富山県",
    "石川県",
    "福井県",
    "山梨県",
    "長野県",
    "岐阜県",
    "静岡県",
    "愛知県",
    "三重県",
    "滋賀県",
    "京都府",
    "大阪府",
    "兵庫県",
    "奈良県",
    "和歌山県",
    "鳥取県",
    "島根県",
    "岡山県",
    "広島県",
    "山口県",
    "徳島県",
    "香川県",
    "愛媛県",
    "高知県",
    "福岡県",
    "佐賀県",
    "長崎県",
    "熊本県",
    "大分県",
    "宮崎県",
    "鹿児島県",
    "沖縄県",
    "海外",
    "回答しない",
]

prefecture = st.selectbox(
    "居住地",
    prefectures,
)

interests = st.multiselect(
    "興味のある分野",
    [
        "国内",
        "国際",
        "経済",
        "エンタメ",
        "スポーツ",
        "IT・テクノロジー",
        "科学",
        "ライフ",
        "地域",
        "その他",
    ],
)

st.subheader("Big Five")

st.caption("BIG5-BASICのT得点を入力してください。")

big5_options = list(range(0, 101)) + [None]

def format_big5(value):
    return "回答しない" if value is None else str(value)

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    extraversion = st.selectbox(
        "外向性",
        options=big5_options,
        format_func=format_big5,
        key="extraversion",
    )

with col2:
    agreeableness = st.selectbox(
        "協調性",
        options=big5_options,
        format_func=format_big5,
        key="agreeableness",
    )

with col3:
    conscientiousness = st.selectbox(
        "勤勉性",
        options=big5_options,
        format_func=format_big5,
        key="conscientiousness",
    )

with col4:
    emotionality = st.selectbox(
        "情動性",
        options=big5_options,
        format_func=format_big5,
        key="emotionality",
    )

with col5:
    creativity = st.selectbox(
        "創造性",
        options=big5_options,
        format_func=format_big5,
        key="creativity",
    )

# 推薦結果を保存するための初期設定
if "recommendation_result" not in st.session_state:
    st.session_state.recommendation_result = None


# 「ニュースを取得・推薦する」ボタンを押したときだけ実行
if st.button("ニュースを取得・推薦する"):

    # 画面で入力された情報からユーザープロフィールを作成
    user_profile = {
        "age": age,
        "gender": gender,
        "occupation": occupation,
        "prefecture": prefecture,
        "interests": interests,
        "big5": {
            "extraversion": extraversion,
            "agreeableness": agreeableness,
            "conscientiousness": conscientiousness,
            "emotionality": emotionality,
            "creativity": creativity,
        },
    }

    try:
        with st.spinner(
            "ニュースを取得して、あなたに合いそうな記事を選んでいます..."
        ):
            result = recommend_news(
                user_profile=user_profile
            )

        # 推薦結果を保存
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


# 保存済みの推薦結果を取得
result = st.session_state.recommendation_result


# 推薦結果がある場合だけニュースを表示
if result is not None:

    recommended = result["recommended_news"]

    # ↓ここから現在の
    # 「あなたへのおすすめ」
    # 以降の表示コードをそのまま置く

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