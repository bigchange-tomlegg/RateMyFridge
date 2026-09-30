import base64
import os
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from openai import OpenAI
from pydantic import BaseModel

app = FastAPI(title="Rate My Fridge API", version="1.0.0")

MAX_BYTES = 10 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}

SYSTEM_PROMPT = """
You are Rate My Fridge, a brutally funny but friendly fridge critic.
Analyze the supplied fridge photo. Be playful, concise, and never cruel about
the person. Identify only items you can reasonably see; uncertainty is fine.

Return JSON with exactly these fields:
{
  "score": integer 0-100,
  "verdict": "one short funny sentence",
  "items": ["up to 6 visible food/drink items"],
  "advice": "one short funny sentence",
  "vibe": "one of: student, bachelor, meal-prepper, foodie, chaos, surprisingly-organised, family-fridge, mystery"
}

Scoring guidance:
90-100 = impressively stocked
70-89 = solid
50-69 = questionable
30-49 = concerning
0-29 = emergency

Do not claim to identify brands or ingredients that are not visible.
Do not mention sensitive personal attributes.
""".strip()


class FridgeResult(BaseModel):
    score: int
    verdict: str
    items: list[str]
    advice: str
    vibe: str


def client() -> OpenAI:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return OpenAI(api_key=key)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/rate-fridge", response_model=FridgeResult)
async def rate_fridge(image: UploadFile = File(...)) -> Any:
    if image.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, "Please upload a JPEG, PNG, or WebP image.")

    data = await image.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Image is too large. Maximum size is 10 MB.")

    mime = image.content_type
    encoded = base64.b64encode(data).decode("utf-8")

    try:
        response = client().responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": SYSTEM_PROMPT},
                    {
                        "type": "input_image",
                        "image_url": f"data:{mime};base64,{encoded}",
                    },
                ],
            }],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "fridge_result",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "score": {"type": "integer", "minimum": 0, "maximum": 100},
                            "verdict": {"type": "string"},
                            "items": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
                            "advice": {"type": "string"},
                            "vibe": {
                                "type": "string",
                                "enum": [
                                    "student", "bachelor", "meal-prepper", "foodie",
                                    "chaos", "surprisingly-organised", "family-fridge", "mystery"
                                ],
                            },
                        },
                        "required": ["score", "verdict", "items", "advice", "vibe"],
                        "additionalProperties": False,
                    },
                }
            },
        )
        return FridgeResult.model_validate_json(response.output_text)
    except Exception as exc:
        raise HTTPException(502, f"Fridge analysis failed: {exc}") from exc
