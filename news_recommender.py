# -*- coding: utf-8 -*-
"""
STEP3: ユーザーの基本情報とBig Fiveを用いて、取得済みニュースから表示候補と最推薦を決める。
"""

from __future__ import annotations

import json
import sys
import time
from batch_news_summarizer import prepare_news_summaries

from llm import call_llm
from pinecone_client import search_memories

from news_fetcher import (
    fetch_article_text_for_news,
    fetch_yahoo_news_for_recommendation,
)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


DISPLAY_NEWS_COUNT = 9
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


# ニュース推薦用に各記事へ番号を付ける関数
def _news_payload_for_ranking(news_list: list[dict]) -> list[dict]:
    payload = []

    for number, news in enumerate(news_list, start=1):
        payload.append(
            {
                "number": number,
                "category": news.get("category"),
                "title": news.get("title"),
                "summary": news.get("ai_summary") or news.get("summary"),
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


# AIが返した推薦番号を検証し、元のニュースIDに変換する関数
def validate_recommendation_output(
    raw: dict,
    candidate_ids: list[str],
) -> dict:
    number = raw.get("recommended_number")
    reason = raw.get("recommendation_reason")

    # 1〜候補件数の整数であることを確認
    if (
        type(number) is not int
        or not 1 <= number <= len(candidate_ids)
    ):
        raise RecommendationError(
            f"推薦番号が不正です: {number}"
        )

    if not isinstance(reason, str) or not reason.strip():
        raise RecommendationError(
            "recommendation_reason が空です。"
        )

    # AIの番号をPython側でニュースIDに変換
    recommended_id = candidate_ids[number - 1]

    return {
        "recommended_news_id": recommended_id,
        "recommendation_reason": reason.strip(),
    }



# 今回のニュース候補に関連する過去の選択履歴をRAGで取得する関数
def retrieve_recommendation_memories(
    user_id: str,
    news_list: list[dict],
) -> str:
    # 今回の候補ニュースを検索クエリにまとめる
    query_parts = []

    for news in news_list:
        query_parts.append(
            f"カテゴリ：{news.get('category', '')}\n"
            f"タイトル：{news.get('title', '')}\n"
            f"概要：{news.get('ai_summary') or news.get('summary') or ''}"
        )

    query_text = "\n\n".join(query_parts)

    # 過去のニュース選択履歴を検索する
    search_results = search_memories(
        user_id=user_id,
        query_text=query_text,
        memory_type="selection",
        top_k=5,
    )

    # Pineconeの検索結果を辞書に変換する
    if hasattr(search_results, "to_dict"):
        search_data = search_results.to_dict()
    else:
        search_data = dict(search_results)

    hits = search_data.get("result", {}).get("hits", [])

    memory_texts = []

    for hit in hits:
        fields = hit.get("fields", {})
        text = fields.get("text", "")

        if text:
            memory_texts.append(text)

    # 過去の選択履歴がない場合
    if not memory_texts:
        return "過去のニュース選択履歴はありません。"

    # 取得した記憶をプロンプトに渡せる形にする
    return "\n\n---\n\n".join(memory_texts)



# ニュース推薦用のプロンプトを作成する関数
def _build_ranking_prompt(
    user_profile: dict,
    news_list: list[dict],
    past_memories: str,
) -> str:
    news_json = json.dumps(
        _news_payload_for_ranking(news_list),
        ensure_ascii=False,
        separators=(",", ":"),
    )

    
    return f"""
あなたは、ユーザーの興味・関心を推測するニュース推薦AIです。
ユーザーの基本情報と過去のニュース選択履歴をもとに、
{len(news_list)}件の候補ニュースから、最も読みたいと思う可能性が高い記事を1件推薦してください。

【ユーザーの基本情報】
{format_user_profile_for_prompt(user_profile)}

【過去のニュース選択履歴（RAG検索結果）】
{past_memories}

【今回の候補ニュース】
{news_json}

【タスク】
以下の順番で判断してください。

1. ユーザーの興味・関心の推測
過去のニュース選択履歴から、ユーザーが関心を示した話題や記事の特徴を推測する。
単なるカテゴリだけでなく、記事の具体的な内容やテーマにも注目する。
基本情報（興味のある分野、職業、居住地域、年齢、Big Fiveなど）も補助的に考慮する。

2. 候補ニュースの比較
今回の候補ニュースをそれぞれ確認し、
推測した興味・関心との関連性を比較する。
過去に選択した記事とカテゴリが異なっていても、
内容やテーマに共通点があれば考慮する。

3. 最推薦ニュースの決定
ユーザーが最も興味を持ち、実際に読みたいと思う可能性が高い記事を1件選ぶ。
その記事を選んだ理由を、過去の選択履歴や基本情報との関連性から説明する。

【推測・推薦のルール】
- 過去の実際の選択行動を、基本情報からの推測よりも優先する。
- 過去の選択履歴はRAGで取得した一部の記憶であり、ユーザーの全履歴ではない。
- 選択した記事は興味・関心の手掛かりとするが、1回の選択だけで継続的な関心があるとは断定しない。
- どの記事も選択しなかった履歴は、その提示記事群に対する非選択として扱い、個々の記事や分野への無関心とは断定しない。
- 過去の選択履歴と今回の候補ニュースの関連性が弱い場合は、無理に共通点を作らない。
- 興味のある分野と同じカテゴリの記事を機械的に推薦せず、具体的な内容を比較する。
- 年齢、性別、職業、居住地域、Big Fiveなどの単一の属性だけで興味を決めつけない。
- Big FiveはT得点（平均50、標準偏差10）として扱い、極端な解釈を避ける。
- 未回答の情報を勝手に補完しない。
- 過去の選択履歴がない場合は、基本情報を中心に推薦する。
- 根拠が少ない場合でも、候補ニュースを比較して最も適切な記事を選ぶ。
- 過去の選択行動や興味・関心について、存在しない情報を作り出さない。

【出力条件】
- 推薦するニュースは必ず1件とする。
- 候補ニュースに付けられたnumberから選択する。
- news_idを新たに生成しない。
- 推薦理由は、実際に参照した情報に基づいて具体的に説明する。
- 推薦理由は簡潔な日本語で2〜4文程度とする。

【出力形式】
以下のJSONのみを出力する。

{{
    "recommended_number": 1,
    "recommendation_reason": "過去の選択履歴や基本情報を踏まえて、そのニュースを推薦した理由"
}}

recommended_numberは1〜{len(news_list)}の整数とする。
"""


# LLMを使って最推薦ニュースを決定する関数
def _request_recommendation(
    user_profile: dict,
    news_list: list[dict],
    past_memories: str,
) -> dict:
    prompt = _build_ranking_prompt(
        user_profile,
        news_list,
        past_memories,
    )

    try:
        response = call_llm(
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

    # LLMの応答をJSONとして解析する
    raw = _parse_json_text(response)

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
    user_id: str | None = None,
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
    # 9記事の本文を取得し、AIで一括要約する
    start = time.perf_counter()

    prepare_news_summaries(selected_items)

    print(f"【計測】本文取得＋一括要約：{time.perf_counter() - start:.2f}秒")

    
    # 過去のニュース選択履歴をRAGで取得する
    if user_id:
        past_memories = retrieve_recommendation_memories(
            user_id=user_id,
            news_list=selected_items,
        )
    else:
        past_memories = "ユーザーIDが指定されていないため、過去の選択履歴は参照していません。"

    # AIが過去の選択履歴と基本情報をもとに最推薦1件を選ぶ
    start = time.perf_counter()

    ranking = _request_recommendation(
        profile,
        selected_items,
        past_memories,
    )


    print(f"【計測】ニュース推薦：{time.perf_counter() - start:.2f}秒")


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



    reason = ranking[
        "recommendation_reason"
    ]

    recommended_news[
        "recommendation_reason"
    ] = reason


    # 今回表示するニュースのID一覧を作る
    selected_news_ids = [
        str(news.get("news_id"))
        for news in selected_items
    ]

    return {
        "selected_news_ids": selected_news_ids,
        "recommended_news_id": recommended_id,
        "recommendation_reason": reason,
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
    print(f"要約:\n{recommended.get('ai_summary') or recommended.get('summary')}")
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


# ==========================================
# 保存済みニュース（10件）から最推薦1件を決める関数
# ==========================================
def recommend_from_saved_news(
    news_list: list[dict],
    user_profile: dict | None = None,
    user_id: str | None = None,
) -> dict:
    """
    すでに取得・要約済みのニュース一覧（10件）を受け取り、
    過去の記憶（Pinecone RAG）と基本情報をもとにAI推薦を実行する。
    ※ ニュース取得・本文取得・AI要約は一切行わない。
    """
    if not news_list:
        raise RecommendationError("推薦対象のニュースがありません。")

    profile = (
        user_profile
        if user_profile is not None
        else TEST_USER_PROFILE
    )

    selected_items = [
        _copy_news(news)
        for news in news_list
    ]

    # 過去のニュース選択履歴をRAGで取得する
    if user_id:
        past_memories = retrieve_recommendation_memories(
            user_id=user_id,
            news_list=selected_items,
        )
    else:
        past_memories = "ユーザーIDが指定されていないため、過去の選択履歴は参照していません。"

    # AIが過去の選択履歴と基本情報をもとに最推薦1件を選ぶ
    start = time.perf_counter()

    ranking = _request_recommendation(
        profile,
        selected_items,
        past_memories,
    )

    print(f"【計測】ニュース推薦：{time.perf_counter() - start:.2f}秒")

    recommended_id = ranking["recommended_news_id"]
    recommended_news = None
    other_news = []

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

    reason = ranking["recommendation_reason"]
    recommended_news["recommendation_reason"] = reason

    selected_news_ids = [
        str(news.get("news_id"))
        for news in selected_items
    ]

    return {
        "selected_news_ids": selected_news_ids,
        "recommended_news_id": recommended_id,
        "recommendation_reason": reason,
        "recommended_news": recommended_news,
        "other_news": other_news,
    }
