
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.8-flash",
)


# Gemini APIを使ってLLMを呼び出す関数
def call_llm(
    prompt: str,
    json_mode: bool = False,
    temperature: float = 0.3,
    max_completion_tokens: int | None = None,
) -> str:

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY が設定されていません。"
        )

    client = genai.Client(api_key=api_key)

    # APIに渡す設定を作成
    config_params = {
    "temperature": temperature,
    }

    if max_completion_tokens is not None:
        config_params["max_output_tokens"] = max_completion_tokens

    # JSON形式が必要な場合
    if json_mode:
        config_params["response_mime_type"] = "application/json"

    # API呼び出し時間を計測
    api_start = time.perf_counter()

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(**config_params),
    )

    elapsed_time = time.perf_counter() - api_start

    print(f"【Gemini】モデル：{GEMINI_MODEL}")
    print(f"【Gemini】API呼び出し実時間：{elapsed_time:.2f}秒")

    # トークン使用量を表示
    usage = response.usage_metadata

    if usage:
        print(f"【Gemini】入力トークン：{usage.prompt_token_count}")
        print(f"【Gemini】出力トークン：{usage.candidates_token_count}")
        print(f"【Gemini】合計トークン：{usage.total_token_count}")

    content = response.text

    if not content:
        raise RuntimeError(
            "Geminiから空の応答が返されました。"
        )

    return content.strip()
