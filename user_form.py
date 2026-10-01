import streamlit as st

def show_user_registration_form():

    st.subheader("新規登録")

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
        "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県",
        "福島県", "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県",
        "東京都", "神奈川県", "新潟県", "富山県", "石川県", "福井県",
        "山梨県", "長野県", "岐阜県", "静岡県", "愛知県", "三重県",
        "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
        "鳥取県", "島根県", "岡山県", "広島県", "山口県", "徳島県",
        "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
        "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
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
            big5_options,
            format_func=format_big5,
        )

    with col2:
        agreeableness = st.selectbox(
            "協調性",
            big5_options,
            format_func=format_big5,
        )

    with col3:
        conscientiousness = st.selectbox(
            "勤勉性",
            big5_options,
            format_func=format_big5,
        )

    with col4:
        emotionality = st.selectbox(
            "情動性",
            big5_options,
            format_func=format_big5,
        )

    with col5:
        creativity = st.selectbox(
            "創造性",
            big5_options,
            format_func=format_big5,
        )

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

    return user_profile


def show_user_edit_form(current_user):

    st.subheader("登録情報の変更")

    age_options = list(range(0, 101)) + [None]

    current_age = current_user.get("age")
    age_index = (
        age_options.index(current_age)
        if current_age in age_options
        else 0
    )

    age = st.selectbox(
        "年齢",
        options=age_options,
        index=age_index,
        format_func=lambda x: "回答しない" if x is None else f"{x}歳",
        key="edit_age",
    )

    gender_options = ["未選択", "男性", "女性", "その他"]

    current_gender = current_user.get("gender")

    gender = st.selectbox(
        "性別",
        gender_options,
        index=gender_options.index(current_gender)
        if current_gender in gender_options else 0,
        key="edit_gender",
    )

    occupation_options = [
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
    ]

    current_occupation = current_user.get("occupation")

    # 選択肢にない職業は「その他」
    if current_occupation in occupation_options:
        occupation_index = occupation_options.index(current_occupation)
    else:
        occupation_index = occupation_options.index("その他")

    occupation_choice = st.selectbox(
        "職業",
        occupation_options,
        index=occupation_index,
        format_func=lambda x: "回答しない" if x is None else x,
        key="edit_occupation_choice",
    )

    if occupation_choice == "その他":
        occupation = st.text_input(
            "職業を入力してください",
            value=(
                current_occupation
                if current_occupation not in occupation_options
                else ""
            ),
            key="edit_occupation_text",
        )
    else:
        occupation = occupation_choice

    prefectures = [
        "未選択",
        "北海道", "青森県", "岩手県", "宮城県", "秋田県",
        "山形県", "福島県", "茨城県", "栃木県", "群馬県",
        "埼玉県", "千葉県", "東京都", "神奈川県", "新潟県",
        "富山県", "石川県", "福井県", "山梨県", "長野県",
        "岐阜県", "静岡県", "愛知県", "三重県", "滋賀県",
        "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
        "鳥取県", "島根県", "岡山県", "広島県", "山口県",
        "徳島県", "香川県", "愛媛県", "高知県", "福岡県",
        "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県",
        "鹿児島県", "沖縄県", "海外", "回答しない",
    ]

    current_prefecture = current_user.get("prefecture")

    prefecture = st.selectbox(
        "居住地",
        prefectures,
        index=prefectures.index(current_prefecture)
        if current_prefecture in prefectures else 0,
        key="edit_prefecture",
    )

    interest_options = [
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
    ]

    interests = st.multiselect(
        "興味のある分野",
        interest_options,
        default=current_user.get("interests", []),
        key="edit_interests",
    )

    st.subheader("Big Five")
    st.caption("BIG5-BASICのT得点を入力してください。")

    big5 = current_user.get("big5", {})
    big5_options = list(range(0, 101)) + [None]

    def big5_input(label, field):
        current_value = big5.get(field)

        index = (
            big5_options.index(current_value)
            if current_value in big5_options
            else 0
        )

        return st.selectbox(
            label,
            big5_options,
            index=index,
            format_func=lambda x: "回答しない" if x is None else str(x),
            key=f"edit_{field}",
        )

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        extraversion = big5_input("外向性", "extraversion")

    with col2:
        agreeableness = big5_input("協調性", "agreeableness")

    with col3:
        conscientiousness = big5_input("勤勉性", "conscientiousness")

    with col4:
        emotionality = big5_input("情動性", "emotionality")

    with col5:
        creativity = big5_input("創造性", "creativity")

    return {
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