
from opinion_generator import predict_user_opinion


# 意見予測をテストする関数
def test_prediction():
    # テスト用の架空のニュース
    news = {
        "title": "学校がいじめ問題の公表を遅らせた",
        "summary": (
            "ある学校でいじめ問題が発覚したが、"
            "学校は事実関係の確認と生徒のプライバシー保護を理由に、"
            "問題の公表を遅らせたという想定のニュース。"
        ),
    }

    # テスト用の10個の意見候補
    opinion_candidates = {
        "main_issue": (
            "学校がいじめ問題の公表を遅らせた対応は適切だったか"
        ),
        "gradient_opinions": [
            "学校はすぐに公表すべきで、遅らせたことは許されない。",
            "学校には早期に説明する責任があり、対応は問題だった。",
            "事情は理解できるが、もう少し早く説明すべきだった。",
            "早期公表と慎重な確認のどちらにも理由がある。",
            "生徒への影響を考えると、公表を遅らせた判断も理解できる。",
            "事実確認とプライバシー保護を優先したのは適切だった。",
            "生徒を守るためなら、公表を遅らせることは当然だ。",
        ],
        "alternative_perspectives": [
            {
                "perspective": "被害者への支援",
                "opinion": "公表時期よりも被害者への支援を優先すべきだ。",
            },
            {
                "perspective": "再発防止",
                "opinion": "同じ問題を繰り返さない仕組みを作るべきだ。",
            },
            {
                "perspective": "保護者への説明",
                "opinion": "一般公開とは別に保護者への説明を充実させるべきだ。",
            },
        ],
    }

    result = predict_user_opinion(
        user_id="P0001",
        news=news,
        opinion_candidates=opinion_candidates,
    )

    print("\n【過去の意見履歴】")
    print("履歴あり：", result["has_history"])
    print("取得件数：", result["retrieved_memory_count"])

    print("\n【推測した判断傾向】")
    for tendency in result["inferred_tendencies"]:
        print("・", tendency)

    print("\n【予測した意見】")
    print("番号：", result["predicted_opinion_id"])
    print("内容：", result["predicted_opinion_text"])

    print("\n【予測理由】")
    print(result["prediction_reason"])


if __name__ == "__main__":
    test_prediction()
