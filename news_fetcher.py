"""
Yahoo!ニュース公式のカテゴリ別RSSからニュースを取得するモジュール。
RSSの見出し・概要に加え、記事ページから本文と配信元の取得を試みる。
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import random
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urldefrag
from urllib.request import Request, urlopen

import feedparser
from bs4 import BeautifulSoup

# Windowsターミナルでの文字化け（cp932によるUnicodeEncodeError）を防止
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Yahoo!ニュース公式 カテゴリ別RSS（https://news.yahoo.co.jp/rss の categories 系統）
# 公式お知らせの例: https://news.yahoo.co.jp/rss/categories/domestic.xml
YAHOO_NEWS_CATEGORY_RSS: dict[str, str] = {
    "国内": "https://news.yahoo.co.jp/rss/categories/domestic.xml",
    "国際": "https://news.yahoo.co.jp/rss/categories/world.xml",
    "経済": "https://news.yahoo.co.jp/rss/categories/business.xml",
    "エンタメ": "https://news.yahoo.co.jp/rss/categories/entertainment.xml",
    "スポーツ": "https://news.yahoo.co.jp/rss/categories/sports.xml",
    "IT": "https://news.yahoo.co.jp/rss/categories/it.xml",
    "科学": "https://news.yahoo.co.jp/rss/categories/science.xml",
    "ライフ": "https://news.yahoo.co.jp/rss/categories/life.xml",
    "地域": "https://news.yahoo.co.jp/rss/categories/local.xml",
}

# 記事HTML取得時の待ち時間（連続アクセスを少し緩める）
ARTICLE_FETCH_INTERVAL_SEC = 0.3

_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NewsRevisionPrototype/0.1; research)",
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.8",
}

_NOISE_HEADINGS = {
    "関連記事",
    "あわせて読みたい",
    "おすすめ",
    "オススメ",
    "この記事へのコメント",
    "コメント",
    "アクセスランキング",
}

_YAHOO_SITE_NAMES = {
    "yahoo",
    "yahoo!",
    "yahoo!ニュース",
    "yahoo japan",
}


def _normalize_url(url: str | None) -> str | None:
    if not url:
        return None
    normalized, _frag = urldefrag(url.strip())
    normalized = normalized.rstrip("/")
    return normalized or None


def _make_news_id(url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return digest[:16]


def _clean_html_text(value: str | None) -> str | None:
    if not value:
        return None
    soup = BeautifulSoup(value, "html.parser")
    text = soup.get_text(" ", strip=True)
    return text or None


def _extract_summary(entry) -> str | None:
    raw = entry.get("summary") or entry.get("description")
    return _clean_html_text(raw) if raw else None


# RSSの記事情報から配信元を取得する関数
def _extract_source_from_rss(entry) -> str | None:

    # RSSのsource情報から取得する
    source = entry.get("source")

    if isinstance(source, dict):
        name = (
            source.get("title")
            or source.get("value")
        )

        if name:
            return str(name).strip() or None

    elif source:
        return str(source).strip() or None


    # RSSのauthor情報から取得する
    author = entry.get("author")

    if author:
        return str(author).strip() or None


    # ==========================================
    # source / authorがない場合はタイトルから取得する
    # ==========================================
    title = entry.get("title")

    if title:

        title = str(title).strip()

        # タイトル末尾の（配信元）を取得する
        match = re.search(
            r"[（(]([^（）()]+)[）)]$",
            title,
        )

        if match:
            return match.group(1).strip()

        # タイトル末尾の【配信元】を取得する
        match = re.search(
            r"【([^【】]+)】$",
            title,
        )

        if match:
            return match.group(1).strip()


    return None


def _ld_name(value) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        name = value.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
        if isinstance(name, dict):
            return _ld_name(name)
    if isinstance(value, list):
        for item in value:
            name = _ld_name(item)
            if name:
                return name
    return None


def _iter_ld_objects(data):
    if isinstance(data, list):
        for item in data:
            yield from _iter_ld_objects(item)
        return
    if not isinstance(data, dict):
        return
    yield data
    graph = data.get("@graph")
    if graph:
        yield from _iter_ld_objects(graph)


def _extract_source_from_html(soup: BeautifulSoup) -> str | None:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue

        for obj in _iter_ld_objects(data):
            for key in ("author", "creator", "sourceOrganization", "publisher"):
                name = _ld_name(obj.get(key))
                if name and name.strip().lower() not in _YAHOO_SITE_NAMES:
                    return name

    for attrs in (
        {"name": "author"},
        {"property": "article:author"},
        {"property": "article:publisher"},
        {"name": "publisher"},
    ):
        meta = soup.find("meta", attrs=attrs)
        if meta:
            content = (meta.get("content") or "").strip()
            if content and content.lower() not in _YAHOO_SITE_NAMES:
                return content

    return None


def _is_noise_paragraph(text: str) -> bool:
    if not text:
        return True
    compact = "".join(text.split())
    if compact in _NOISE_HEADINGS:
        return True
    if compact.startswith("最終更新"):
        return True
    if compact.startswith("©") or compact.lower().startswith("copyright"):
        return True
    if "著作権" in compact and len(compact) < 80:
        return True
    return False


def _remove_noisy_blocks(article) -> None:
    for tag in article.find_all(["script", "style", "nav", "aside", "footer", "form", "iframe", "figure"]):
        tag.decompose()

    for heading in article.find_all(["h2", "h3", "h4"]):
        heading_text = "".join(heading.get_text(" ", strip=True).split())
        if heading_text not in _NOISE_HEADINGS:
            continue
        parent = heading.find_parent(["section", "div"])
        if parent is not None and parent.name != "article" and parent is not article:
            parent.decompose()
        else:
            heading.decompose()


def extract_article_text(soup: BeautifulSoup, title: str | None = None) -> str | None:
    """
    記事HTMLから本文らしいテキストを抽出する。
    Yahoo!ニュースでは <article> に本文が含まれることを手動確認済み。
    構造変更に備え、特定媒体の class 名には依存しない。
    """
    article = soup.find("article")
    if article is None:
        return None

    _remove_noisy_blocks(article)

    paragraphs: list[str] = []
    for tag in article.find_all("p"):
        text = tag.get_text(" ", strip=True)
        if _is_noise_paragraph(text):
            continue
        if title and text == title.strip():
            continue
        paragraphs.append(text)

    if paragraphs:
        return "\n".join(paragraphs)

    fallback = article.get_text("\n", strip=True)
    lines = []
    for line in fallback.splitlines():
        text = " ".join(line.split())
        if _is_noise_paragraph(text):
            continue
        if title and text == title.strip():
            continue
        lines.append(text)

    return "\n".join(lines) if lines else None


def fetch_html(url: str, timeout: int = 15) -> str | None:
    """記事ページのHTMLを取得する。失敗時はNone。"""
    try:
        request = Request(url, headers=_HTTP_HEADERS)
        with urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", None)
            if status is not None and status != 200:
                print(f"【警告】記事HTMLの取得に失敗しました。(HTTP {status}) URL: {url}", file=sys.stderr)
                return None
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
        try:
            return raw.decode(charset)
        except LookupError:
            return raw.decode("utf-8", errors="replace")
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="replace")
    except HTTPError as e:
        print(f"【警告】記事HTMLの取得に失敗しました。(HTTP {e.code}) URL: {url}", file=sys.stderr)
        return None
    except (URLError, TimeoutError, OSError) as e:
        print(f"【警告】記事HTMLの取得に失敗しました。({e}) URL: {url}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"【警告】記事HTMLの取得中に予期せぬエラーが発生しました: {e} URL: {url}", file=sys.stderr)
        return None


def _fetch_rss_entries(rss_url: str, category: str) -> list:
    try:
        feed = feedparser.parse(rss_url)
        status = getattr(feed, "status", None)
        if status is not None and status != 200:
            print(
                f"【エラー】RSSの取得に失敗しました。カテゴリ={category} "
                f"(HTTP ステータスコード: {status})",
                file=sys.stderr,
            )
            return []

        if feed.bozo and not feed.entries:
            print(
                f"【エラー】RSSの解析に失敗しました。カテゴリ={category}: {feed.bozo_exception}",
                file=sys.stderr,
            )
            return []

        if not feed.entries:
            print(f"【警告】RSSフィードから記事が見つかりませんでした。カテゴリ={category}", file=sys.stderr)
            return []

        return list(feed.entries)
    except Exception as e:
        print(f"【エラー】RSS取得中にエラーが発生しました。カテゴリ={category}: {e}", file=sys.stderr)
        return []


def _build_news_item(entry, category: str, url: str) -> dict:
    return {
        "news_id": _make_news_id(url),
        "title": entry.get("title") or None,
        "summary": _extract_summary(entry),
        "article_text": None,
        "url": url,
        "published_at": entry.get("published") or None,
        "category": category,
        "source": _extract_source_from_rss(entry),
    }


def fetch_article_text_for_news(news_item: dict) -> dict:
    """
    1件のニュースについて、記事ページから本文を取得して news_item に格納する。
    配信元が未取得ならHTMLからも補完する。失敗時は article_text を None のままにする。
    """
    url = news_item.get("url")
    if not url:
        news_item["article_text"] = None
        return news_item

    html = fetch_html(url)
    if not html:
        news_item["article_text"] = None
        return news_item

    try:
        soup = BeautifulSoup(html, "html.parser")
        news_item["article_text"] = extract_article_text(soup, title=news_item.get("title"))
        if not news_item.get("source"):
            news_item["source"] = _extract_source_from_html(soup)
    except Exception as e:
        print(f"【警告】本文抽出に失敗しました: {e} URL: {url}", file=sys.stderr)
        news_item["article_text"] = None

    return news_item


def fetch_yahoo_news(
    category_rss: dict[str, str] | None = None,
    per_category_limit: int = 3,
    fetch_article: bool = False,
    article_interval_sec: float = ARTICLE_FETCH_INTERVAL_SEC,
) -> list[dict]:
    """
    複数カテゴリの公式RSSからニュースを取得し、1つのリストとして返す。
    既定では記事ページへアクセスせず、article_text は None のままにする。

    Args:
        category_rss: カテゴリ名とRSS URLの対応。Noneなら公式カテゴリ一式を使う。
        per_category_limit: 各カテゴリから採用する最大件数（重複除外後）。
        fetch_article: Trueなら各記事HTMLから本文・配信元の補完を試みる。
        article_interval_sec: 記事ページ取得の間隔（秒）。fetch_article=True のときのみ使用。
    """
    feeds = category_rss if category_rss is not None else YAHOO_NEWS_CATEGORY_RSS
    news_list: list[dict] = []
    seen_urls: set[str] = set()

    for category, rss_url in feeds.items():
        entries = _fetch_rss_entries(rss_url, category)
        accepted = 0

        for entry in entries:
            if accepted >= per_category_limit:
                break

            url = _normalize_url(entry.get("link"))
            if not url:
                continue
            if url in seen_urls:
                continue

            seen_urls.add(url)
            news_item = _build_news_item(entry, category, url)

            if fetch_article:
                fetch_article_text_for_news(news_item)
                if article_interval_sec > 0:
                    time.sleep(article_interval_sec)

            news_list.append(news_item)
            accepted += 1

    return news_list

# 各カテゴリから、未表示のニュースをランダムに1件ずつ取得する関数
def fetch_yahoo_news_for_recommendation(
    exclude_news_ids: set[str] | None = None,
) -> list[dict]:
    """
    Yahoo!ニュースの各カテゴリから1件ずつ取得する。

    各カテゴリの記事をランダムな順番で確認し、
    過去に表示済みの記事だった場合は次の記事を確認する。
    未表示の記事が見つかった時点で、そのカテゴリの記事として採用する。
    """

    # 過去に表示したニュースIDを集合にする
    excluded_ids = {
        str(news_id)
        for news_id in (exclude_news_ids or set())
    }

    # 今回表示するニュースを保存する
    news_list: list[dict] = []

    # 今回の9件の中で同じ記事を重複させないために使う
    selected_urls: set[str] = set()


    # ==========================================
    # 各カテゴリから1件ずつニュースを取得する
    # ==========================================
    for category, rss_url in YAHOO_NEWS_CATEGORY_RSS.items():

        # このカテゴリのRSS記事を取得する
        entries = _fetch_rss_entries(
            rss_url,
            category,
        )

        if not entries:
            continue


        # ==========================================
        # 記事を確認する順番だけランダムにする
        # ==========================================
        entry_indexes = list(
            range(len(entries))
        )

        random.shuffle(
            entry_indexes
        )


        # ==========================================
        # 未表示の記事が見つかるまで確認する
        # ==========================================
        for index in entry_indexes:

            entry = entries[index]

            url = _normalize_url(
                entry.get("link")
            )

            if not url:
                continue

            # 今回すでに別カテゴリで採用した記事なら次へ進む
            if url in selected_urls:
                continue

            news_id = _make_news_id(
                url
            )

            # 過去に表示済みなら次の記事を確認する
            if news_id in excluded_ids:
                continue


            # ==========================================
            # 未表示の記事を採用する
            # ==========================================
            news_list.append(
                _build_news_item(
                    entry,
                    category,
                    url,
                )
            )

            selected_urls.add(
                url
            )

            # このカテゴリでは1件だけ採用するため終了する
            break


    return news_list

def display_news_list(news_list: list[dict], article_preview_chars: int = 800) -> None:
    """
    取得したニュース一覧をターミナルに出力する。
    本文は長いため、先頭のみ表示する。
    """
    if not news_list:
        print("表示できるニュースがありません。")
        return

    for news in news_list:
        title = news.get("title") or ""
        summary = news.get("summary") or ""
        published_at = news.get("published_at") or ""
        category = news.get("category") or ""
        source = news.get("source") or ""
        url = news.get("url") or ""
        article_text = news.get("article_text")

        print("-" * 20)
        print(f"ニュースID：{news.get('news_id')}")
        print(f"タイトル：{title}")
        print(f"概要：{summary}")
        print(f"公開日時：{published_at}")
        print(f"カテゴリ：{category}")
        print(f"配信元：{source}")
        print(f"URL：{url}")

        if article_text:
            preview = article_text
            omitted = ""
            if len(article_text) > article_preview_chars:
                preview = article_text[:article_preview_chars]
                omitted = f"\n…(省略、全文 {len(article_text)} 文字)"
            print(f"本文：\n{preview}{omitted}")
        else:
            print("本文：（取得できませんでした）")
    print("-" * 20)


def main():
    print("=== Yahoo!ニュース カテゴリ別RSS 取得開始 ===")
    print("対象カテゴリ:", " / ".join(YAHOO_NEWS_CATEGORY_RSS.keys()))
    print()

    news_list = fetch_yahoo_news(per_category_limit=3)

    if news_list:
        print(f"ニュースを {len(news_list)} 件取得しました。\n")
        display_news_list(news_list)
    else:
        print("ニュースを取得できませんでした。")


if __name__ == "__main__":
    main()

