# -*- coding: utf-8 -*-
"""
STEP3: ユーザーの基本情報とBig Fiveを用いて、取得済みニュースから表示候補と最推薦を決める。
"""

from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from news_fetcher import fetch_article_text_for_news, fetch_yahoo_news

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

GEMINI_MODEL = "gemini-3.5-flash"
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

RECOMMENDATION_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "selected_news_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "recommended_news_id": {"type": "string"},
        "recommendation_reason": {"type": "string"},
    },
    "required": [
        "selected_news_ids",
        "recommended_news_id",
        "recommendation_reason",
    ],
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
    """推薦処理またはGemini応答の検証に失敗したときに送出する。"""


def create_gemini_client() -> genai.Client:
    """STEP1と同様に .env の GEMINI_API_KEY からクライアントを作る。"""
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RecommendationError(
            "GEMINI_API_KEY が設定されていません。.env を確認してください。"
        )
    if api_key == "your_gemini_api_key_here":
        raise RecommendationError(
            ".env の GEMINI_API_KEY が初期値のままです。実際のAPIキーを設定してください。"
        )

    return genai.Client(api_key=api_key)


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
        raise RecommendationError("Geminiの応答が空です。")

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
        raise RecommendationError(f"Geminiの応答をJSONとして解析できませんでした: {e}") from e

    if not isinstance(data, dict):
        raise RecommendationError("Geminiの応答がJSONオブジェクトではありません。")
    return data


def validate_recommendation_output(
    raw: dict,
    candidate_ids: list[str],
    expected_count: int,
) -> dict:
    problems: list[str] = []
    candidate_set = set(candidate_ids)

    selected = raw.get("selected_news_ids")
    recommended = raw.get("recommended_news_id")
    reason = raw.get("recommendation_reason")

    if not isinstance(selected, list):
        raise RecommendationError(
            "推薦結果の検証に失敗しました。\n"
            "- selected_news_ids が配列ではありません。"
        )

    unknown_ids: list[str] = []
    duplicate_ids: list[str] = []
    cleaned_ids: list[str] = []
    seen: set[str] = set()

    for item in selected:
        news_id = str(item).strip() if item is not None else ""
        if not news_id:
            unknown_ids.append("(空のID)")
            continue
        if news_id not in candidate_set:
            unknown_ids.append(news_id)
            continue
        if news_id in seen:
            duplicate_ids.append(news_id)
            continue
        seen.add(news_id)
        cleaned_ids.append(news_id)

    if unknown_ids:
        problems.append(f"候補に存在しないnews_idが含まれています: {unknown_ids}")
    if duplicate_ids:
        problems.append(f"同じnews_idが重複しています: {duplicate_ids}")
    if len(cleaned_ids) != expected_count:
        problems.append(
            f"有効な選択件数が {expected_count} 件ではなく {len(cleaned_ids)} 件です。"
            f" 有効なnews_id: {cleaned_ids}"
        )

    if not isinstance(recommended, str) or not recommended.strip():
        problems.append("recommended_news_id が空です。")
        recommended_id = ""
    else:
        recommended_id = recommended.strip()
        if recommended_id not in candidate_set:
            problems.append(
                f"recommended_news_id が候補ニュースに存在しません: {recommended_id}"
            )
        elif recommended_id not in cleaned_ids:
            problems.append(
                f"recommended_news_id が selected_news_ids の有効な10件（または指定件数）に含まれていません: {recommended_id}"
            )

    if not isinstance(reason, str) or not reason.strip():
        problems.append("recommendation_reason が空です。")
        reason_text = ""
    else:
        reason_text = reason.strip()

    if problems:
        raise RecommendationError(
            "推薦結果の検証に失敗しました。\n" + "\n".join(f"- {item}" for item in problems)
        )

    return {
        "selected_news_ids": cleaned_ids,
        "recommended_news_id": recommended_id,
        "recommendation_reason": reason_text,
    }


def _build_ranking_prompt(user_profile: dict, news_list: list[dict], select_count: int) -> str:
    candidate_ids = [str(news.get("news_id")) for news in news_list]
    news_json = json.dumps(_news_payload_for_ranking(news_list), ensure_ascii=False, indent=2)

    return f"""あなたはニュース推薦システムです。
与えられた候補ニュースの中から、このユーザーが興味を持ちそうな記事を {select_count} 件選び、
その中で最も興味を持つ可能性が高い 1 件を推薦してください。

# 判断の方針
- 年齢、性別、職業、居住地域、興味のある分野（複数）、Big Five、各ニュースの category / title / summary を総合的に見て判断する。
- 「興味のある分野」と同じ category の記事だけを機械的に選ばない。分野は手がかりの一つにすぎない。
- 性別や Big Five など単一の属性から、「この人は必ずこの種のニュースに興味がある」と断定しない。
- 未回答の項目は無理に補完して決めつけない。分かっている情報だけを使う。
- Big Five はT得点（平均50、標準偏差10）である。極端な解釈は避ける。
- 推薦理由は、後でユーザー画面に出すため、簡潔で自然な日本語にする（2〜4文程度）。
- 候補に無い news_id は使わない。同じ news_id を繰り返さない。

# ユーザー情報
{format_user_profile_for_prompt(user_profile)}

# 候補ニュース（この news_id だけを使う）
{news_json}

# 出力
次のJSONだけを返す。
- selected_news_ids: 選んだ {select_count} 件の news_id。順序は、先頭ほど興味を持ちそう、でよい。
- recommended_news_id: selected_news_ids のうち最もおすすめの 1 件。必ず selected_news_ids に含める。
- recommendation_reason: その 1 件を推薦する理由（日本語）。

利用可能な news_id 一覧: {candidate_ids}
"""


def _request_recommendation(
    client: genai.Client,
    user_profile: dict,
    news_list: list[dict],
    select_count: int,
) -> dict:
    prompt = _build_ranking_prompt(user_profile, news_list, select_count)
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RECOMMENDATION_RESPONSE_SCHEMA,
                temperature=0.3,
            ),
        )
    except errors.APIError as e:
        raise RecommendationError(f"推薦判断のGemini API呼び出しに失敗しました: {e}") from e
    except Exception as e:
        raise RecommendationError(f"推薦判断のGemini API呼び出し中にエラーが発生しました: {e}") from e

    raw = _parse_json_text(response.text or "")
    candidate_ids = [str(news.get("news_id")) for news in news_list]
    return validate_recommendation_output(raw, candidate_ids, select_count)


def _build_summary_prompt(article_source_text: str, used_fallback_summary: bool) -> str:
    source_note = (
        "以下は記事本文ではなく、RSSの概要です。この情報の範囲で要約してください。"
        if used_fallback_summary
        else "以下は記事本文です。"
    )
    return f"""次のニュースについて、読者が「この記事を読むかどうか」を判断できる程度の日本語要約を書いてください。

要件:
- 短すぎる一文要約にしない。
- 主要な内容・出来事・論点が分かるようにする。
- 3〜6文程度。
- 記事本文またはRSS要約に書かれていない情報を追加しない。
- 意見や評価を勝手に加えない。
- 要約本文だけを返す。見出しや前置きは不要。

{source_note}

{article_source_text}
"""


def summarize_article(client: genai.Client, news: dict) -> str:
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
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2),
        )
    except errors.APIError as e:
        raise RecommendationError(f"記事要約のGemini API呼び出しに失敗しました: {e}") from e
    except Exception as e:
        raise RecommendationError(f"記事要約のGemini API呼び出し中にエラーが発生しました: {e}") from e

    text = (response.text or "").strip()
    if not text:
        raise RecommendationError("記事要約のGemini応答が空です。")
    return text


def _copy_news(news: dict) -> dict:
    return dict(news)


def recommend_news(
    user_profile: dict | None = None,
    news_list: list[dict] | None = None,
    client: genai.Client | None = None,
    display_count: int = DISPLAY_NEWS_COUNT,
) -> dict:
    """
    ニュース候補から表示用の件数を選び、最推薦1件とその要約を返す。

    Returns:
        recommended_news: 最推薦1件（元ニュースの全フィールド + recommendation_reason / article_summary）
        other_news: 残りの表示候補（元ニュースの全フィールド。本文要約は付けない）
        selected_news_ids: 表示候補の news_id 一覧
        recommended_news_id: 最推薦の news_id
        recommendation_reason: 最推薦の理由
        article_summary: 最推薦記事の要約
    """
    profile = user_profile if user_profile is not None else TEST_USER_PROFILE
    items = news_list if news_list is not None else fetch_yahoo_news()

    if not items:
        raise RecommendationError("推薦対象のニュースがありません。")

    missing_ids = [index for index, news in enumerate(items) if not news.get("news_id")]
    if missing_ids:
        raise RecommendationError(f"news_id が無いニュースがあります。index={missing_ids}")

    select_count = min(display_count, len(items))
    gemini_client = client if client is not None else create_gemini_client()

    ranking = _request_recommendation(gemini_client, profile, items, select_count)
    news_by_id = {str(news.get("news_id")): news for news in items}

    selected_items = []
    for news_id in ranking["selected_news_ids"]:
        selected_items.append(_copy_news(news_by_id[news_id]))

    recommended_id = ranking["recommended_news_id"]
    recommended_news = None
    other_news = []
    for news in selected_items:
        if str(news.get("news_id")) == recommended_id and recommended_news is None:
            recommended_news = news
        else:
            other_news.append(news)

    if recommended_news is None:
        raise RecommendationError(
            f"推薦記事を元データに紐付けできませんでした: {recommended_id}"
        )

    try:
        fetch_article_text_for_news(recommended_news)
    except Exception as e:
        print(f"【警告】最推薦記事の本文取得に失敗しました: {e}", file=sys.stderr)
        recommended_news["article_text"] = None

    article_summary = summarize_article(gemini_client, recommended_news)
    reason = ranking["recommendation_reason"]
    recommended_news["recommendation_reason"] = reason
    recommended_news["article_summary"] = article_summary

    return {
        "selected_news_ids": ranking["selected_news_ids"],
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
