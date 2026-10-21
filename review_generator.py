
import json
from llm import call_llm


# 本人の選択・補足から、確認用の意見文章を生成する関数
def generate_review(
    news: dict,
    selected_opinion_id: str,
    selected_opinion_text: str,
    correction_text: str,
    prediction: dict,
) -> dict:

    correction_text = correction_text.strip()
    selected_opinion_text = selected_opinion_text.strip()

    # 補足がない場合は、本人の選択した意見をそのまま使用する
    if not correction_text:
        user_opinion = selected_opinion_text

    # 「該当する意見がない」場合は、自由記述をそのまま使用する
    elif selected_opinion_id == "none":
        user_opinion = correction_text

    # 選択した意見と補足がある場合のみAIで統合する
    else:
        opinion_prompt = f"""
あなたは、ユーザー本人の意見を文章として整理するAIです。

【選択した意見】
{selected_opinion_text}

【本人が入力した補足・訂正】
{correction_text}

2つの内容を統合し、自然な日本語の意見文を作成してください。

【ルール】
- 本人が述べていない主張や価値観を追加しない。
- 補足が元の意見を修正している場合は、補足を優先する。
- 意味を変えず、簡潔な一人称の意見文にする。
- 意見文だけを出力する。
"""
        user_opinion = call_llm(
            opinion_prompt,
            json_mode=False,
            temperature=0.2,
        ).strip()

        if not user_opinion:
            raise RuntimeError("本人の意見文を生成できませんでした。")

    # AIの予測と本人の意見の違いを分析する
    predicted_id = prediction["predicted_opinion_id"]
    predicted_text = prediction["predicted_opinion_text"]
    tendencies = prediction.get("inferred_tendencies", [])
    prediction_reason = prediction.get("prediction_reason", "")

    analysis_prompt = f"""
あなたは、分身AIの予測と本人の回答を比較するAIです。

【ニュース】
{news.get('title', '')}

【分身AIが予測した意見】
意見{predicted_id}：{predicted_text}

【予測に用いた判断傾向の仮説】
{json.dumps(tendencies, ensure_ascii=False)}

【予測理由】
{prediction_reason}

【本人が選択した意見番号】
{selected_opinion_id}

【本人の意見】
{user_opinion}

【タスク】
分身AIの予測と本人の意見を比較し、
予測時に重視しすぎた判断基準や、
見落としていた可能性のある考え方を推測してください。

【ルール】
- 単なる文章表現の違いと、判断基準の違いを区別する。
- 予測と本人の意見が一致している場合は、無理に違いを作らない。
- 推測した理由を事実として断定しない。
- 本人が確認・訂正するための下書きとして、簡潔に説明する。
- 過去の判断傾向が今回にも当てはまるとは限らない。

【出力形式】
次のJSONのみを返してください。

{{
    "difference_reason": "予測と本人の意見が異なった理由の仮説"
}}
"""

    response = call_llm(
        analysis_prompt,
        json_mode=True,
        temperature=0.3,
    )

    try:
        result = json.loads(response)
        difference_reason = result["difference_reason"]

        if not isinstance(difference_reason, str):
            raise ValueError("理由が文字列ではありません。")

    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        raise RuntimeError("予測のずれの分析に失敗しました。") from e

    return {
        "user_opinion": user_opinion,
        "difference_reason": difference_reason,
    }
