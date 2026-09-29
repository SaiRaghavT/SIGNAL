import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


# Load .env from the SIGNAL project root
PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not configured.")


client = genai.Client(api_key=GEMINI_API_KEY)


def generate_json(prompt: str) -> str:
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
        ),
    )

    if not response.text:
        raise ValueError("Gemini returned an empty response.")

    return response.text