# Data model – LinkedIn sequence generator

This document describes the **data modelling** for the system: entities, relationships, invariants, lifecycle, and tradeoffs. It is written for reviewers who care about schema design and evolution, not implementation details.

---

## 1. Domain and boundaries

**Scope**: We store (a) who we’re reaching out to (prospects), (b) how we talk (tone-of-voice), (c) each generated outreach “campaign” (sequence) and its messages, and (d) AI usage and cost per generation.

**Out of scope for the model**: User/tenant, auth, rate limits, and actual delivery state (sent/opened). The model supports “generate and store”; attribution and delivery would be separate.

---

## 2. Entities and attributes

### Prospect

- **Identity**: One row per distinct LinkedIn profile, keyed by normalized URL.
- **Attributes**:
  - `linkedin_url` (unique, indexed): Canonical lookup key. Normalization (scheme, trailing slash) is applied before insert/select so we never duplicate the same person.
  - `profile_data` (JSONB, nullable): Analysis output — summary, role/industry, signals, raw_data. Flexible so we can add fields (e.g. from a real scraper) without migrations.
  - `analyzed_at` (timestamptz, nullable): When this profile was last analyzed. Supports “re-analyze if stale” and debugging.
  - `created_at`: When we first saw this prospect (stored in UTC; all timestamps in the model are timestamptz/UTC).
- **Why JSONB for profile_data**: AI and future scrapers produce variable shapes; we query by prospect_id, not by fields inside profile_data. JSONB gives schema flexibility and good enough queryability (e.g. GIN on key paths) if we need it later.

### TovConfig (tone-of-voice preset)

- **Identity**: Named presets for formality, warmth, directness (each 0–1).
- **Attributes**: `name`, `formality`, `warmth`, `directness`, `created_at`.
- **Usage**: Optional. The API accepts inline TOV in the request; we do **not** store a foreign key from sequences to TovConfig. Instead we snapshot the TOV used into each sequence (see MessageSequence). So TovConfig is a “library” of presets; the source of truth for “what TOV was used for this sequence” is the snapshot.

### MessageSequence

- **Identity**: One row per generation request (one campaign for one prospect).
- **Relationships**: Belongs to one **Prospect**. Has many **SequenceMessage** (ordered by step). Has one **AIGeneration** (usage/cost for this run).
- **Attributes**:
  - `prospect_id` (FK → prospects): Which prospect this sequence is for.
  - `tov_config` (JSONB): **Snapshot** of the TOV parameters used (formality, warmth, directness). We do not store a reference to `tov_configs.id` so that (1) history is preserved even if a preset is deleted, and (2) inline TOV (no preset) is represented the same way.
  - `company_context` (text): The “what we do / who we help” string used in this run.
  - `sequence_length` (integer): Requested number of messages (e.g. 3). Invariant: the number of child SequenceMessage rows should equal this (enforced in application logic; could be a DB check in a stricter setup).
  - `created_at`: When the sequence was generated.

### SequenceMessage

- **Identity**: One row per step in a sequence.
- **Relationships**: Belongs to one **MessageSequence**.
- **Attributes**:
  - `sequence_id` (FK → message_sequences), `step_number` (1..N): **Unique (sequence_id, step_number)** so we never have duplicate steps for the same sequence.
  - `content` (text): The message body.
  - `thinking_process` (JSONB, nullable): AI reasoning for this message (e.g. “why this angle”). Kept flexible for different model outputs.
  - `confidence_score` (float, nullable): Model’s confidence for this message (0–1).

### AIGeneration

- **Identity**: One row per sequence generation run (combined usage for the whole request).
- **Relationships**: Belongs to one **MessageSequence** (1:1 for “one generation run”).
- **Attributes**:
  - `sequence_id` (FK → message_sequences).
  - `model_used`: Model name (e.g. gpt-4o-mini).
  - `input_tokens`, `output_tokens`: Total for both profile analysis and sequence generation in that run.
  - `cost_estimate` (nullable): Derived cost in USD for monitoring/budgeting.
  - `created_at`.

**Design choice**: We aggregate “profile analysis” and “sequence generation” into a single AIGeneration row per sequence. Alternative would be one row per API call (e.g. analysis vs sequence) for finer-grained analytics; we chose one row per business operation (one sequence) for simplicity and direct cost-per-sequence reporting.

---

## 3. Relationships and cardinalities

| Parent       | Child            | Cardinality | Notes |
|-------------|------------------|------------|--------|
| Prospect    | MessageSequence  | 1 : N      | One prospect can have many sequences (e.g. different TOV or context over time). |
| MessageSequence | SequenceMessage | 1 : N   | Ordered by step_number; N = sequence_length. |
| MessageSequence | AIGeneration  | 1 : 1      | One usage record per sequence. |
| TovConfig   | (none)           | —          | No FK from sequences; TOV is snapshotted. |

**Cascades**: On delete of a Prospect we delete all its MessageSequences (and thus their SequenceMessages and AIGenerations). On delete of a MessageSequence we delete its messages and AIGeneration. This keeps referential integrity and avoids orphans.

---

## 4. Invariants (what must hold)

- **Prospect**: `linkedin_url` is normalized and unique. If `profile_data` is not null, `analyzed_at` should be set (we update both together).
- **MessageSequence**: `sequence_length` is in [1, 10] (enforced at API layer). The number of SequenceMessage rows for this sequence equals `sequence_length`.
- **SequenceMessage**: `(sequence_id, step_number)` is unique. Step numbers are 1..sequence_length.
- **AIGeneration**: Exactly one per MessageSequence; token counts and cost_estimate reflect the full run (analysis + sequence).

These are enforced in application code; a stricter setup would add check constraints or triggers (e.g. count of messages = sequence_length).

---

## 5. Lifecycle and data flow

1. **Prospect**: Created on first occurrence of a normalized LinkedIn URL. On every generate request for that URL we **overwrite** `profile_data` and `analyzed_at` (we re-run analysis each time; caching could be added later).
2. **MessageSequence**: Created once per successful generate request. Immutable after creation (no updates).
3. **SequenceMessage**: Created with the sequence; one row per step. Immutable.
4. **AIGeneration**: Created with the sequence; immutable.
5. **TovConfig**: Created/updated via a separate concern (preset CRUD); not written by the generate endpoint.

So the main write path is: **Prospect (get-or-create + update profile) → MessageSequence (insert) → SequenceMessage (bulk insert) → AIGeneration (insert)**.

---

## 6. Tradeoffs

- **Normalization vs audit trail**: We normalize identity (one Prospect per URL, sequences as separate rows) but denormalize where we need a stable audit trail: TOV is snapshotted per sequence, and profile_data is a blob per prospect. That way we never lose “what was used for this run” even if presets or analysis logic change later.
- **Snapshot vs reference for TOV**: We snapshot TOV into `message_sequences.tov_config` instead of storing `tov_config_id`. Tradeoff: we can’t efficiently “all sequences that used preset X” without scanning JSONB, but we preserve exact parameters and support inline TOV; presets can be renamed or deleted without affecting history.
- **JSONB for profile_data and thinking_process**: Lets AI/output schema evolve without migrations. We index and query by foreign keys and scalars; we don’t rely on JSONB for critical uniqueness or joins.
- **One AIGeneration per sequence**: Simpler reporting (cost per sequence). If we need per-call breakdown (analysis vs sequence), we’d add a generation “type” or split into two tables.
- **No tenant_id / user_id**: Single-tenant model; multi-tenant would add a tenant (or user) and scope all tables by it.

---

## 7. Access patterns and indexing

- **Prospect by URL**: Lookup by `linkedin_url` (unique index).
- **Sequences by prospect**: List sequences for a prospect, often by recency → index on `(prospect_id, created_at)`.
- **Messages by sequence**: Load messages for a sequence, ordered by step → `sequence_id` (FK index) and unique `(sequence_id, step_number)`.
- **AIGeneration by sequence**: 1:1 lookup by `sequence_id` (FK index).
- **Analytics**: Aggregate cost/tokens over time → filter by `created_at` on `ai_generations` or `message_sequences`; index on `created_at` on either table if we do time-range queries.

---

## 8. Evolution

- **Profile source**: Add `profile_source` (e.g. 'ai' | 'scraper') and keep `profile_data` shape compatible.
- **Caching analysis**: Could add a cache key (e.g. hash of url + company_context) and TTL; model stays the same, logic decides whether to re-call AI.
- **Thinking at sequence level**: Store `thinking_summary` (or full reasoning blob) on MessageSequence or a small companion table for analytics without joining through messages.
- **Multi-tenant**: Add `tenant_id` (or `user_id`) to prospects and message_sequences (and optionally to tov_configs); partition or index by tenant on hot paths.

This is the data model the implementation follows. Schema changes (e.g. unique constraint on `(sequence_id, step_number)`, index on `(prospect_id, created_at)`) are reflected in the ORM and documented here.
