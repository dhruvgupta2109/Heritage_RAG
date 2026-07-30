# Heritage RAG

**Status:** Phases 0–4 complete; Phase 5 is next

**Last updated:** 2026-07-30

A localhost, single-user knowledge assistant for asking grounded questions over personal documents. Heritage combines page-level citations, evidence-based confidence, selectable LLM providers, adjustable retrieval depth, password-gated document ingestion, persistent chat history, and a minimalist glass interface.

## Product Contract

Every completed answer must include:

- Inline source citations when supporting evidence exists.
- An always-visible **Answered from** summary naming the supporting document(s) and page(s).
- An expandable source list with snippets and precise locations.
- One of five evidence confidence states: Very high, High, Medium, Low, or Very low.
- A glass confidence badge whose hover, focus, or tap view explains all five states and highlights the current one.

If information is not supported by indexed documents, Heritage says so, shows **Answered from: No supporting document found**, and uses Very low confidence. It never fabricates a citation or page number; non-paginated sources show **Page unavailable** with the best structural locator.

## Current Implementation Stack

- Next.js 16 + React 19 + Tailwind CSS
- FastAPI
- Groq Chat Completions, OpenAI Responses, and Gemini Generate Content adapters
- Chroma with free local `all-MiniLM-L6-v2` ONNX embeddings
- SQLite for document lifecycle and answer snapshots

No hosted vector database or embedding API is required. The first indexing run downloads approximately 80 MB of model files to the local Chroma cache.

## Run Locally

Prerequisites: Node.js 20.9 or newer, Python 3.11, and `uv`.

1. Keep source files in `DOCS/`.
2. If `.env` does not exist, copy `.env.example` to `.env`.
3. Set `GROQ_API_KEY` in `.env`. Optionally set `OPENAI_API_KEY` and
   `GEMINI_API_KEY`; models stay visible but disabled until their provider
   authenticates. The local document-upload password defaults to `Password`;
   override `UPLOAD_PASSWORD_HASH` with a bcrypt hash before using the app in a
   less trusted environment. Never commit `.env`.
4. Install dependencies:

   ```bash
   npm install
   uv sync --project apps/api
   ```

5. Index or re-index the document folder:

   ```bash
   npm run index
   ```

6. Start the web app and API together:

   ```bash
   npm run dev
   ```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000). The API runs on `http://127.0.0.1:8000`.

## Verification

```bash
npm run test:api
npm run test:web
npm run build
npm run eval -- --mode medium
```

The Phase 1 corpus test asks `What are the four components of experiential learning?` and expects `Experiential Learning at HXLS Noida | Learning by Doing.pdf`, Page 1. The verified answer identifies Experience, Reflection, Dialogue, and Understanding.

## Implemented Through Phase 4

Implemented:

- PDF, DOCX, TXT, and Markdown parsing.
- Page-aware chunks for PDF and structural locators for non-paginated files.
- Idempotent local ingestion with checksums.
- Local Chroma vector search and a basic lexical re-rank.
- Groq token streaming.
- Per-message provider/model selection across Groq, OpenAI, and Gemini.
- Provider availability checks that disable missing, invalid, or inaccessible models.
- Working Quick vector search, Medium hybrid ranking, and Deep LLM query expansion
  with local BM25/vector fusion and full re-ranking.
- Normalized provider errors, timeouts, cancellation-safe streaming, and one retry
  for transient failures.
- Persistent SQLite chat history with sidebar loading and continuation.
- Groq-generated conversation titles based on each chat's first user question.
- Persistent rename, pin/unpin, and confirmed chat deletion controls.
- Calendar-grouped history for pinned chats, Today, Yesterday, recent ranges,
  and older month/year sections. History is shared by every browser connected
  to the same local backend.
- Password-gated multi-document upload with a short-lived HTTP-only session,
  rate limiting, safe file validation, duplicate detection, and immediate
  indexing.
- Real per-file upload progress, processing/indexing status, independent
  indexed/duplicate/failure results, and one-click retry.
- Manual folder re-indexing for documents copied directly into `DOCS/`.
- Citation validation, source/page links, query-aware snippets, and **Answered from**.
- Evidence confidence calculation and all five glass UI states.
- Explicit no-evidence behavior with Very low confidence.

The current corpus includes a 25-question evaluation set covering expected
document/page retrieval and explicit no-answer cases. Optional
Anthropic/Ollama adapters and broader confidence calibration are later work.
The OpenAI and Gemini adapters are implemented and contract-tested; their live
authentication check is an operational follow-up once valid keys are supplied,
not a blocker for starting Phase 5.

## Current Limitations

- OCR is intentionally excluded from the current scope.
- Confidence thresholds are initial values and still need evaluation-set calibration.
- The current stable Next.js release includes a transitive PostCSS security advisory. Heritage does not accept or process user-supplied CSS and binds to localhost, but the dependency should be upgraded when Next.js ships a patched stable release.

## Documentation

- [Product requirements](mds/PRD.md)
- [Architecture](mds/Architechture.md)
- [Design system](mds/Design.md)
- [Delivery phases](mds/Phases.md)
- [Engineering rules](mds/Rules.md)
- [Project memory](mds/Memory.md)
