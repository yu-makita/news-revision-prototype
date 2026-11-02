# -*- coding: utf-8 -*-
"""
毎朝実行するニュース事前取得・要約・保存バッチスクリプト。

Yahoo!ニュースの9カテゴリから各5件（計45件程度）を取得し、
5件ずつ分割してAI要約を生成した上で、Googleスプレッドシートの daily_news シートに保存する。
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime

from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

# Windowsターミナルでの文字化け防止
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from batch_news_summarizer import fetch_all_article_texts, summarize_news_batch
from database import save_daily_news
from news_fetcher import YAHOO_NEWS_CATEGORY_RSS, fetch_yahoo_news

# 設定値
PER_CATEGORY_LIMIT = 5
CHUNK_SIZE = 5
API_CALL_INTERVAL_SEC = 1.0


def run_daily_news_batch(
    batch_date: str | None = None,
    dry_run: bool = False,
) -> dict:
    """
    毎朝のニュース事前取得・要約・保存処理を実行する。

    Args:
        batch_date: 保存対象日付（YYYY-MM-DD）。Noneの場合は当日日付。
        dry_run: Trueの場合、スプレッドシートへの書き込みをスキップする。

    Returns:
        処理結果の要約辞書
    """
    today_str = batch_date or datetime.now().strftime("%Y-%m-%d")
    print(f"[{datetime.now().isoformat()}] === 毎朝ニュース事前処理バッチ開始 (対象日: {today_str}) ===")

    # -------------------------------------------------------------------------
    # 1. Yahoo!ニュースの9カテゴリからRSS記事を取得
    # -------------------------------------------------------------------------
    print(f"1. Yahoo!ニュースより各カテゴリ最大{PER_CATEGORY_LIMIT}件のRSSを取得中...")
    try:
        raw_news_list = fetch_yahoo_news(
            category_rss=YAHOO_NEWS_CATEGORY_RSS,
            per_category_limit=PER_CATEGORY_LIMIT,
            fetch_article=False,  # 本文取得は後段のバッチ処理で実行
        )
    except Exception as e:
        print(f"【重大エラー】RSS記事の取得全体でエラーが発生しました: {e}", file=sys.stderr)
        return {
            "status": "error",
            "message": f"RSS取得エラー: {e}",
            "processed_count": 0,
        }

    if not raw_news_list:
        print("【警告】取得できたニュース記事が0件でした。処理を終了します。", file=sys.stderr)
        return {
            "status": "warning",
            "message": "ニュース記事が0件でした",
            "processed_count": 0,
        }

    print(f"-> 合計 {len(raw_news_list)} 件のRSS記事を取得しました。")

    # カテゴリごとにグループ化（または5件ずつのチャンクに分割）
    # カテゴリの偏りや文脈を揃えるため、カテゴリ単位でチャンクを作成
    category_grouped: dict[str, list[dict]] = {}
    for news in raw_news_list:
        cat = news.get("category", "未分類")
        category_grouped.setdefault(cat, []).append(news)

    processed_news_list: list[dict] = []
    success_summary_count = 0
    fallback_summary_count = 0

    # -------------------------------------------------------------------------
    # 2. カテゴリごと（約5件ずつ）に本文取得とAI要約を分割実行
    # -------------------------------------------------------------------------
    print("2. 本文取得およびAI要約を分割実行中...")
    total_categories = len(category_grouped)

    for idx, (cat_name, items) in enumerate(category_grouped.items(), start=1):
        print(f"  [{idx}/{total_categories}] カテゴリ「{cat_name}」({len(items)}件) の処理中...")

        # 2-1. 本文HTMLの取得
        try:
            fetch_all_article_texts(items)
        except Exception as e:
            print(f"    【警告】「{cat_name}」の本文取得中にエラー（一部継続）: {e}", file=sys.stderr)

        # 2-2. AI要約の生成（失敗時はRSS概要へフォールバック）
        try:
            summarize_news_batch(items)
            for item in items:
                if item.get("ai_summary"):
                    success_summary_count += 1
                else:
                    # ai_summaryが空だった場合の補完
                    item["ai_summary"] = item.get("summary") or "要約を取得できませんでした。"
                    fallback_summary_count += 1

            print(f"    -> 「{cat_name}」のAI要約完了")

        except Exception as e:
            print(f"    【警告】「{cat_name}」のAI要約に失敗しました。RSS概要で代替します: {e}", file=sys.stderr)
            for item in items:
                # 要約失敗時はRSS概要をai_summaryに設定して継続
                item["ai_summary"] = item.get("summary") or "要約を取得できませんでした。"
                fallback_summary_count += 1

        processed_news_list.extend(items)

        # APIレートリミット対策のための短い待機
        if idx < total_categories and API_CALL_INTERVAL_SEC > 0:
            time.sleep(API_CALL_INTERVAL_SEC)

    print(
        f"-> 本文取得・要約完了: 合計{len(processed_news_list)}件 "
        f"(AI要約成功: {success_summary_count}件, RSS概要代替: {fallback_summary_count}件)"
    )

    # -------------------------------------------------------------------------
    # 3. Googleスプレッドシート（daily_newsシート）に保存
    # -------------------------------------------------------------------------
    if dry_run:
        print("[Dry Run] スプレッドシートへの保存をスキップしました。")
        save_result = {
            "saved_count": len(processed_news_list),
            "skipped_count": 0,
            "batch_date": today_str,
            "dry_run": True,
        }
    else:
        print("3. Googleスプレッドシート（daily_news シート）へ保存中...")
        try:
            save_result = save_daily_news(
                news_list=processed_news_list,
                batch_date=today_str,
            )
            print(
                f"-> 保存完了: 新規追加 {save_result.get('saved_count', 0)} 件, "
                f"重複スキップ {save_result.get('skipped_count', 0)} 件"
            )
        except Exception as e:
            print(f"【重大エラー】スプレッドシートへの保存中にエラーが発生しました: {e}", file=sys.stderr)
            return {
                "status": "error",
                "message": f"スプレッドシート保存エラー: {e}",
                "processed_count": len(processed_news_list),
            }

    print(f"[{datetime.now().isoformat()}] === 毎朝ニュース事前処理バッチ正常終了 ===")
    return {
        "status": "success",
        "batch_date": today_str,
        "processed_count": len(processed_news_list),
        "ai_summary_success": success_summary_count,
        "fallback_summary": fallback_summary_count,
        "save_result": save_result,
    }


def main():
    parser = argparse.ArgumentParser(description="毎朝ニュース事前取得・要約・保存バッチ")
    parser.add_argument(
        "--batch-date",
        type=str,
        default=None,
        help="対象日付 (YYYY-MM-DD)。省略時は本日",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="スプレッドシートに保存せず、取得と要約のみテストする",
    )

    args = parser.parse_args()
    result = run_daily_news_batch(
        batch_date=args.batch_date,
        dry_run=args.dry_run,
    )

    if result.get("status") == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
