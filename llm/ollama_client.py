import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv


load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434/api/chat",
)


def call_llm(
    prompt: str,
    json_mode: bool = False,
    temperature: float = 0.3,
) -> str:
    """
    ローカルのOllamaを使ってLLMを呼び出す。
    """

    body = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "stream": False,
        "options": {
            "temperature": temperature,
        },
    }

    if json_mode:
        body["format"] = "json"

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=300,
        ) as response:
            result = json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Ollamaへの接続に失敗しました: {e}"
        ) from e

    content = (
        result.get("message", {}).get("content")
    )

    if not content:
        raise RuntimeError(
            "Ollamaから空の応答が返されました。"
        )

    return content.strip()