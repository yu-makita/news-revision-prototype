
import time
from news_fetcher import (
    fetch_yahoo_news_for_recommendation,
    fetch_article_text_for_news,
)


# RSSから推薦候補を取得する時間を計測する関数
def benchmark_rss():
    start = time.perf_counter()

    news_list = fetch_yahoo_news_for_recommendation()

    elapsed = time.perf_counter() - start

    print(f"\nRSS取得：{elapsed:.2f}秒")
    print(f"取得記事数：{len(news_list)}件")

    return news_list


# 各記事の本文取得時間と成功率を計測する関数
def benchmark_articles(news_list):
    total_start = time.perf_counter()
    success_count = 0

    for i, news in enumerate(news_list, start=1):
        start = time.perf_counter()

        fetch_article_text_for_news(news)

        elapsed = time.perf_counter() - start
        article_text = news.get("article_text") or ""

        if article_text.strip():
            success_count += 1
            status = "成功"
        else:
            status = "失敗"

        print(
            f"{i}. [{news.get('category')}] "
            f"{elapsed:.2f}秒 / {status} / "
            f"{len(article_text)}文字"
        )

    total_elapsed = time.perf_counter() - total_start

    print(f"\n本文取得合計：{total_elapsed:.2f}秒")
    print(f"取得成功：{success_count}/{len(news_list)}件")


# RSS取得と記事本文取得の時間を計測する関数
def main():
    news_list = benchmark_rss()

    if news_list:
        benchmark_articles(news_list)


if __name__ == "__main__":
    main()
