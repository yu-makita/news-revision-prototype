# -*- coding: utf-8 -*-
"""
STEP3: ユーザーの基本情報とBig Fiveを用いて、取得済みニュースから表示候補と最推薦を決める。
"""

from __future__ import annotations

import json
import sys

from llm import call_llm

from news_fetcher import (
    fetch_article_text_for_news,
    fetch_yahoo_news_for_recommendation,
)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


DISPLAY_NEWS_COUNT = 10
SUMMARY_ARTICLE_TEXT_MAX_CHARS = 12000

INTEREST_CHOICES = [
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
    "特になし・未回答",
]

BIG5_LABELS = {
    "extraversion": "外向性",
    "agreeableness": "協調性",
    "conscientiousness": "勤勉性",
    "emotionality": "情動性",
    "creativity": "創造性",
}


# ---------------------------------------------------------------------------
# テスト用ユーザー情報
# Streamlit未実装のため、手動確認時は次の辞書を編集する。
# 未回答は None / "" / "未回答" のいずれかでよい。
# interests は複数選択をリストで保持する。「特になし・未回答」も可。
# big5 は BIG5-BASIC のT得点（平均50、標準偏差10）。未診断は None。
# ---------------------------------------------------------------------------
TEST_USER_PROFILE = {
    "age": 21,
    "gender": "未回答",
    "occupation": "大学生",
    "prefecture": "東京都",
    "interests": ["IT・テクノロジー", "科学", "国内"],
    "big5": {
        "extraversion": 48,
        "agreeableness": 55,
        "conscientiousness": 52,
        "emotionality": 50,
        "creativity": 60,
    },
}


class RecommendationError(Exception):
    """推薦処理またはLLM応答の検証に失敗したときに送出する。"""



def _is_unanswered(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() in ("", "未回答"):
        return True
    return False


def _display_value(value) -> str:
    if _is_unanswered(value):
        return "未回答"
    return str(value)


def _normalize_interests(interests) -> list:
    if interests is None:
        return []
    if isinstance(interests, str):
        text = interests.strip()
        return [text] if text else []
    if isinstance(interests, (list, tuple, set)):
        normalized = []
        for item in interests:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                normalized.append(text)
        return normalized
    text = str(interests).strip()
    return [text] if text else []


def format_user_profile_for_prompt(user_profile: dict) -> str:
    profile = user_profile or {}
    interests = _normalize_interests(profile.get("interests"))
    if not interests or interests == ["特になし・未回答"]:
        interests_text = "特になし・未回答"
    else:
        interests_text = "、".join(interests)

    big5 = profile.get("big5") or {}
    big5_lines = []
    for key, label in BIG5_LABELS.items():
        score = big5.get(key)
        if _is_unanswered(score):
            big5_lines.append(f"- {label}: 未回答")
        else:
            big5_lines.append(f"- {label}: {score}（T得点）")

    return "\n".join(
        [
            f"- 年齢: {_display_value(profile.get('age'))}",
            f"- 性別: {_display_value(profile.get('gender'))}",
            f"- 職業: {_display_value(profile.get('occupation'))}",
            f"- 居住地域: {_display_value(profile.get('prefecture'))}",
            f"- 興味のある分野（複数選択可）: {interests_text}",
            "- Big Five（BIG5-BASIC のT得点。平均50、標準偏差10）:",
            *big5_lines,
        ]
    )


def _news_payload_for_ranking(news_list: list[dict]) -> list[dict]:
    payload = []
    for news in news_list:
        payload.append(
            {
                "news_id": news.get("news_id"),
                "category": news.get("category"),
                "title": news.get("title"),
                "summary": news.get("summary"),
            }
        )
    return payload


def _parse_json_text(text: str) -> dict:
    if not text or not text.strip():
        raise RecommendationError("LLMの応答が空です。")

    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RecommendationError(
            f"LLMの応答をJSONとして解析できませんでした: {e}"
        ) from e

    if not isinstance(data, dict):
        raise RecommendationError("LLMの応答がJSONオブジェクトではありません。")
    return data


def validate_recommendation_output(
    raw: dict,
    candidate_ids: list[str],
) -> dict:
    candidate_set = set(candidate_ids)

    recommended = raw.get("recommended_news_id")
    reason = raw.get("recommendation_reason")

    if not isinstance(recommended, str) or not recommended.strip():
        raise RecommendationError("recommended_news_id が空です。")

    recommended_id = recommended.strip()

    if recommended_id not in candidate_set:
        raise RecommendationError(
            f"recommended_news_id が候補ニュースに存在しません: {recommended_id}"
        )

    if not isinstance(reason, str) or not reason.strip():
        raise RecommendationError("recommendation_reason が空です。")

    return {
        "recommended_news_id": recommended_id,
        "recommendation_reason": reason.strip(),
    }

def _build_ranking_prompt(user_profile: dict, news_list: list[dict]) -> str:
    candidate_ids = [str(news.get("news_id")) for news in news_list]

    news_json = json.dumps(
        _news_payload_for_ranking(news_list),
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return f"""あなたはニュース推薦システムです。
与えられた10件の候補ニュースの中から、このユーザーが最も興味を持つ可能性が高い記事を1件だけ選んでください。

# 判断の方針
- 年齢、性別、職業、居住地域、興味のある分野、Big Five、各ニュースの category / title / summary を総合的に見て判断する。
- 「興味のある分野」と同じ category の記事を機械的に選ばない。分野は判断材料の一つとして扱う。
- 性別や Big Five など単一の属性だけから興味を断定しない。
- 未回答の項目は無理に補完しない。
- Big Five はT得点（平均50、標準偏差10）として扱い、極端な解釈は避ける。
- 候補ニュース10件を比較したうえで、最も興味を持つ可能性が高い1件を選ぶ。
- 推薦理由は、なぜ他の候補よりそのニュースに興味を持つと判断したのかが分かるよう、簡潔な日本語で2〜4文程度にする。
- 候補に存在しない news_id は絶対に使用しない。

# ユーザー情報
{format_user_profile_for_prompt(user_profile)}

# 候補ニュース
{news_json}

# 出力
次のJSONだけを返してください。
{{
  "recommended_news_id": "最も興味を持つ可能性が高いニュースのnews_id",
  "recommendation_reason": "そのニュースを選んだ理由"
}}

利用可能な news_id 一覧:
{candidate_ids}
"""


def _request_recommendation(
    user_profile: dict,
    news_list: list[dict],
) -> dict:
    prompt = _build_ranking_prompt(user_profile, news_list)

    try:
        response_text = call_llm(
            prompt,
            json_mode=True,
            temperature=0.3,
        )
    except RecommendationError:
        raise
    except Exception as e:
        raise RecommendationError(
            f"推薦判断のLLM呼び出し中にエラーが発生しました: {e}"
        ) from e

    raw = _parse_json_text(response_text)

    candidate_ids = [
        str(news.get("news_id"))
        for news in news_list
    ]

    return validate_recommendation_output(
        raw,
        candidate_ids,
    )


def _build_summary_prompt(article_source_text: str, used_fallback_summary: bool) -> str:
    source_note = (
        "以下は記事本文ではなく、RSSの概要です。この情報の範囲で要約してください。"
        if used_fallback_summary
        else "以下は記事本文です。"
    )
    return f"""次のニュースについて、読者が「この記事を読むかどうか」を判断できる程度の日本語要約を書いてください。

要件:
- 記事全体の内容が分かるように、十分な情報量を含める。
- 主要な出来事だけでなく、その背景、経緯、具体的な内容、今後の予定など、記事内の重要な情報をできるだけ落とさずまとめる。
- ユーザーが元記事を読まなくても、ニュースの全体像を把握できる程度の要約にする。
- 目安として10〜15文程度、500〜800字程度とする。
- 記事本文またはRSS要約に書かれていない情報を追加しない。
- 意見や評価を勝手に加えない。
- 要約本文だけを返す。見出しや前置きは不要。

{source_note}

{article_source_text}
"""


def summarize_article(news: dict) -> str:
    article_text = news.get("article_text")
    used_fallback = False

    if isinstance(article_text, str) and article_text.strip():
        source_text = article_text.strip()
    else:
        summary = news.get("summary")
        if isinstance(summary, str) and summary.strip():
            source_text = summary.strip()
            used_fallback = True
        else:
            return "記事本文も概要も取得できなかったため、要約できませんでした。"

    if len(source_text) > SUMMARY_ARTICLE_TEXT_MAX_CHARS:
        source_text = source_text[:SUMMARY_ARTICLE_TEXT_MAX_CHARS]

    prompt = _build_summary_prompt(source_text, used_fallback)

    try:
        text = call_llm(
            prompt,
            json_mode=False,
            temperature=0.2,
        )
    except RecommendationError:
        raise
    except Exception as e:
        raise RecommendationError(
            f"記事要約のLLM呼び出し中にエラーが発生しました: {e}"
        ) from e

    text = text.strip()
    if not text:
        raise RecommendationError("記事要約のLLM応答が空です.")
    return text


def _copy_news(news: dict) -> dict:
    return dict(news)


# ユーザー情報をもとに、未表示ニュース10件から最推薦1件を決める関数
def recommend_news(
    user_profile: dict | None = None,
    news_list: list[dict] | None = None,
    display_count: int = DISPLAY_NEWS_COUNT,
    seen_news_ids: set[str] | None = None,
) -> dict:
    """
    既出ニュースを除外した候補から表示ニュースを取得し、
    その中から最推薦1件を決める。

    Returns:
        recommended_news: 最推薦1件
        other_news: 最推薦以外の記事
        selected_news_ids: 表示するニュースのnews_id一覧
        recommended_news_id: 最推薦のnews_id
        recommendation_reason: 最推薦の理由
        article_summary: 最推薦記事の要約
    """

    profile = (
        user_profile
        if user_profile is not None
        else TEST_USER_PROFILE
    )

    # 既出ニュースIDが指定されていなければ空集合にする
    seen_ids = {
        str(news_id)
        for news_id in (seen_news_ids or set())
    }

    # ニュース一覧が外部から渡されていない場合は、
    # 既出ニュースを除外しながらYahoo!ニュースから取得する
    # 各カテゴリから未表示ニュースを1件ずつ取得する
    items = (
        news_list
        if news_list is not None
        else fetch_yahoo_news_for_recommendation(
            exclude_news_ids=seen_ids,
        )
    )

    if not items:
        raise RecommendationError(
            "推薦対象のニュースがありません。"
        )


    # 9カテゴリすべてから1件ずつ取得できたか確認する
    if len(items) < 9:
        raise RecommendationError(
            f"9カテゴリすべてのニュースを取得できませんでした。"
            f"取得できた件数は{len(items)}件です。"
        )

    # news_idが設定されていないニュースがないか確認する
    missing_ids = [
        index
        for index, news in enumerate(items)
        if not news.get("news_id")
    ]

    if missing_ids:
        raise RecommendationError(
            f"news_id が無いニュースがあります。index={missing_ids}"
        )

    # 表示するニュースをコピーする
    selected_items = [
        _copy_news(news)
        for news in items[:display_count]
    ]

    # AIが表示候補から最推薦1件を選ぶ
    ranking = _request_recommendation(
        profile,
        selected_items,
    )

    recommended_id = ranking[
        "recommended_news_id"
    ]

    recommended_news = None
    other_news = []

    # 最推薦1件と、それ以外のニュースに分ける
    for news in selected_items:

        if (
            str(news.get("news_id")) == recommended_id
            and recommended_news is None
        ):
            recommended_news = news

        else:
            other_news.append(news)

    if recommended_news is None:
        raise RecommendationError(
            f"推薦記事を元データに紐付けできませんでした: {recommended_id}"
        )

    # 最推薦された1件だけ記事本文を取得する
    try:
        fetch_article_text_for_news(
            recommended_news
        )

    except Exception as e:
        print(
            f"【警告】最推薦記事の本文取得に失敗しました: {e}",
            file=sys.stderr,
        )

        recommended_news[
            "article_text"
        ] = None

    # 最推薦1件だけAIで本文要約する
    article_summary = summarize_article(
        recommended_news
    )

    reason = ranking[
        "recommendation_reason"
    ]

    recommended_news[
        "recommendation_reason"
    ] = reason

    recommended_news[
        "article_summary"
    ] = article_summary

    # 今回表示するニュースのID一覧を作る
    selected_news_ids = [
        str(news.get("news_id"))
        for news in selected_items
    ]

    return {
        "selected_news_ids": selected_news_ids,
        "recommended_news_id": recommended_id,
        "recommendation_reason": reason,
        "article_summary": article_summary,
        "recommended_news": recommended_news,
        "other_news": other_news,
    }

def display_recommendation_result(result: dict) -> None:
    recommended = result["recommended_news"]

    print("=== 最推薦ニュース ===")
    print(f"news_id: {recommended.get('news_id')}")
    print(f"タイトル: {recommended.get('title')}")
    print(f"カテゴリ: {recommended.get('category')}")
    print(f"配信元: {recommended.get('source')}")
    print(f"URL: {recommended.get('url')}")
    print(f"推薦理由: {result.get('recommendation_reason')}")
    print(f"要約:\n{result.get('article_summary')}")
    print()

    print("=== その他の表示候補 ===")
    for index, news in enumerate(result.get("other_news") or [], start=1):
        print(
            f"{index}. [{news.get('category')}] {news.get('title')} "
            f"(news_id={news.get('news_id')})"
        )


def main():
    print("=== STEP3 ニュース推薦開始 ===")

    try:
        result = recommend_news(user_profile=TEST_USER_PROFILE)
        print()
        display_recommendation_result(result)
    except RecommendationError as e:
        print(f"【推薦エラー】{e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"【予期せぬエラー】{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()