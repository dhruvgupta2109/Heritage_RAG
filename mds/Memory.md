# Heritage RAG — Project Memory

This file is the concise handoff record for future work. Update it whenever a decision changes, a phase is completed, or a new blocker appears. Do not use it as a replacement for the PRD or architecture.

**Last updated:** 2026-07-29

**Current phase:** Phase 1 complete; Phase 2 implementation complete pending valid OpenAI/Gemini credentials; Phase 3 and Phase 4 substantially implemented

**Implementation status:** Runnable local multi-provider RAG app with Groq
generation, dormant OpenAI/Gemini adapters, local hybrid/full re-ranking, Deep
query decomposition, citations, confidence, evaluation data, password-gated
document uploads, persistent chat actions, and a connected glass chat UI.

## Current Product Definition

Heritage RAG is a single-user, localhost document assistant with:

- RAG answers grounded in local PDF, DOCX, TXT, and MD files.
- Inline citations plus an always-visible **Answered from** document/page summary.
- A five-level evidence confidence system: Very high, High, Medium, Low, and Very low.
- A glass confidence badge whose hover/focus/tap popover explains all five states and highlights the active state.
- Per-message model choice and Quick, Medium, or Deep retrieval.
- Password-gated uploads and manual folder re-indexing.
- Local chat history with rename, pin/unpin, and confirmed deletion.
- A minimalist glass UI with light/dark themes and WCAG 2.2 AA behavior.

## Confirmed Decisions

- Frontend: Next.js with Tailwind CSS.
- Backend: FastAPI.
- Persistence: Chroma for vector search and SQLite for conversations/document lifecycle.
- Phase 1 generation provider: Groq using the configurable `GROQ_MODEL`; current default is `openai/gpt-oss-120b`.
- Embeddings: Chroma's free local ONNX `all-MiniLM-L6-v2` model. No hosted vector database is required.
- Source folder: `/Users/deepakgupta/Desktop/HERITAGE/DOCS`.
- Target runtime: loopback-only localhost.
- Default retrieval mode: Medium.
- Answer confidence measures document support, not model certainty.
- Every provider uses one shared adaptive-formatting contract: concise prose,
  bullets, numbered steps, comparison tables, or short sections according to
  whichever structure makes the specific answer easiest to understand.
- No source evidence means Very low confidence and an explicit no-support response.
- Page numbers must come from reliable extraction metadata. If unavailable, show **Page unavailable** and a section/paragraph/line locator; never fabricate a page.
- Answer text, citations, **Answered from**, and confidence snapshots are stored together so history is reproducible.
- Manual folder re-indexing is the initial default.
- Document upload uses the shared local password `Password`, stored as a bcrypt
  hash, with a 10-minute HTTP-only session and five-attempt rate limit.
- Uploaded files are limited to 25 MB each and PDF, DOCX, TXT, or MD.
- OCR is not required for the current corpus.

## Phase 1 Completed

- Added the Next.js glass chat UI and connected it to the streaming API.
- Added the FastAPI application, health check, CORS, source-file preview, and re-index route.
- Added PDF, DOCX, TXT, and MD extraction with page/structural provenance.
- Added checksum-based idempotent ingestion. The current corpus has three PDFs and 12 indexed chunks.
- Added persistent Chroma search with local embeddings and basic lexical re-ranking.
- Added a Groq provider adapter with provider-safe error handling.
- Added per-message selection between GPT-OSS 120B and GPT-OSS 20B.
- Added functional Quick, Medium, and Deep retrieval profiles.
- Added OpenAI Responses API and Gemini Generate Content adapters. Their models
  remain disabled until the corresponding key authenticates and grants model access.
- Added provider health/model-access checks, normalized safe errors, timeouts,
  cancellation-safe streaming, and transient retries.
- Upgraded Deep retrieval to LLM query expansion plus local vector/BM25/RRF
  re-ranking; no hosted reranker or vector database is required.
- Added Markdown rendering for paragraphs, numbered lists, emphasis, and clickable citations.
- Added citation validation and normalization, including decorative bracket variants returned by providers.
- Added query-aware evidence snippets and page-opening source links.
- Added server-side confidence scoring and the five-state badge/popover UI.
- Added SQLite schemas and persisted answer/citation/confidence snapshots.
- Added persistent chat list/detail APIs, sidebar navigation, new-chat behavior, and full historical answer rehydration.
- Added Groq-generated titles from the first user query with a safe fallback when the provider is unavailable.
- Added a 25-question corpus evaluation set covering direct, comparison,
  multi-step, calendar/table, and no-answer cases.
- Medium and Deep retrieval locate the expected document/page for all 21
  answerable evaluation cases; Quick locates 18/21 by design.
- Added persistent chat rename, pin/unpin, and confirmed deletion with automatic
  migration of existing SQLite data.
- Added password-gated multi-document upload, secure session/rate limiting,
  content and size validation, safe naming, duplicate detection, and immediate indexing.
- Hid the Next.js development indicator from the app preview.
- Added 34 passing backend tests, three focused web Markdown-rendering tests,
  and a successful production frontend build.
- Verified the known answer: Experience, Reflection, Dialogue, and Understanding from `Experiential Learning at HXLS Noida | Learning by Doing.pdf`, Page 1, with High confidence.
- Verified an unrelated query returns no source and Very low confidence.

## Documentation Completed

- `mds/PRD.md`: product requirements and confidence/source additions.
- `mds/Architechture.md`: system structure, data contracts, API boundaries, security, and persistence.
- `mds/Design.md`: UI rules, glass tokens, answer/source anatomy, and confidence interactions.
- `mds/Phases.md`: implementation sequence, deliverables, and exit criteria.
- `mds/Rules.md`: mandatory engineering, grounding, security, and accessibility rules.
- `README.md`: project overview and documentation map.

## Open Product Decisions

- Approximate number and total size of source documents.
- Whether Anthropic or Ollama should be added after OpenAI/Gemini credentials work.
- Whether folder auto-watch is worth adding after manual re-index.
- Whether DOCX should be converted/rendered to create stable page locations or use structural locators only.
- Whether CSV should be supported in addition to the current 25 MB
  PDF/DOCX/TXT/MD upload contract.

These decisions should be captured in the PRD, Architecture, and this file when resolved.

## Next Recommended Work

Review the connected upload and history controls locally, then:

1. Add asynchronous per-file upload stage updates and explicit retry.
2. Add date grouping to long chat histories.
3. Replace the invalid OpenAI/Gemini credentials and run provider contract checks.
4. Expand and calibrate the evaluation set as more documents are added.

## Known Risks

- PDF text extraction and displayed page labels may differ for scanned or front-matter-heavy documents.
- DOCX/TXT/MD do not always have stable native pages.
- LLM-generated citation markers can be invalid unless checked against retrieved chunk IDs.
- Confidence scores will need calibration against a labeled evaluation set.
- Cloud providers receive retrieved document text; the UI and setup guide must disclose this.
- Glass/translucent visuals can fail contrast requirements without opaque fallbacks.
- Next.js 16.2.12 currently includes a transitive PostCSS advisory. Current use is localhost-only with repository-controlled CSS; upgrade when a patched stable Next.js version is available.

## Change Log

### 2026-07-29

- Expanded the PRD to require document/page provenance and evidence confidence.
- Defined the five confidence states, thresholds, colors, fallback behavior, and popover interaction.
- Filled the project architecture, design, phase plan, engineering rules, and README from the PRD.
- Implemented and verified the Phase 0 foundation and Phase 1 grounded RAG MVP.
- Fixed answer Markdown rendering and connected the model/retrieval menus to per-message backend behavior.
- Connected persistent chat history and API-generated conversation titles end to end.
- Implemented the Phase 2 provider adapters, availability-aware model menu,
  Deep query expansion, local full re-ranking, and corpus evaluation set.
- Added protected multi-document upload and persistent rename/pin/delete chat actions.
- Added shared adaptive Markdown answer formatting across all providers, with
  citations required on factual prose, list items, and table rows.
- Added complete answer typography and spacing for headings, paragraphs, nested
  lists, tables, quotations, links, code, separators, task lists, and images.
  Wide tables now scroll within an accessible bordered region, and citation
  punctuation spacing is repaired for both new and historical answers.
