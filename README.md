# Rate My Fridge API

A tiny shared backend for the iOS vs Android Rate My Fridge mini hack. Teams send a photo of a fridge, and the API uses an OpenAI vision model to send back a score, a funny verdict, the items it spotted, some advice and the fridge's "vibe".

**Live:** https://ratemyfridge.onrender.com

| Page | What it is |
| --- | --- |
| [`/mini-hack`](https://ratemyfridge.onrender.com/mini-hack) | The challenge brief for the teams (rendered from [`exercise.md`](exercise.md)) |
| [`/docs`](https://ratemyfridge.onrender.com/docs) | Interactive API docs. Use **Try it out** to upload a photo from your browser |
| [`/redoc`](https://ratemyfridge.onrender.com/redoc) | Read-only API reference |
| [`/openapi.json`](https://ratemyfridge.onrender.com/openapi.json) | OpenAPI spec, for Postman or client code generation |

## API contract

This is all the mobile teams need.

### `POST /rate-fridge`

Send the photo as `multipart/form-data` with one field:

| Field | Type | Notes |
| --- | --- | --- |
| `image` | file | JPEG, PNG or WebP, max 10 MB |

```bash
curl -X POST https://ratemyfridge.onrender.com/rate-fridge \
  -F "image=@$HOME/Downloads/fridge.jpg"
```

The field must be called `image`, and the path needs the `@` in front of it so curl sends the file itself. Opening this URL in a browser sends a GET request and returns `405 Method Not Allowed`; that's expected.

#### Response `200`

```json
{
  "score": 37,
  "verdict": "Your fridge needs professional help.",
  "items": ["half a cucumber", "three sauces", "mysterious container"],
  "advice": "Buy actual food before opening another condiment.",
  "vibe": "chaos"
}
```

| Field | Type | Notes |
| --- | --- | --- |
| `score` | integer | 0–100. 90+ impressively stocked, 70–89 solid, 50–69 questionable, 30–49 concerning, under 30 emergency |
| `verdict` | string | One short, funny sentence |
| `items` | string[] | Up to 6 visible food or drink items |
| `advice` | string | One short, funny sentence |
| `vibe` | string | One of `student`, `bachelor`, `meal-prepper`, `foodie`, `chaos`, `surprisingly-organised`, `family-fridge`, `mystery` |

The text is written by the model and changes on every request, so build the UI around the fields, not exact strings. Requests usually take 3–8 seconds, so show a loading state.

#### Errors

Errors come back as `{"detail": "..."}`.

| Status | Meaning |
| --- | --- |
| `413` | Image is larger than 10 MB |
| `415` | Not a JPEG, PNG or WebP (iPhone HEIC photos need converting first) |
| `422` | No `image` field in the request |
| `502` | The AI analysis failed. Safe to retry |

### `GET /health`

Returns `{"status": "ok"}`. Useful for waking the server up before a demo.

## Run it locally

You need Python 3.12 (see [`.python-version`](.python-version)). On macOS the system `python3` is too old; install one with `brew install python@3.12`.

**1. Install** (first time only)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**2. Configure** (first time only)

Copy `.env.example` to `.env` and set `OPENAI_API_KEY`. `OPENAI_MODEL` defaults to `gpt-6-luna`. `.env` is git-ignored; never commit it.

**3. Run**

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --env-file .env --host 0.0.0.0 --port 8000
```

Then open http://localhost:8000/docs, or test with curl:

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/rate-fridge \
  -F "image=@/path/to/fridge.jpg"
```

To test from a phone on the same Wi-Fi, use your Mac's IP address (`ipconfig getifaddr en0`) instead of `localhost`.
