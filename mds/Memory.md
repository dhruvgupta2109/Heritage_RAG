# Heritage RAG — Project Memory

This file is the concise handoff record for future work. Update it whenever a decision changes, a phase is completed, or a new blocker appears. Do not use it as a replacement for the PRD or architecture.

**Last updated:** 2026-07-30

**Current phase:** Phases 0–5 complete; Phase 6 release hardening is in progress

**Implementation status:** Runnable local multi-provider RAG app with Groq
generation, availability-aware OpenAI/Gemini adapters, local hybrid/full re-ranking, Deep
query decomposition, citations, confidence, evaluation data, password-gated
application access and document uploads, persistent chat actions, and a
connected glass chat UI.
Phase 5 includes persistent light/dark themes, accessible confidence
interaction, an in-app source/page drawer, and stopped-stream preservation.
Phase 6 now includes deterministic answer/confidence evaluation,
malicious-document defenses, structured redacted logs, recovery tooling, and a
recorded 300-document local performance benchmark.
The complete workspace and its non-auth API routes now sit behind the shared
`Password` login with a 12-hour HTTP-only session.

## Current Product Definition

Heritage RAG is a single-user, localhost document assistant with:

- RAG answers grounded in local PDF, DOCX, TXT, and MD files.
- Inline citations plus an always-visible **Answered from** document/page summary.
- A five-level evidence confidence system: Very high, High, Medium, Low, and Very low.
- A glass confidence badge whose hover/focus/tap popover explains all five states and highlights the active state.
- Per-message model choice and Quick, Medium, or Deep retrieval.
- Password-gated uploads with per-file progress/retry and manual folder re-indexing.
- Universal local chat history with date grouping, rename, pin/unpin, and confirmed deletion.
- A minimalist glass UI with light/dark themes and WCAG 2.2 AA behavior.
- A minimalist shared-password entry screen that opens the complete workspace.

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
- Conversations are universal within this localhost installation: every browser
  connected to the same FastAPI/SQLite backend sees the same chat history.
  Per-user/private history requires accounts and is outside v1.
- Manual folder re-indexing is the initial default.
- The complete application uses the shared local password `Password`, stored as
  a bcrypt hash, with a rate-limited 12-hour HTTP-only session. The same
  authenticated session authorizes document uploads without a second prompt.
- Uploaded files are limited to 25 MB each and PDF, DOCX, TXT, or MD.
- OCR is not required for the current corpus.
- Partial evidence is capped at Medium confidence and acknowledged conflicting
  evidence is capped at Low confidence.
- Runtime logs are rotating JSON Lines with sensitive fields and secret-shaped
  values redacted. Raw questions, answers, and document bodies are not logged.
- Backups include documents, Chroma, and a consistent SQLite snapshot, but
  exclude `.env` and logs.

## Phases 0–4 Completed

- Added the Next.js glass chat UI and connected it to the streaming API.
- Added the FastAPI application, health check, CORS, source-file preview, and re-index route.
- Added PDF, DOCX, TXT, and MD extraction with page/structural provenance.
- Added checksum-based idempotent ingestion. The current corpus has four PDFs and 16 indexed chunks.
- Added persistent Chroma search with local embeddings and basic lexical re-ranking.
- Added a Groq provider adapter with provider-safe error handling.
- Added per-message selection between GPT-OSS 120B and GPT-OSS 20B.
- Added functional Quick, Medium, and Deep retrieval profiles.
- Added OpenAI Responses API and Gemini Generate Content adapters. Their models
  remain disabled until the corresponding key authenticates and grants model access.
- Phase 2 is implementation-complete: provider adapters, shared schemas,
  availability behavior, retrieval modes, timeouts, and retries are covered by
  automated tests. Live OpenAI/Gemini authentication is an operational check
  awaiting valid keys and does not block Phase 5.
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
- Added real per-file transfer progress, processing/indexing states, durable
  indexed/duplicate/failure outcomes, and one-click retry.
- Added date-grouped history for pinned chats, Today, Yesterday, Previous 7
  days, Previous 30 days, and older month/year groups.
- Hid the Next.js development indicator from the app preview.
- Added 34 passing backend tests, 13 focused web rendering/interaction tests,
  and a successful production frontend build.
- Verified the known answer: Experience, Reflection, Dialogue, and Understanding from `Experiential Learning at HXLS Noida | Learning by Doing.pdf`, Page 1, with High confidence.
- Verified an unrelated query returns no source and Very low confidence.

## Phase 6 Work Implemented

- Added `evals/answer_cases.json` with labeled direct, partial, conflicting,
  absent, multi-source, and adversarial-document answer cases.
- Added deterministic scoring for citation precision, answer groundedness,
  confidence accuracy, expected answer terms, and no-answer behavior.
- Calibrated confidence with completeness and contradiction factors; partial
  support cannot exceed 74/Medium and conflict cannot exceed 54/Low.
- Hardened provider prompts by treating document text as JSON-encoded untrusted
  data, escaping structural delimiters, and rejecting instructions embedded in
  sources.
- Added structured request, retrieval, completion, and failure logs with
  request IDs, latency, provider/model, chunk IDs, and confidence factors.
- Added field/value redaction and rotating local log files.
- Added versioned ZIP backup, checksum inspection, path-safe restore, consistent
  SQLite snapshotting, and explicit replacement protection.
- Added a repeatable isolated 300-document Chroma benchmark. The recorded run
  indexed 300 synthetic documents in 3.142 seconds; retrieval p95 was
  68.56 ms Quick, 68.89 ms Medium, and 68.77 ms Deep on the local development
  machine.
- Recorded the quality baseline: Quick 18/21, Medium 21/21, Deep 21/21 expected
  document/page hits; deterministic labeled answer metrics are all 100%.
- Added operations, privacy/provider disclosure, and known-limitations guides.
- Added the minimalist application login, protected every non-auth API route,
  restored authenticated sessions on reload, and added explicit logout.
- Authenticated entry now opens a fresh **New conversation** while retaining
  the shared history in the sidebar.
- Reused the application session for document uploads while preserving the
  legacy short-lived upload unlock as a compatibility fallback.
- Expanded backend coverage from 34 to 43 passing tests and web coverage to 15
  focused tests.

## Documentation Completed

- `mds/PRD.md`: product requirements and confidence/source additions.
- `mds/Architechture.md`: system structure, data contracts, API boundaries, security, and persistence.
- `mds/Design.md`: UI rules, glass tokens, answer/source anatomy, and confidence interactions.
- `mds/Phases.md`: implementation sequence, deliverables, and exit criteria.
- `mds/Rules.md`: mandatory engineering, grounding, security, and accessibility rules.
- `README.md`: project overview and documentation map.

## Open Product Decisions

- Approximate number and total size of source documents.
- Whether Anthropic or Ollama should be added after live OpenAI/Gemini verification.
- Whether folder auto-watch is worth adding after manual re-index.
- Whether DOCX should be converted/rendered to create stable page locations or use structural locators only.
- Whether CSV should be supported in addition to the current 25 MB
  PDF/DOCX/TXT/MD upload contract.

These decisions should be captured in the PRD, Architecture, and this file when resolved.

## Next Recommended Work

1. Run final connected web/API verification, then obtain release sign-off on
   the documented v1 limitations.
2. When valid OpenAI/Gemini credentials are available, run the optional live
   authentication checks; this is not a Phase 5 prerequisite.
3. Expand and recalibrate the evaluation set as more documents are added.

## Known Risks

- PDF text extraction and displayed page labels may differ for scanned or front-matter-heavy documents.
- DOCX/TXT/MD do not always have stable native pages.
- LLM-generated citation markers can be invalid unless checked against retrieved chunk IDs.
- Confidence calibration currently relies on a small deterministic labeled set;
  expand it as real answer and conflict patterns are observed.
- Cloud providers receive retrieved document text; the UI and setup guide must disclose this.
- Glass/translucent visuals can fail contrast requirements without opaque fallbacks.
- Next.js 16.2.12 currently includes a transitive PostCSS advisory. Current use is localhost-only with repository-controlled CSS; upgrade when a patched stable Next.js version is available.

## Change Log

### 2026-07-30

- Added an application-wide shared-password gate with a 12-hour HTTP-only
  session, minimalist themed login screen, session restoration, and logout.
- Reused the verified application session for uploads so users enter the
  password only once.
- Started Phase 6 release hardening with labeled answer evaluation, calibrated
  partial/conflict confidence behavior, prompt-injection defenses, structured
  redacted logs, backup/restore tooling, a 300-document performance benchmark,
  and complete local operations/privacy/limitations documentation.
- Completed Phase 5 after user verification of the responsive visual and
  keyboard experience at mobile, tablet, and desktop sizes.
- Started Phase 5 with shared visual tokens, persistent light/dark themes,
  dark-theme component surfaces, and reduced-effect fallbacks.
- Added accessible confidence popover state for hover, focus, tap,
  outside-click, and Escape behavior.
- Added an in-app source drawer with focus containment/restoration, cited-page
  preview, page navigation, and original-file access.
- Added modal focus containment and return-focus behavior for rename, delete,
  and document-upload dialogs.
- Added answer-stream cancellation with retained partial text and an explicit
  **Stopped** state that does not display completed confidence.
- Added immediate-submit grounded prompts plus query Copy/Edit-and-resend and
  response Copy/Retry actions with copied/editing feedback.
- Expanded web coverage to 13 tests, including grounded starter prompts,
  theme/responsive modes, and AA
  contrast checks for every confidence state in both themes.
- Completed Phase 3 with real per-file upload progress, processing/indexing
  feedback, independent final outcomes, expired-session recovery, and retry.
- Completed Phase 4 with calendar date-grouped history.
- Confirmed that chat history and the document corpus are universal to the
  single local backend rather than isolated by browser.
- Reconciled all project documentation: Phases 0–4 are complete and Phase 5 is
  the next implementation phase. OpenAI/Gemini live authentication remains a
  credential-dependent operational check, not unfinished Phase 2 code.

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
