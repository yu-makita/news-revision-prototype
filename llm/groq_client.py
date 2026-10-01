import os

from dotenv import load_dotenv
from groq import Groq


load_dotenv()

GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")


def call_llm(
    prompt: str,
    json_mode: bool = False,
    temperature: float = 0.3,
) -> str:
    """
    Groq APIを使ってLLMを呼び出す。
    """

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY が設定されていません。"
        )

    client = Groq(api_key=api_key)

    response = client.chat.completions.create(
    model=GROQ_MODEL,
    messages=[
        {
            "role": "user",
            "content": prompt,
        }
    ],
    temperature=temperature,
    reasoning_effort="none",
    max_completion_tokens=800,
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            "Groqから空の応答が返されました。"
        )

    return content.strip()