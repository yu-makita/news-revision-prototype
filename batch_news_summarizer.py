
import json

from llm.groq_client import call_llm
from news_fetcher import fetch_article_text_for_news


# 9記事の本文を取得する関数
def fetch_all_article_texts(news_list):
    for news in news_list:
        try:
            fetch_article_text_for_news(news)
        except Exception as e:
            print(f"本文取得失敗: {news.get('title')} / {e}")
            news["article_text"] = None

    return news_list


# 9記事をまとめてAI要約する関数
def summarize_news_batch(news_list):
    if not news_list:
        return news_list

    articles = []

    for number, news in enumerate(news_list, start=1):
        articles.append({
            "number": number,
            "title": news.get("title", ""),
            "article_text": (
                news.get("article_text")
                or news.get("summary")
                or ""
            ),
        })

    prompt = f"""
以下のニュース記事を、それぞれ独立して要約してください。

【要約の条件】
- 各記事100字程度の日本語で要約する。
- 主要な事実、背景、経緯をできるだけ含める。
- 記事にない情報を追加しない。
- 異なる記事の情報を混ぜない。
- 明確な争点がない記事に、無理に争点を作らない。
- 全記事について回答する。
- 各記事のnumberを変更しない。

【ニュース記事一覧】
{json.dumps(articles, ensure_ascii=False)}

【出力形式】
次のJSON形式のみを返してください。

{{
  "articles": [
    {{
      "number": 1,
      "summary": "150字程度の要約",
      "main_issue": "中心的な争点。なければ空文字"
    }}
  ]
}}

numberには、入力記事の1から{len(news_list)}までの番号を指定してください。
全{len(news_list)}記事について、重複なく回答してください。
"""

    response = call_llm(
        prompt,
        json_mode=True,
        temperature=0.2,
        max_completion_tokens=1000,
    )

    data = json.loads(response)
    results = data.get("articles")

    if not isinstance(results, list):
        raise ValueError("要約結果がリストではありません")

    result_map = {}

    for item in results:
        if not isinstance(item, dict):
            raise ValueError("要約結果に不正なデータがあります")

        number = item.get("number")
        summary = item.get("summary")

        if (
            type(number) is not int
            or not 1 <= number <= len(news_list)
            or number in result_map
            or not isinstance(summary, str)
            or not summary.strip()
        ):
            raise ValueError(
                f"要約結果の番号または本文が不正です: {number}"
            )

        result_map[number] = item

    if len(result_map) != len(news_list):
        raise ValueError(
            f"一部の記事の要約が不足しています。"
            f"期待件数: {len(news_list)}、取得件数: {len(result_map)}"
        )

    # 番号を使って元の記事にAI要約を対応付ける
    for number, news in enumerate(news_list, start=1):
        item = result_map[number]

        news["ai_summary"] = item["summary"].strip()
        news["main_issue"] = item.get("main_issue") or ""

    return news_list


# 本文取得と一括要約を実行する関数
def prepare_news_summaries(news_list):
    fetch_all_article_texts(news_list)

    try:
        summarize_news_batch(news_list)

    except Exception as e:
        raise RuntimeError(
            f"9記事のAI一括要約に失敗しました: {e}"
        ) from e

    return news_list
