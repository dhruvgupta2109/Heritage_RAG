# Heritage RAG — Project Memory

This file is the concise handoff record for future work. Update it whenever a decision changes, a phase is completed, or a new blocker appears. Do not use it as a replacement for the PRD or architecture.

**Last updated:** 2026-07-29

**Current phase:** Phase 1 complete; Phase 2 and Phase 4 slices started

**Implementation status:** Runnable local MVP with Groq generation, local embeddings, Chroma retrieval, citations, page provenance, confidence, persistent chat history, and a connected glass chat UI.

## Current Product Definition

Heritage RAG is a single-user, localhost document assistant with:

- RAG answers grounded in local PDF, DOCX, TXT, and MD files.
- Inline citations plus an always-visible **Answered from** document/page summary.
- A five-level evidence confidence system: Very high, High, Medium, Low, and Very low.
- A glass confidence badge whose hover/focus/tap popover explains all five states and highlights the active state.
- Per-message model choice and Quick, Medium, or Deep retrieval.
- Password-gated uploads and manual folder re-indexing.
- Local chat history with rename/delete.
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
- No source evidence means Very low confidence and an explicit no-support response.
- Page numbers must come from reliable extraction metadata. If unavailable, show **Page unavailable** and a section/paragraph/line locator; never fabricate a page.
- Answer text, citations, **Answered from**, and confidence snapshots are stored together so history is reproducible.
- Manual folder re-indexing is the initial default.
- OCR is not required for the current corpus.

## Phase 1 Completed

- Added the Next.js glass chat UI and connected it to the streaming API.
- Added the FastAPI application, health check, CORS, source-file preview, and re-index route.
- Added PDF, DOCX, TXT, and MD extraction with page/structural provenance.
- Added checksum-based idempotent ingestion. The current corpus has three PDFs and 12 indexed chunks.
- Added persistent Chroma search with local embeddings and basic lexical re-ranking.
- Added a Groq provider adapter with provider-safe error handling.
- Added per-message selection between GPT-OSS 120B and GPT-OSS 20B.
- Added functional Quick, Medium, and Deep retrieval profiles; full re-ranking and Deep query decomposition remain pending.
- Added Markdown rendering for paragraphs, numbered lists, emphasis, and clickable citations.
- Added citation validation and normalization, including decorative bracket variants returned by providers.
- Added query-aware evidence snippets and page-opening source links.
- Added server-side confidence scoring and the five-state badge/popover UI.
- Added SQLite schemas and persisted answer/citation/confidence snapshots.
- Added persistent chat list/detail APIs, sidebar navigation, new-chat behavior, and full historical answer rehydration.
- Added Groq-generated titles from the first user query with a safe fallback when the provider is unavailable.
- Added 17 passing backend tests and a successful production frontend build.
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
- Which additional providers should be added in Phase 2.
- Whether folder auto-watch is worth adding after manual re-index.
- Whether DOCX should be converted/rendered to create stable page locations or use structural locators only.
- Maximum upload size and allowed CSV behavior.

These decisions should be captured in the PRD, Architecture, and this file when resolved.

## Next Recommended Work

Review the running Phase 1 experience locally, then either calibrate confidence against a larger document set or begin Phase 2:

1. Add representative documents and expected-answer/no-answer questions.
2. Measure retrieval quality and tune the minimum relevance and confidence weights.
3. Add full re-ranking and Deep query decomposition behind the existing depth selector.
4. Add another provider family when its key or local runtime is available.

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
