import os

from dotenv import load_dotenv


load_dotenv()

LLM_PROVIDER = os.getenv(
    "LLM_PROVIDER",
    "groq",
).lower()


if LLM_PROVIDER == "groq":
    from .groq_client import call_llm

elif LLM_PROVIDER == "ollama":
    from .ollama_client import call_llm

elif LLM_PROVIDER == "gemini":
    from .gemini_client import call_llm

else:
    raise ValueError(
        f"未対応のLLM_PROVIDERです: {LLM_PROVIDER}"
    )