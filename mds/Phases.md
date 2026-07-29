# Heritage RAG — Delivery Phases

**Status:** Phase 0 and Phase 1 complete; Phase 2 implemented pending external-provider credential verification; Phase 3 and Phase 4 substantially implemented

**Last updated:** 2026-07-29

Each phase should finish with a demonstrable vertical slice and automated checks. A phase is complete only when its exit criteria pass; a UI mock without the connected behavior is not a completed feature.

## Phase 0 — Foundation ✅

**Goal:** Establish a runnable local system and stable contracts.

Deliverables:

- Next.js + Tailwind frontend scaffold.
- FastAPI backend scaffold with health endpoint.
- Typed environment configuration and `.env.example`.
- Local data directories, gitignore rules, and one start command.
- SQLite schema/migrations for chats, messages, documents, and ingestion jobs.
- Provider, retrieval, citation, and confidence interfaces.
- Shared API schemas for source locations and the five confidence states.
- Small test corpus with known document/page answers.

Exit criteria:

- Frontend can reach the backend health endpoint.
- Fresh setup runs from documented commands without hand-created database state.
- No secrets or runtime data are committed.
- Contract tests accept all five confidence enum values and nullable page metadata.

## Phase 1 — Grounded RAG MVP ✅

**Goal:** Ask a question against a local folder and receive a verifiable answer.

Deliverables:

- PDF, DOCX, TXT, and MD parsing.
- Page/section-aware chunking, embeddings, and Chroma persistence.
- Idempotent folder ingestion using content checksums.
- Single provider adapter and Medium retrieval mode.
- Streaming chat answer.
- Inline citation markers, source list, and **Answered from** document/page summary.
- Server-side citation validation.
- Initial evidence confidence score, level, and rationale.
- Explicit no-support response with Very low confidence.

Exit criteria:

- Known-answer test questions cite the expected document and page.
- No-answer tests do not fabricate a source or page and return Very low confidence.
- A citation can always be resolved to an indexed chunk.
- Formats without reliable pagination show **Page unavailable** plus a structural locator.
- Refreshing or restarting does not require re-embedding unchanged documents.

## Phase 2 — Models and Retrieval Modes

**Goal:** Make provider and retrieval depth selectable per message.

Current progress:

- Complete: selectable Groq models with per-message persistence.
- Complete: working Quick, Medium, and Deep chunk-depth profiles.
- Complete: OpenAI and Gemini adapters, provider/model health, and unavailable states.
- Complete: local full re-ranking and LLM-driven Deep query decomposition.
- Complete: normalized errors, timeouts, cancellation-safe streaming, and retries.
- Complete: 25-question corpus evaluation set and retrieval baseline.
- Pending: live OpenAI/Gemini contract verification once valid keys are supplied.
- Pending: broader answer/confidence calibration as the corpus grows.

Deliverables:

- OpenAI and Gemini adapters when keys are available.
- Optional Anthropic/Ollama adapter behind configuration.
- Quick, Medium, and Deep retrieval profiles.
- Basic/full re-ranking and Deep query decomposition.
- Model and speed chips in the composer; selection is retained for the next message.
- Provider error normalization, timeouts, cancellation, and retry.
- Confidence calibration across retrieval modes.

Exit criteria:

- Switching model or speed affects only the submitted message and is persisted with it.
- Quick/Medium/Deep use their documented backend parameters.
- All enabled providers produce the same internal citation/confidence schema.
- Provider self-reported confidence cannot override the application score.

## Phase 3 — Password-Gated Uploads

**Goal:** Add and index documents safely without restarting.

Current progress:

- Complete: bcrypt-backed universal upload password (`Password` by default).
- Complete: 10-minute HTTP-only upload session and rate-limited unlock attempts.
- Complete: password dialog, multi-file picker, and drag-and-drop panel.
- Complete: PDF/DOCX/TXT/MD validation, 25 MB limit, safe naming, and path protection.
- Complete: content-hash duplicate detection and immediate per-file indexing.
- Complete: success, duplicate, partial-failure feedback and manual folder re-index.
- Pending: asynchronous per-file stage updates and an explicit retry action.

Deliverables:

- Upload unlock flow backed by a secure password hash.
- Short-lived upload session, rate limiting, and generic password errors.
- Drag-and-drop/file picker for supported types.
- File validation, safe naming, size limits, and path-traversal protection.
- Asynchronous ingestion status per file.
- Duplicate, success, partial failure, and retry UI.
- Manual folder re-index action.

Exit criteria:

- Upload routes cannot be used before unlock.
- A successful upload becomes searchable without a process restart.
- Duplicate content is detected and does not create duplicate chunks.
- Failed or partially indexed files do not appear ready.
- Re-index leaves unchanged files untouched.

## Phase 4 — Persistent Chat History

**Goal:** Reopen and continue prior conversations faithfully.

Current progress:

- Complete: SQLite-backed chat/message persistence and list/detail APIs.
- Complete: Groq title generation from the first user query.
- Complete: sidebar navigation, new-chat flow, continuation, and historical source/confidence replay.
- Complete: rename, pin/unpin, and delete-with-confirmation controls.
- Pending: date-grouped history.

Deliverables:

- Chat/message persistence in SQLite.
- Auto-title, rename, delete with confirmation, and history grouping.
- Sidebar navigation and new-chat flow.
- Stored model, retrieval mode, citations, confidence, and message status.
- Historical source preview using the saved provenance snapshot.

Exit criteria:

- Restarting the application preserves all completed conversations.
- A reopened answer displays the same text, source pages, and confidence state.
- Rename/delete behavior is keyboard accessible.
- Missing or replaced source files show a clear unavailable state without rewriting history.

## Phase 5 — Glass UI and Accessibility

**Goal:** Deliver the polished visual system and complete trust interactions.

Deliverables:

- Shared glass, typography, spacing, theme, and motion tokens.
- Responsive desktop/mobile layouts and collapsible drawers.
- Light and dark themes plus reduced transparency/motion fallbacks.
- Five-color confidence badge with icon and full label.
- Hover/focus/tap confidence popover listing all five states and highlighting the active state.
- Inline rationale for Low and Very low confidence.
- Source drawer with page navigation where supported.
- Loading, empty, stopped-stream, error, and no-evidence states.

Exit criteria:

- WCAG 2.2 AA contrast and keyboard checks pass.
- Confidence never relies on color alone.
- The confidence legend is fully usable with mouse, keyboard, and touch.
- Answered-from citations remain visible when Sources is collapsed.
- Core layouts are verified at 360 px, tablet, and desktop widths.

## Phase 6 — Evaluation and Release Hardening

**Goal:** Make the local v1 reliable, measurable, and ready for daily use.

Deliverables:

- Labeled retrieval/answer evaluation set covering direct, partial, conflicting, and absent evidence.
- Confidence threshold calibration and regression tests.
- Prompt-injection and malicious document tests.
- Performance measurements for a few hundred documents.
- Backup/restore instructions for documents, Chroma, and SQLite.
- Structured local logs with sensitive-content redaction.
- Full setup, troubleshooting, and privacy/provider disclosure documentation.

Exit criteria:

- Citation precision, answer groundedness, and no-answer behavior meet agreed targets.
- Confidence states are reasonably calibrated on the evaluation set.
- Core end-to-end tests pass in light/dark themes and each retrieval mode.
- A new local installation can be completed from the README.
- Known limitations are documented and accepted.

## Cross-Phase Quality Gates

At every phase:

- Run formatting, linting, type checks, and relevant tests.
- Add tests for each bug fixed.
- Keep API/data contracts backward-compatible or add a migration.
- Update `mds/Memory.md` with completed work, decisions, next steps, and risks.
- Never mark a feature complete until the connected user path works.
