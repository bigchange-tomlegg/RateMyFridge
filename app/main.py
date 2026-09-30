import base64
import os
from pathlib import Path
from typing import Any

import markdown
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(
    title="Rate My Fridge API",
    version="1.0.0",
    description=(
        "Upload a photo of the inside of a fridge and get back a score, a funny verdict, "
        "the items spotted, some advice and the fridge's vibe.\n\n"
        "Send the photo to `POST /rate-fridge` as `multipart/form-data` with a single field "
        "called `image` (JPEG, PNG or WebP, max 10 MB). Responses usually take 3-8 seconds.\n\n"
        "The text is written by an AI model, so it changes every time. Build your UI around "
        "the fields, not exact strings."
    ),
)

MAX_BYTES = 10 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
EXERCISE_PATH = Path(__file__).resolve().parent.parent / "exercise.md"

EXERCISE_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rate My Fridge Mini Hack</title>
<style>
  :root {{ color-scheme: light dark; --fg: #1d1d1f; --bg: #fafaf7; --muted: #6e6e73; --accent: #2e8b57; --quote: #eef5ef; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --fg: #f2f2f2; --bg: #141414; --muted: #a1a1a6; --accent: #5fd08a; --quote: #1f2a22; }}
  }}
  body {{ margin: 0; background: var(--bg); color: var(--fg);
         font: 17px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
  main {{ max-width: 720px; margin: 0 auto; padding: 32px 16px 64px; }}
  h1, h2, h3 {{ line-height: 1.25; }}
  h1 {{ font-size: 2rem; }}
  h2 {{ margin-top: 2.5rem; }}
  h3 {{ color: var(--accent); }}
  blockquote {{ margin: 1rem 0; padding: 0.75rem 1rem; background: var(--quote);
               border-left: 4px solid var(--accent); border-radius: 6px; }}
  blockquote p {{ margin: 0.25rem 0; }}
  hr {{ border: 0; border-top: 1px solid var(--muted); opacity: 0.3; margin: 2.5rem 0; }}
  code {{ font-size: 0.9em; }}
</style>
</head>
<body><main>
{body}
</main></body>
</html>
"""

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


VIBES = [
    "student", "bachelor", "meal-prepper", "foodie",
    "chaos", "surprisingly-organised", "family-fridge", "mystery",
]


class FridgeResult(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "score": 37,
            "verdict": "Your fridge needs professional help.",
            "items": ["half a cucumber", "three sauces", "mysterious container"],
            "advice": "Buy actual food before opening another condiment.",
            "vibe": "chaos",
        }
    })

    score: int = Field(description="Fridge score from 0 (emergency) to 100 (impressively stocked).")
    verdict: str = Field(description="One short, funny sentence summing up the fridge.")
    items: list[str] = Field(description="Up to 6 food or drink items visible in the photo.")
    advice: str = Field(description="One short, funny piece of advice.")
    vibe: str = Field(description="One of: " + ", ".join(VIBES) + ".")


class ErrorDetail(BaseModel):
    detail: str


def client() -> OpenAI:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return OpenAI(api_key=key)


@app.get("/health", summary="Check the API is up")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/mini-hack", response_class=HTMLResponse, include_in_schema=False)
def mini_hack() -> str:
    body = markdown.markdown(EXERCISE_PATH.read_text(encoding="utf-8"), extensions=["nl2br"])
    return EXERCISE_PAGE.format(body=body)


@app.post(
    "/rate-fridge",
    response_model=FridgeResult,
    summary="Rate a fridge photo",
    responses={
        413: {"model": ErrorDetail, "description": "Image is larger than 10 MB."},
        415: {"model": ErrorDetail, "description": "Image is not a JPEG, PNG or WebP."},
        502: {"model": ErrorDetail, "description": "The AI analysis failed. Safe to retry."},
    },
)
async def rate_fridge(
    image: UploadFile = File(..., description="Photo of the inside of a fridge. JPEG, PNG or WebP, max 10 MB."),
) -> Any:
    if image.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, "Please upload a JPEG, PNG, or WebP image.")

    data = await image.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Image is too large. Maximum size is 10 MB.")

    mime = image.content_type
    encoded = base64.b64encode(data).decode("utf-8")

    try:
        response = client().responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-6-luna"),
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
                                "enum": VIBES,
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
