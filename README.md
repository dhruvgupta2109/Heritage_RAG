# Heritage RAG

A localhost, single-user knowledge assistant for asking grounded questions over personal documents. Heritage combines page-level citations, evidence-based confidence, selectable LLM providers, adjustable retrieval depth, password-gated document ingestion, persistent chat history, and a minimalist glass interface.

## Product Contract

Every completed answer must include:

- Inline source citations when supporting evidence exists.
- An always-visible **Answered from** summary naming the supporting document(s) and page(s).
- An expandable source list with snippets and precise locations.
- One of five evidence confidence states: Very high, High, Medium, Low, or Very low.
- A glass confidence badge whose hover, focus, or tap view explains all five states and highlights the current one.

If information is not supported by indexed documents, Heritage says so, shows **Answered from: No supporting document found**, and uses Very low confidence. It never fabricates a citation or page number; non-paginated sources show **Page unavailable** with the best structural locator.

## Implemented Phase 1 Stack

- Next.js 16 + React 19 + Tailwind CSS
- FastAPI
- Groq Chat Completions API
- Chroma with free local `all-MiniLM-L6-v2` ONNX embeddings
- SQLite for document lifecycle and answer snapshots

No hosted vector database or embedding API is required. The first indexing run downloads approximately 80 MB of model files to the local Chroma cache.

## Run Locally

Prerequisites: Node.js 20.9 or newer, Python 3.11, and `uv`.

1. Keep source files in `DOCS/`.
2. If `.env` does not exist, copy `.env.example` to `.env`.
3. Set `GROQ_API_KEY` in `.env`. Never commit that file.
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
npm run build
```

The Phase 1 corpus test asks `What are the four components of experiential learning?` and expects `Experiential Learning at HXLS Noida | Learning by Doing.pdf`, Page 1. The verified answer identifies Experience, Reflection, Dialogue, and Understanding.

## Phase 1 Scope

Implemented:

- PDF, DOCX, TXT, and Markdown parsing.
- Page-aware chunks for PDF and structural locators for non-paginated files.
- Idempotent local ingestion with checksums.
- Local Chroma vector search and a basic lexical re-rank.
- Groq token streaming.
- Per-message Groq model selection: GPT-OSS 120B or GPT-OSS 20B.
- Working Quick, Medium, and Deep retrieval-depth profiles.
- Persistent SQLite chat history with sidebar loading and continuation.
- Groq-generated conversation titles based on each chat's first user question.
- Citation validation, source/page links, query-aware snippets, and **Answered from**.
- Evidence confidence calculation and all five glass UI states.
- Explicit no-evidence behavior with Very low confidence.

Chat rename/delete, upload authentication, additional provider families, full re-ranking, and Deep query decomposition are later work.

## Current Limitations

- OCR is intentionally excluded from Phase 1.
- Confidence thresholds are initial values and still need evaluation-set calibration.
- The current stable Next.js release includes a transitive PostCSS security advisory. Heritage does not accept or process user-supplied CSS and binds to localhost, but the dependency should be upgraded when Next.js ships a patched stable release.

## Documentation

- [Product requirements](mds/PRD.md)
- [Architecture](mds/Architechture.md)
- [Design system](mds/Design.md)
- [Delivery phases](mds/Phases.md)
- [Engineering rules](mds/Rules.md)
- [Project memory](mds/Memory.md)
