# Setup guide

Nothing here is required beyond step 1 — the app runs free, offline, with no configuration.

## 1. Minimum setup (free, ~2 minutes)

**Windows PowerShell**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173/demo.

If activation is blocked:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

**macOS / Linux**

```bash
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && python -m uvicorn app.main:app --reload
cd ../frontend && npm install && npm run dev
```

Verify what's active:

```bash
curl http://localhost:8000/api/dashboard/health
```

## 2. Demo data (optional)

Replays scripted conversations through the real engine, so transcripts, scores and actions are
genuinely generated rather than faked.

```powershell
cd backend
python seed_demo_data.py --reset
```

Produces 8 customers spanning HOT / WARM / COLD, English / Hindi / Hinglish, a seller, an
objection-handling call and a do-not-call opt-out.

## 3. Train the classifier (optional, free)

```powershell
python ..\training\generate_dataset.py --samples 180
python ..\training\train_classifier.py
python ..\training\evaluate.py
```

The backend picks up `training/artifacts/lead_classifier.joblib` automatically. The same workflow
is available from the **AI & Training** page.

## 4. Add a free LLM (optional)

### Option A — Ollama, fully local

```bash
# install from ollama.com
ollama pull qwen2.5:3b-instruct     # ~2 GB, comfortable on 8 GB RAM
ollama serve
```

`LLM_PROVIDER=auto` detects it. Alternatives: `llama3.2:3b`, `gemma2:2b`, `qwen2.5:7b-instruct`
(better Hinglish if you have the RAM).

### Option B — Groq free tier, hosted and fast

```env
LLM_PROVIDER=openai_compatible
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_API_KEY=gsk_your_key
OPENAI_MODEL=llama-3.3-70b-versatile
```

### Option C — Hugging Face Inference

```env
LLM_PROVIDER=huggingface
HF_API_TOKEN=hf_your_token
HF_MODEL=Qwen/Qwen2.5-7B-Instruct
```

You can also switch providers live from the **Settings** page — no restart.

## 5. Real phone calls (the only paid part)

1. Twilio account + a Voice-capable number.
2. On a trial, verify the destination number in the Twilio console.
3. Expose the backend: `ngrok http 8000`
4. `.env`:

```env
TELEPHONY_PROVIDER=twilio
TWILIO_ACCOUNT_SID=ACxxxx
TWILIO_AUTH_TOKEN=xxxx
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx
PUBLIC_BASE_URL=https://your-id.ngrok-free.app
```

5. Restart the backend, open `/demo`, tick **Place a real phone call**.

No Twilio console webhook configuration is needed — the outbound call passes its webhook URL with
the request. For **inbound** calls, set the number's Voice webhook to
`https://<your-ngrok>/api/telephony/twilio/voice`.

### Troubleshooting

| Symptom | Cause |
|---|---|
| Call connects then drops | `PUBLIC_BASE_URL` unreachable — must be the https ngrok URL |
| "Twilio credentials missing" | Credentials absent; the app silently uses the mock provider |
| Call not placed on trial | Destination number not verified in the Twilio console |
| Agent doesn't hear the customer | Check `TWILIO_STT_LANGUAGE` (`en-IN` handles Hinglish best) |

## 6. Real WhatsApp (free sandbox)

1. Twilio console → Messaging → Try it out → WhatsApp sandbox.
2. From the destination phone, WhatsApp the join code to the sandbox number.
3. `.env`:

```env
WHATSAPP_PROVIDER=twilio
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
CATALOG_URL=https://your-real-catalog-url
```

The recipient must have joined the sandbox, otherwise Twilio rejects the message and the error is
recorded on the `whatsapp_messages` row.

## 7. PostgreSQL (production)

```env
DATABASE_URL=postgresql+psycopg://user:password@host:5432/swapagent
```

```bash
pip install "psycopg[binary]"
```

Tables are created on startup. Neon and Supabase both have usable free tiers.

## 8. Docker

```bash
cp .env.example .env
docker compose up --build
```

Dashboard on :3000, API on :8000. Uncomment the `postgres` and `ollama` services in
`docker-compose.yml` for a production-shaped stack.

## 9. Common issues

| Symptom | Fix |
|---|---|
| Microphone button disabled | Web Speech API needs Chrome or Edge; use the text input elsewhere |
| Mic permission denied | Browsers require https or localhost — localhost is fine |
| Dashboard shows "Reconnecting…" | Backend isn't running, or the Vite proxy target is wrong |
| `ModuleNotFoundError: app` | Run uvicorn from `backend/`, not the repo root |
| Classifier "not trained" | Run `python training/train_classifier.py` (optional — the app works without it) |
| Frontend can't reach the API | Vite proxies `/api` to `:8000`; for a different host set `VITE_API_BASE` |
