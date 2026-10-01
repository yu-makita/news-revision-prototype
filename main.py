import os
import sys

# Windowsターミナルでの文字化け防止
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from google import genai
from google.genai import errors

# 1. .env ファイルから環境変数を読み込む
load_dotenv()

# 2. APIキーの確認
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("=" * 60)
    print("【エラー】GEMINI_API_KEY が設定されていません。")
    print("プロジェクトルートにある `.env` ファイルに、次のようにAPIキーを記述してください：")
    print("GEMINI_API_KEY=あなたのAPIキー")
    print("=" * 60)
    sys.exit(1)

if api_key == "your_gemini_api_key_here":
    print("=" * 60)
    print("【エラー】`.env` ファイルの APIキーが初期値（your_gemini_api_key_here）のままです。")
    print("Google AI Studio ( https://aistudio.google.com/app/apikey ) で取得した")
    print("実際のAPIキーに書き換えてください。")
    print("=" * 60)
    sys.exit(1)


def main():
    print("=== Gemini API 疎通テスト開始 ===")
    
    try:
        # 3. Gemini クライアントの初期化
        client = genai.Client(api_key=api_key)
        
        # 4. 送信するプロンプト（質問）
        prompt = "こんにちは！自己紹介と、今日のニュースを読むときに役立つ心構えを日本語で1〜2文で教えてください。"
        print(f"\n送信プロンプト:\n「{prompt}」\n")
        print("Geminiに問い合わせ中...")
        
        # 5. モデルの呼び出し (推奨モデル: gemini-3.5-flash)
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
        )
        
        # 6. 回答の表示
        print("\n=== Geminiからの回答 ===")
        print(response.text)
        print("========================")
        print("\n✅ STEP 1 完了: Gemini API との通信に成功しました！")
        
    except errors.APIError as e:
        print(f"\n【Gemini API エラー】: {e}")
        print("APIキーが正しいか、または利用制限に達していないか確認してください。")
        sys.exit(1)
    except Exception as e:
        print(f"\n【予期せぬエラー】: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
