# Valley – LinkedIn Sequence Generator API

A REST API that takes a LinkedIn prospect URL and company context, analyzes the prospect (simulated when real profile data isn’t available), and generates a personalized messaging sequence with configurable tone of voice. Built for a ~4–5 hour backend engineer task.

---

## Data model (what we care about most)

**The design is driven by data modelling:** entities, relationships, invariants, and tradeoffs are documented in **[`docs/DATA_MODEL.md`](docs/DATA_MODEL.md)**. That document covers:

- **Entities and attributes**: Prospect, TovConfig, MessageSequence, SequenceMessage, AIGeneration — and why each attribute exists (e.g. JSONB for flexible AI output, snapshot vs reference for TOV).
- **Relationships and cardinalities**: Prospect 1:N MessageSequence, MessageSequence 1:N SequenceMessage, MessageSequence 1:1 AIGeneration; TovConfig standalone with TOV snapshotted per sequence.
- **Invariants**: Uniqueness of (sequence_id, step_number), profile_data/analyzed_at updated together, one AIGeneration per sequence.
- **Lifecycle**: Get-or-create prospect, overwrite profile on each run, immutable sequence and messages once created.
- **Tradeoffs**: Snapshot TOV (audit trail, inline TOV) vs reference; one AI row per sequence (cost per campaign) vs per-call; JSONB for evolution without migrations.
- **Access patterns and indexing**: Lookup by URL, sequences by prospect and created_at, unique step per sequence.

The implementation follows this model (including unique constraint on `(sequence_id, step_number)` and index on `(prospect_id, created_at)`). If you review one thing, make it **`docs/DATA_MODEL.md`**.

---

## What’s in the repo

- **Stack**: Python 3.11+, FastAPI, SQLAlchemy 2 (async), PostgreSQL (asyncpg), Pydantic v2, OpenAI.
- **Core endpoint**: `POST /api/generate-sequence` — request body includes `prospect_url`, `tov_config`, `company_context`, `sequence_length`; response includes generated messages, prospect analysis, AI thinking summary, confidence scores, and token usage.
- **Database**: Tables and constraints as in `docs/DATA_MODEL.md`; schema created on startup via SQLAlchemy `create_all`.
- **AI**: Two-step flow — (1) profile analysis from URL + company context, (2) sequence generation from analysis + TOV. TOV parameters are converted into natural-language instructions; token usage and cost are stored per sequence.

## Quick start

1. **Environment**

   ```bash
   cp .env.example .env
   # Set DATABASE_URL and OPENAI_API_KEY (and optionally OPENAI_MODEL, e.g. gpt-4o-mini)
   ```

2. **PostgreSQL**

   ```bash
   docker compose up -d
   # DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/valley
   ```

3. **Run API**

   ```bash
   pip install -r requirements.txt
   uvicorn main:app --reload
   ```

4. **Try the endpoint**

   ```bash
   curl -X POST http://localhost:8000/api/generate-sequence \
     -H "Content-Type: application/json" \
     -d '{
       "prospect_url": "https://linkedin.com/in/john-doe",
       "tov_config": { "formality": 0.8, "warmth": 0.6, "directness": 0.7 },
       "company_context": "We help SaaS companies automate sales",
       "sequence_length": 3
     }'
   ```

- **Docs**: http://localhost:8000/docs  
- **Health**: http://localhost:8000/health  

---

## Database schema (short summary)

Full rationale, invariants, and tradeoffs are in **[`docs/DATA_MODEL.md`](docs/DATA_MODEL.md)**. Summary:

- **`prospects`**: Identity by normalized `linkedin_url`; `profile_data` (JSONB) and `analyzed_at` for analysis output and freshness.
- **`tov_configs`**: Named TOV presets; sequences do **not** reference these by FK — we snapshot TOV into `message_sequences.tov_config` for history and inline TOV.
- **`message_sequences`**: One per generation; `prospect_id`, `tov_config` (JSONB snapshot), `company_context`, `sequence_length`; index on `(prospect_id, created_at)` for “sequences for this prospect by time”.
- **`sequence_messages`**: One per step; unique `(sequence_id, step_number)`; `content`, `thinking_process` (JSONB), `confidence_score`.
- **`ai_generations`**: One per sequence; `model_used`, `input_tokens`, `output_tokens`, `cost_estimate` for the full run (analysis + sequence).

---

## How I approached prompt engineering

- **TOV → natural language**  
  Numerical TOV (formality, warmth, directness in 0–1) is mapped to banded, human-readable instructions (e.g. “formal and businesslike”, “warm and personable”) in `app/prompts/tov.py`. The model receives these instructions in the system/user prompt so behavior is consistent and debuggable.

- **Structured outputs**  
  Both “profile analysis” and “sequence generation” prompts ask for JSON only, with explicit key names and structure. We parse the response and handle markdown-wrapped JSON. This keeps the API response shape predictable and easy to store.

- **Two-step flow**  
  Step 1: “Analyze this prospect (URL + company context)” → one JSON with summary, role, signals. Step 2: “Given this analysis and TOV, generate N messages with reasoning and confidence.” Separating analysis from writing keeps prompts focused and lets us cache or reuse analysis later.

- **Length and format**  
  Prompts specify “short messages”, “under 300/500 characters”, and “first person as the sender” so outputs stay LinkedIn-appropriate and on-brand.

---

## AI integration patterns and error handling

- **Single AI client**  
  `AIService` wraps the OpenAI client and exposes `analyze_prospect` and `generate_sequence`. Both return `(data, input_tokens, output_tokens)` so the orchestrator can always record usage.

- **Graceful fallbacks**  
  On API or parse errors, we return minimal but valid data (e.g. generic “B2B prospect” analysis, placeholder messages with 0.5 confidence) so the pipeline completes and the client gets a 200 with a clear “fallback” signal in the content. Errors are logged for debugging.

- **Token and cost tracking**  
  We use the `usage` field from the completion response, aggregate tokens for analysis + sequence, and store them in `ai_generations`. A simple per-token cost (e.g. gpt-4o-mini) is used for `cost_estimate` so we can monitor spend.

- **No real LinkedIn scraping**  
  The task doesn’t require a scraper. We treat the prospect URL (and optional slug) as context and have the AI infer a plausible B2B profile. The same schema supports plugging in real profile data later.

---

## API design choices and data validation

- **Single primary endpoint**  
  `POST /api/generate-sequence` does “create or reuse prospect → analyze → generate → persist” in one call. This keeps the demo simple and matches the requested flow. We could later split into “analyze prospect” and “generate sequence” if we want to cache analysis or support multiple sequences per analysis.

- **Pydantic**  
  Request body is validated with Pydantic: `prospect_url` must look like a LinkedIn profile URL (we normalize it), `tov_config` defaults and clamps to [0, 1], `sequence_length` is bounded (e.g. 1–10). Invalid payloads return 422 with field-level errors.

- **Response shape**  
  Response includes `sequence_id`, `prospect_analysis`, `messages` (with step, content, thinking_process, confidence_score), `thinking_process_summary`, `model_used`, and `token_usage` so the client has everything for display and transparency.

- **Idempotency / duplicates**  
  Same `prospect_url` (after normalization) reuses the same prospect row and overwrites `profile_data` and `analyzed_at`. Each request still creates a new sequence and new AI generation row so we keep full history.

---

## What I’d improve with more time

1. **Real profile data**  
   Integrate a LinkedIn scraping or enrichment API (e.g. PhantomBuster, Proxycurl) and store real profile_data; keep the same JSONB shape and add an “source: ai | scraped” flag.

2. **Caching**  
   Cache profile analysis by `(prospect_url, company_context)` or by prospect_id with TTL so we don’t re-call the model when only TOV or sequence_length changes.

3. **Structured “thinking” in DB**  
   Store a single JSONB “thinking” blob per sequence (e.g. `thinking_summary` + per-message reasoning) in `message_sequences` or a small companion table for easier analytics.

4. **Auth and rate limits**  
   Add API keys or JWT and rate limit per key; use `ai_generations` for cost-based limits.

5. **Alembic**  
   Replace `create_all` with Alembic migrations for production-safe schema changes.

6. **Tests**  
   Unit tests for TOV → instructions, request validation, and a mocked AI path for the full generate-sequence flow; integration test against a test DB.

7. **Deployment**  
   Dockerfile + Railway/Render config so the repo is one-click deploy with a Postgres add-on.

---

## Project layout

```
.
├── main.py                 # FastAPI app, lifespan, health
├── requirements.txt
├── .env.example
├── docker-compose.yml
├── README.md
├── docs/
│   └── DATA_MODEL.md       # Data model: entities, relationships, invariants, tradeoffs (no code)
└── app/
    ├── config.py           # Settings (DB, OpenAI)
    ├── api/
    │   └── routes.py       # POST /api/generate-sequence
    ├── db/
    │   ├── base.py
    │   └── session.py      # Async engine, session, init_db
    ├── models/             # Prospect, TovConfig, MessageSequence, SequenceMessage, AIGeneration
    ├── schemas/
    │   └── generate.py     # Request/response and TOV validation
    ├── prompts/
    │   ├── tov.py          # TOV params → natural language
    │   └── templates.py    # Profile + sequence prompts
    └── services/
        ├── ai.py           # OpenAI calls, token/cost, fallbacks
        └── generate.py    # Orchestration and persistence
```

---

## License

MIT.
