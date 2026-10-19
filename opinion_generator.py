# -*- coding: utf-8 -*-

import json

from llm import call_llm
from news_fetcher import fetch_article_text_for_news


# 保存済みの記事本文を優先して取得する関数
def get_article_text(news: dict) -> str:
    article_text = news.get("article_text")

    if isinstance(article_text, str) and article_text.strip():
        return article_text.strip()

    news_with_text = fetch_article_text_for_news(news.copy())
    article_text = news_with_text.get("article_text")

    if not isinstance(article_text, str) or not article_text.strip():
        raise RuntimeError("記事本文を取得できませんでした。")

    return article_text.strip()


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
- 目安として10〜15文程度、300〜400字程度とする。記事の重要な情報を簡潔にまとめる。
- 記事本文またはRSS要約に書かれていない情報を追加しない。
- 意見や評価を勝手に加えない。
- 要約本文だけを返す。見出しや前置きは不要。
"""

    summary = call_llm(
        prompt,
        json_mode=False,
        temperature=0.2,
        max_completion_tokens=900,
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
    あなたは、ニュース記事を読んだ一般の人が持ちうる
    多様な意見候補を生成するAIです。

    以下の記事本文を必ず根拠として、
    10個の異なる意見候補を生成してください。

    記事本文に書かれていない情報を、
    事実であるかのように追加しないでください。


    【記事タイトル】
    {title}


    【記事本文】
    {article_text}


    【意見候補の基本方針】

    生成する意見は、専門家による評論ではなく、
    一般のニュース読者がこの記事を読んだときに
    実際に持ちそうな意見にしてください。

    以下の点を守ってください。

    ・難しい専門用語や抽象的な表現はできるだけ避ける。
    ・政治、法律、経済などの専門知識を持っていることを前提にしない。
    ・大学生を含む一般の読者が、読んですぐ意味を理解できる表現にする。
    ・一つの意見に多くの論点を詰め込みすぎない。
    ・単なる「賛成」「反対」ではなく、なぜそう思うのかが分かる内容にする。
    ・一般の人が「自分の考えに近い」と判断して選択できる意見にする。
    ・記事本文から大きく飛躍した専門的な分析や推測はしない。
    ・それぞれの意見は、できるだけ1〜2文程度の自然な文章にする。


    【手順1：中心争点の特定】

    この記事について、
    一般の読者の間で意見が分かれそうな
    最も中心的な争点を1つ特定してください。

    単なる記事内容の要約ではなく、
    「この記事について何をどう考えるか」
    が分かる問いになるようにしてください。

    中心争点自体も、
    専門用語をできるだけ使わず、
    一般の人が理解しやすい表現にしてください。


    【手順2：中心争点について7つの意見を生成】

    中心争点について、
    対立する2つの立場を両端とした
    「1本の意見軸」を作ってください。

    そのうえで、7つの意見を必ず
    一方の立場から反対側の立場へ
    少しずつ移動する順番で生成してください。

    イメージは以下です。

    1. 一方の立場を非常に強く支持
    2. 一方の立場をかなり支持
    3. 一方の立場をやや支持
    4. 両方に同程度の理由がある・中間的
    5. 反対側の立場をやや支持
    6. 反対側の立場をかなり支持
    7. 反対側の立場を非常に強く支持

    重要なのは、
    7つすべてを同じ「意見軸」の上に並べることです。

    途中で別の論点に移ったり、
    異なる観点の意見を混ぜたりしないでください。
    別の観点は手順3・4で生成します。

    また、1から7までを順番に読んだときに、
    立場が急に飛ぶことなく、
    少しずつ反対側へ変化していることが
    明確に分かるようにしてください。

    ただし、単に
    「とても賛成」「賛成」「やや賛成」
    のように強さだけを変えるのではなく、
    それぞれの立場になる自然な理由も含めてください。

    生成後に、
    1→2→3→4→5→6→7の順に
    立場が一方向へ変化しているか確認してから出力してください。


    【手順3：異なる着眼点を3つ発見】

    中心争点とは異なる角度から、
    一般の読者がこの記事を読んだときに
    考えそうな重要な着眼点を3つ特定してください。

    着眼点の種類は固定しません。

    記事の内容に応じて、
    その記事だからこそ考えられる着眼点を選んでください。

    例えば、

    ・別の当事者はどう感じるか
    ・自分たちの生活への影響
    ・今後どうなるのか
    ・なぜこの問題が起きたのか
    ・企業や政府などの対応は適切だったか
    ・公平性に問題はないか
    ・安全性に問題はないか
    ・お金や費用への影響
    ・社会全体への影響

    などがありますが、
    これらはあくまで例です。

    毎回同じ種類の3つを選ぶ必要はありません。

    3つの着眼点は、
    互いにできるだけ異なるものにしてください。

    また、
    中心争点への賛成・反対の程度を変えただけのものにはせず、
    中心争点とは別の問いとして考えられるものにしてください。


    【手順4：異なる着眼点から3つの意見を生成】

    手順3で特定した3つの着眼点について、
    それぞれ1つずつ意見を生成してください。

    ここでも専門家の分析ではなく、
    一般のニュース読者が実際に持ちそうな
    自然な意見にしてください。


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