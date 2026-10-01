import os

from dotenv import load_dotenv
from google import genai


load_dotenv()

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash-lite",
)


def call_llm(
    prompt: str,
    json_mode: bool = False,
    temperature: float = 0.3,
) -> str:
    """
    Gemini APIを使ってLLMを呼び出す。
    """

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY が設定されていません。"
        )

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={
            "temperature": temperature,
        },
    )

    content = response.text

    if not content:
        raise RuntimeError(
            "Geminiから空の応答が返されました。"
        )

    return content.strip()