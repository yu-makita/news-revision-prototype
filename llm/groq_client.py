import os

from dotenv import load_dotenv
from groq import Groq


load_dotenv()

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "qwen/qwen3.8-27b",
)


# ==========================================
# Groq APIを使ってLLMを呼び出す関数
# ==========================================
def call_llm(
    prompt: str,
    json_mode: bool = False,
    temperature: float = 0.3,
    max_completion_tokens: int = 800,
) -> str:

    api_key = os.getenv(
        "GROQ_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY が設定されていません。"
        )

    client = Groq(
        api_key=api_key
    )


    # ==========================================
    # APIに渡す設定を作成
    # ==========================================
    request_params = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": temperature,
        "reasoning_effort": "none",
        "max_completion_tokens": max_completion_tokens,
    }


    # ==========================================
    # JSON形式が必要な場合
    # ==========================================
    if json_mode:
        request_params["response_format"] = {
            "type": "json_object"
        }


    # Groq API呼び出し全体の時間を計測する
    import time

    api_start = time.perf_counter()

    response = client.chat.completions.create(**request_params)

    print(
        f"【Groq】API呼び出し実時間："
        f"{time.perf_counter() - api_start:.2f}秒"
    )
    # AIのトークン使用量を確認する
    usage = response.usage

    print(f"【Groq】モデル：{GROQ_MODEL}")
    print(f"【Groq】入力トークン：{usage.prompt_tokens}")
    print(f"【Groq】出力トークン：{usage.completion_tokens}")
    print(f"【Groq】合計トークン：{usage.total_tokens}")

    # Groq側の処理時間を確認する
    timings = getattr(usage, "prompt_time", None)
    completion_time = getattr(usage, "completion_time", None)
    queue_time = getattr(usage, "queue_time", None)
    total_time = getattr(usage, "total_time", None)

    print(f"【Groq】入力処理時間：{timings}秒")
    print(f"【Groq】出力生成時間：{completion_time}秒")
    print(f"【Groq】待機時間：{queue_time}秒")
    print(f"【Groq】サーバー処理時間：{total_time}秒")

    content = (
        response
        .choices[0]
        .message
        .content
    )

    if not content:
        raise RuntimeError(
            "Groqから空の応答が返されました。"
        )

    return content.strip()