# Heritage RAG — Project Rules

These rules turn the PRD into mandatory engineering and product constraints. If a rule conflicts with a later approved requirement, update the PRD, architecture, design, phases, and this file in the same change.

## 1. Product Scope

- Build for one user on localhost in v1.
- Bind frontend/backend services to loopback unless the user explicitly opts into another network configuration.
- Keep upload protection separate from a full account/login system.
- Avoid adding cloud deployment, collaboration, fine-tuning, or unrelated administration features to v1.

## 2. Grounding and Answer Rules

- Answer document questions from retrieved indexed evidence.
- Every material factual claim must map to at least one valid retrieved chunk.
- Every completed answer with evidence must show inline citations and an expandable source list.
- Every completed answer must show an **Answered from** summary. When no evidence exists, it reads **No supporting document found** and no citation is fabricated.
- Persist document ID, file name/title, chunk ID, page start/end, structural locator, and supporting snippet for each citation.
- Never invent a source, quotation, page number, or confidence rationale.
- For PDF, use reader-facing page metadata from extraction. For any format without reliable pagination, display **Page unavailable** and the best section/heading/paragraph/line locator.
- If documents disagree, state the conflict, cite all relevant sources, and reduce confidence.
- If the answer is absent from the indexed documents, say so plainly and return Very low confidence. Do not disguise general model knowledge as document evidence.
- Validate provider-produced citation IDs against the retrieved chunk allowlist before returning them.

## 3. Confidence Rules

- Confidence represents evidence support in the indexed documents, not model certainty and not a universal truth score.
- Use exactly five public labels and stable API values:

| API value | UI label | Score |
|---|---|---:|
| `very_high` | Very high confidence | 90–100 |
| `high` | High confidence | 75–89 |
| `medium` | Medium confidence | 55–74 |
| `low` | Low confidence | 30–54 |
| `very_low` | Very low confidence | 0–29 |

- Calculate confidence server-side from measurable evidence signals.
- No supporting source must resolve to Very low. Partial support cannot exceed Medium. Missing reliable location metadata applies a penalty.
- Return and persist the score, label, short rationale, and factor snapshot.
- The UI must show the full text label and a non-color icon in addition to color.
- Hover, keyboard focus, and tap on the glass confidence badge must show all five states, ranges, meanings, and the active state.
- Low and Very low rationales must be visible without hover.
- A canceled, interrupted, or failed answer must be marked incomplete and must not display a completed high-confidence rating.

## 4. Technology and Architecture

- Use Next.js + Tailwind CSS for the frontend and FastAPI for the backend.
- Use SQLite for chats/metadata and Chroma for local vector retrieval unless an architecture decision explicitly replaces them.
- Keep LLM providers behind one adapter contract; do not spread provider-specific response handling through business logic.
- Keep retrieval, generation, citation validation, and confidence evaluation as separate testable services.
- Use typed request/response schemas on both sides of the API.
- Use SSE or streaming fetch for v1 answer streaming unless two-way real-time behavior becomes necessary.
- Treat the final completion event as authoritative for sources and confidence.

## 5. Document and Data Handling

- Support PDF, DOCX, TXT, and MD in v1. Treat CSV as optional until its behavior is specified.
- Store original files, checksums, ingestion status, and chunk provenance.
- Make ingestion and re-indexing idempotent.
- Do not cross document boundaries when chunking, and avoid crossing page boundaries when practical.
- Never expose a partially indexed file as ready.
- Coordinate deletion/replacement across SQLite, Chroma, and local file storage; surface partial failures.
- Historical answers retain citation/confidence snapshots even if their source is later removed.

## 6. Security and Privacy

- Never expose provider keys or password hashes to the frontend.
- Keep secrets in ignored environment files; commit only an `.env.example`.
- Hash upload passwords with Argon2id or bcrypt; do not use reversible encryption or a fast general-purpose hash.
- Rate-limit unlock attempts and issue only a short-lived upload session.
- Validate MIME/content, extension, size, and file name; block path traversal and executable uploads.
- Treat document contents as untrusted prompt input. Delimit evidence and prevent it from changing system or security instructions.
- Do not log passwords, tokens, API keys, raw document bodies, or full prompts/answers by default.
- Clearly disclose when a cloud provider will receive retrieved document text.

## 7. UX and Accessibility

- Follow the tokens and component behavior in `Design.md`; do not create one-off glass styles.
- Glass effects must have an opaque fallback and remain readable without blur.
- Meet WCAG 2.2 AA contrast and provide visible focus.
- Make every hover-only interaction available through keyboard focus and touch.
- Do not use color as the only indication of confidence, error, success, or selection.
- Use semantic controls and accessible names for citation markers, dialogs, drawers, disclosures, and message actions.
- Respect reduced motion and reduced transparency preferences.
- Keep **Add documents** outside the main message flow to avoid accidental activation.

## 8. Code and Quality

- Keep modules small and cohesive; prefer explicit data flow over hidden global state.
- Validate all external input at API and parser boundaries.
- Add unit tests for chunk provenance, citation validation, confidence mapping, provider adapters, and security checks.
- Add integration tests for ingestion-to-answer, no-evidence, conflicting-source, upload, and history replay paths.
- Use a fixed test corpus with expected source pages to catch provenance regressions.
- Run formatting, linting, type checking, and tests before declaring a phase complete.
- Add a regression test for every production bug fixed.
- Do not silently swallow errors; return safe user messages and retain useful redacted diagnostics.

## 9. Documentation and Change Control

- `PRD.md` owns product intent and acceptance requirements.
- `Architechture.md` owns component boundaries, data contracts, and technical decisions.
- `Design.md` owns visual/interaction rules.
- `Phases.md` owns delivery order and exit criteria.
- `Memory.md` owns current status, decisions, risks, and next step.
- Update affected documents when behavior or a public contract changes.
- Record unresolved product decisions in `Memory.md`; do not let implementation defaults become invisible requirements.

## 10. Definition of Done

A feature is done only when:

- The complete user path works against real connected components.
- Success, empty, loading, cancellation, and error states are handled where applicable.
- Grounded answers expose valid document/page evidence and confidence.
- Security/privacy requirements are met.
- Keyboard, touch, theme, and contrast behavior are verified.
- Automated tests cover the main behavior and important failure modes.
- Relevant docs and `Memory.md` are current.
