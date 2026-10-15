
import json
import time

from news_fetcher import (
    fetch_yahoo_news_for_recommendation,
    fetch_article_text_for_news,
)
from llm.groq_client import call_llm


# 1記事分の要約と中心争点を生成する関数
def summarize_single(news):
    prompt = f"""
次のニュース記事について、内容を正確に整理してください。

【記事タイトル】
{news.get("title")}

【記事本文】
{news.get("article_text") or news.get("summary") or ""}

以下のJSON形式で回答してください。
{{
  "summary": "記事の主要な事実を150〜200字で要約",
  "main_issue": "この記事について意見が分かれる中心争点を1文で記述。明確な争点がなければ空文字"
}}

JSON以外は出力しないでください。
"""
    response = call_llm(
        prompt,
        json_mode=True,
        max_completion_tokens=600,
    )
    return json.loads(response)


# 9記事をまとめて要約する関数
def summarize_batch(news_list):
    articles = [
        {
            "news_id": news["news_id"],
            "title": news.get("title"),
            "article_text": news.get("article_text") or news.get("summary") or "",
        }
        for news in news_list
    ]

    prompt = f"""
以下のニュース記事をそれぞれ独立して要約してください。
異なる記事の情報を混ぜないでください。

【記事一覧】
{json.dumps(articles, ensure_ascii=False)}

次のJSON形式で回答してください。
{{
  "articles": [
    {{
      "news_id": "入力と同じnews_id",
      "summary": "記事の主要な事実を150〜200字で要約",
      "main_issue": "意見が分かれる中心争点を1文で記述。なければ空文字"
    }}
  ]
}}

全記事について回答し、JSON以外は出力しないでください。
"""
    response = call_llm(
        prompt,
        json_mode=True,
        max_completion_tokens=3500,
    )
    return json.loads(response)["articles"]


# 両方式の処理時間と結果を比較する関数
def main():
    print("ニュースを取得しています...")

    start = time.perf_counter()
    news_list = fetch_yahoo_news_for_recommendation()

    for news in news_list:
        fetch_article_text_for_news(news)

    print(
        f"取得完了：{len(news_list)}件 / "
        f"{time.perf_counter() - start:.2f}秒"
    )

    if not news_list:
        return

    print("\n=== 一括要約 ===")
    start = time.perf_counter()

    try:
        batch_results = summarize_batch(news_list)
        batch_time = time.perf_counter() - start

        expected_ids = {news["news_id"] for news in news_list}
        returned_ids = {
            item.get("news_id")
            for item in batch_results
            if isinstance(item, dict)
        }

        valid_count = sum(
            1
            for item in batch_results
            if isinstance(item, dict)
            and item.get("summary")
            and "main_issue" in item
        )

        print(f"処理時間：{batch_time:.2f}秒")
        print(f"取得件数：{len(batch_results)}件")
        print(f"形式が正常な件数：{valid_count}件")
        print(f"記事ID一致：{expected_ids == returned_ids}")

        for item in batch_results:
            print(
                f"\n{item.get('news_id')}\n"
                f"要約：{item.get('summary')}\n"
                f"争点：{item.get('main_issue')}"
            )

    except Exception as e:
        print(f"一括要約エラー：{e}")

    print("\n=== 個別要約 ===")
    start = time.perf_counter()
    success_count = 0

    for i, news in enumerate(news_list, start=1):
        item_start = time.perf_counter()

        try:
            result = summarize_single(news)
            success_count += 1

            print(
                f"\n{i}. {news.get('title')}\n"
                f"処理時間：{time.perf_counter() - item_start:.2f}秒\n"
                f"要約：{result.get('summary')}\n"
                f"争点：{result.get('main_issue')}"
            )

        except Exception as e:
            print(f"\n{i}. エラー：{e}")

    print(f"\n個別要約合計：{time.perf_counter() - start:.2f}秒")
    print(f"成功件数：{success_count}/{len(news_list)}件")


if __name__ == "__main__":
    main()
