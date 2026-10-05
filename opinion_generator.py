# -*- coding: utf-8 -*-

import json

from llm import call_llm
from news_fetcher import fetch_article_text_for_news


# ==========================================
# ニュース記事の本文を取得する関数
# ==========================================
def get_article_text(
    news: dict,
) -> str:

    news_with_text = fetch_article_text_for_news(
        news.copy()
    )

    article_text = news_with_text.get(
        "article_text"
    )

    if not article_text:
        raise RuntimeError(
            "記事本文を取得できませんでした。"
        )

    return article_text


# ==========================================
# 記事本文から詳細な要約を生成する関数
# ==========================================
def generate_article_summary(
    news: dict,
) -> str:

    title = news.get(
        "title",
        "",
    )

    article_text = get_article_text(
        news
    )

    rss_summary = news.get(
        "summary",
        "",
    )

    prompt = f"""
以下のニュース記事を要約してください。

【記事タイトル】
{title}

【記事本文】
{article_text}

【RSS要約】
{rss_summary}

【要件】
- 記事全体の内容が分かるように、十分な情報量を含める。
- 主要な出来事だけでなく、その背景、経緯、具体的な内容、今後の予定など、記事内の重要な情報をできるだけ落とさずまとめる。
- ユーザーが元記事を読まなくても、ニュースの全体像を把握できる程度の要約にする。
- 目安として10〜15文程度、500〜800字程度とする。
- 記事本文またはRSS要約に書かれていない情報を追加しない。
- 意見や評価を勝手に加えない。
- 要約本文だけを返す。見出しや前置きは不要。
"""

    summary = call_llm(
        prompt,
        json_mode=False,
        temperature=0.2,
    )

    if not summary:
        raise RuntimeError(
            "記事要約を生成できませんでした。"
        )

    return summary.strip()


# ==========================================
# ニュースから10個の意見候補を生成する関数
# ==========================================
def generate_opinion_candidates(
    news: dict,
) -> dict:

    title = news.get(
        "title",
        "",
    )

    if not title:
        raise RuntimeError(
            "記事タイトルを取得できませんでした。"
        )

    article_text = get_article_text(
        news
    )

    prompt = f"""
あなたは、ニュース記事に対して人が持ちうる
多様な意見候補を生成するAIです。

以下の記事本文を必ず根拠として、
10個の異なる意見候補を生成してください。

記事本文に書かれていない情報を、
事実であるかのように追加しないでください。


【記事タイトル】
{title}


【記事本文】
{article_text}


【手順1：中心争点の特定】

この記事について、
人によって意見が分かれうる最も中心的な争点を
1つ特定してください。

単なる記事内容の要約ではなく、
「何について評価や意見が分かれるのか」
が分かる形にしてください。


【手順2：中心争点について7つの意見を生成】

中心争点について、

一方の立場を強く支持する意見
↓
中間的・条件付きの意見
↓
反対側の立場を強く支持する意見

となるように、
立場が段階的に変化する7つの意見を生成してください。

7つは単なる表現の言い換えではなく、
考え方や評価の違いが明確になるようにしてください。


【手順3：異なる着眼点を3つ発見】

中心争点とは異なる角度から
この記事を考えることができる、
重要な着眼点を3つ特定してください。

着眼点の種類は固定しません。

記事の内容を踏まえて、
その記事について考えるうえで重要な着眼点を
毎回選んでください。

例えば、

・別の当事者への影響
・短期的または長期的な影響
・社会的な影響
・経済的な影響
・制度や仕組み
・倫理
・実現可能性
・原因や背景
・今後起こりうること

などがありますが、
これらはあくまで例です。

記事によって、
これ以外の着眼点を選んでも構いません。

3つの着眼点は、
互いにできるだけ異なるものにしてください。

また、
中心争点への賛成・反対の程度を
変えただけのものにはしないでください。

中心争点とは異なる問いを立ててください。


【手順4：異なる着眼点から3つの意見を生成】

手順3で特定した3つの着眼点について、
それぞれ1つずつ意見を生成してください。


【出力形式】

必ず次のJSON形式だけを出力してください。

説明文やMarkdownのコードブロックは
付けないでください。

{{
    "main_issue": "中心争点",
    "gradient_opinions": [
        "意見1",
        "意見2",
        "意見3",
        "意見4",
        "意見5",
        "意見6",
        "意見7"
    ],
    "alternative_perspectives": [
        {{
            "perspective": "着眼点1",
            "opinion": "意見8"
        }},
        {{
            "perspective": "着眼点2",
            "opinion": "意見9"
        }},
        {{
            "perspective": "着眼点3",
            "opinion": "意見10"
        }}
    ]
}}
"""

    response = call_llm(
        prompt,
        json_mode=True,
        temperature=0.7,
    )

    try:
        result = json.loads(
            response
        )

    except json.JSONDecodeError as e:
        raise RuntimeError(
            "意見候補のJSON解析に失敗しました。"
        ) from e

    if not result.get(
        "main_issue"
    ):
        raise RuntimeError(
            "中心争点を生成できませんでした。"
        )

    if len(
        result.get(
            "gradient_opinions",
            [],
        )
    ) != 7:
        raise RuntimeError(
            "中心争点についての意見を7個生成できませんでした。"
        )

    if len(
        result.get(
            "alternative_perspectives",
            [],
        )
    ) != 3:
        raise RuntimeError(
            "その他の視点についての意見を3個生成できませんでした。"
        )

    return result