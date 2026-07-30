# RAG Knowledge Assistant — Product Requirements Document

**Status:** v1.3 — implementation in progress through Phase 4
**Owner:** You
**Target environment:** Localhost (single user, local machine)
**Last updated:** 2026-07-29

---

## 1. Overview

A locally-hosted chat application that lets you ask questions over a folder of your own documents. It combines retrieval-augmented generation (RAG) with a ChatGPT-style, minimalist glass UI. From the same chat input, you can pick which LLM answers the question and how much retrieval "effort" (speed) to spend finding context. A password-protected upload flow lets you add new documents to the knowledge base without restarting anything, and every conversation is saved to a browsable history. Every answer identifies the supporting document(s) and page number(s), and includes an evidence-based confidence indicator.

## 2. Goals

- Answer questions grounded in your own documents, with document and page-level citations.
- Make uncertainty visible with a five-level, evidence-based answer confidence indicator.
- Let you switch between LLM providers/models per message.
- Let you trade off speed vs. retrieval depth per message.
- Let you add new documents to the index through the UI, gated by a password.
- Persist and let you revisit past chats, like ChatGPT/Claude history.
- Clean, minimal, "glass" aesthetic — translucent panels, soft blur, no clutter.
- Run entirely on localhost for now (no auth system, no multi-user, no cloud deploy).

## 3. Non-Goals (v1)

- Multi-user accounts / login system (single password gate for uploads only).
- Cloud deployment or public hosting.
- Fine-tuning or training custom models.
- Real-time collaborative chat.
- Mobile app.

## 4. User Stories

- As the user, I open localhost, see a clean chat screen, and ask a question about my docs.
- As the user, I use Groq in Phase 1 and can choose another configured provider once multi-provider support is added.
- As the user, I pick "Quick," "Medium," or "Deep" depending on how thorough I want the answer.
- As the user, I click an upload control, enter a password, and drop in new files that get added to the searchable index.
- As the user, I see a sidebar of past chats, click one, and continue where I left off.
- As the user, I see which document(s)/snippets an answer was based on.
- As the user, I see the document name and page number for each cited claim, so I can verify the answer.
- As the user, I see how well the answer is supported by my documents, including a clear warning when the information is absent or weakly supported.

## 5. Functional Requirements

### 5.1 Chat Interface
- Central chat window, ChatGPT-style bubbles, streaming token-by-token responses.
- Input bar pinned at the bottom with the two selectors built into it (like ChatGPT's tools row).
- Answers use the clearest question-appropriate Markdown structure: concise
  prose for simple answers, bullets for sets, numbered lists for ordered steps,
  compact tables for comparisons or shared attributes, and short headings only
  for genuinely distinct sections. Formatting must improve comprehension rather
  than decorate the response.
- Each answer supported by retrieved evidence shows citation markers in the answer text and an expandable **Sources** section.
- Every source entry shows the document name, page number or page range, and the supporting snippet. Selecting a citation opens or previews the referenced page when possible.
- The answer footer always summarizes **Answered from** with the document name(s) and page number(s), even when the Sources section is collapsed. A no-evidence response shows **Answered from: No supporting document found**.
- Page locations must come from ingestion metadata; the system must never invent page numbers. For a format with no reliable native pagination, show **Page unavailable** plus the best available section, heading, paragraph, or line locator.
- Each answer includes a visible confidence indicator as specified in §5.7.

### 5.2 Model Selector
- Dropdown/pill in the input bar. v1 candidates:
  - **Groq** (Phase 1 provider; configurable production model)
  - **OpenAI** (GPT-5.6 Terra and GPT-5.6 Luna)
  - **Gemini** (Gemini 3.6 Flash and Gemini 3.5 Flash-Lite)
  - Optional: **Claude** (Anthropic), **local model via Ollama** for a no-API-key option
- Selection is per-message (you can switch mid-conversation) and remembered as the default for the next message.
- Requires you to supply API keys for whichever providers you want active (stored in a local `.env`, never sent anywhere but the provider).

### 5.3 Speed Selector
Controls how much retrieval/reasoning work happens before answering. Maps to concrete backend parameters, not just a label:

| Mode | Chunks retrieved (top-k) | Re-ranking | Query rewriting | Typical latency |
|---|---|---|---|---|
| **Quick** | ~3 | No | No | Fastest |
| **Medium** | ~6–8 | Basic re-rank | No | Balanced (default) |
| **Deep** | ~12–15 | Full re-rank | Yes (query decomposed into sub-questions, results merged) | Slowest, most thorough |

### 5.4 Document Upload (Password Protected)
- An "Add documents" control (e.g. a small lock/upload icon in the sidebar or header — not in the main chat flow, so it can't be triggered accidentally).
- Clicking it prompts for a password before the upload panel appears.
- The initial single-user localhost password is `Password`; only its bcrypt
  hash is stored server-side and it can be overridden through local configuration.
- Password is checked against a locally stored hash (e.g. in `.env` or a small config file) — not a full auth system, just a gate.
- Supports drag-and-drop or file picker; accepts PDF, DOCX, TXT, MD (CSV optional) — matches whatever folder-based ingestion supports.
- On upload: file is chunked, embedded, and added to the vector store; a success confirmation shows what was indexed.
- Also supports pointing at the existing docs folder for a one-time or on-demand re-index (in case you drop files there directly instead of uploading).

### 5.5 Chat History
- Sidebar listing past conversations (auto-titled from the first message, editable).
- Click to reopen and continue any past chat.
- Stored locally (e.g. SQLite) — no cloud sync in v1.
- Delete/rename controls, like standard AI chat apps.
- Pin/unpin controls keep important conversations above recent history.

### 5.6 Glass Minimalist UI
- Frosted-glass panels (translucency + backdrop blur) over a soft gradient or subtly textured background.
- Minimal chrome: thin borders, generous whitespace, no visual noise.
- Sidebar (chat history + upload control) collapsible, glass-panel style.
- Input bar: rounded glass pill, model + speed selectors as small dropdown chips inside/beside it, similar to ChatGPT's toolbar.
- Light and dark mode both supported (glass effect works well in both).

### 5.7 Citations, Grounding, and Answer Confidence

#### Citation requirements
- Each factual answer must be traceable to one or more retrieved chunks.
- Citations use stable markers such as `[1]` in the answer and map to source records containing: document ID, file name/title, page start/end, section/heading when available, chunk ID, and a short supporting snippet.
- Source summaries are deduplicated by document and page range. Multiple documents must all be listed when they materially support the answer.
- PDF page numbers use the page shown to the reader. Other formats retain a page number only when the parser can determine it reliably.
- If the documents conflict, the answer must describe the conflict, cite both sources, and lower confidence.
- If the requested information is not present in the indexed documents, the assistant must say so directly. It must not present general model knowledge as though it came from the documents.

#### Confidence calculation
- Confidence measures **how strongly the indexed documents support the answer**, not how confident the LLM feels.
- The backend returns a score from 0–100, a level, and a short plain-language rationale.
- The score should combine citation coverage, semantic relevance, re-ranker score, agreement across supporting chunks, source/location quality, and penalties for missing evidence or contradictions. Thresholds may be calibrated later, but the labels and response contract remain stable.
- Unsupported answers default to **Very low confidence**. Partially supported answers cannot be rated above **Medium confidence**. A missing reliable page/location reduces confidence.

| Level | Score | Meaning | UI color |
|---|---:|---|---|
| **Very high confidence** | 90–100 | Direct, complete support from highly relevant source passages with reliable locations and no meaningful conflict | Emerald |
| **High confidence** | 75–89 | Strong support with only minor gaps or limited corroboration | Teal |
| **Medium confidence** | 55–74 | Useful but partial, indirect, or mixed support; verification is recommended | Amber |
| **Low confidence** | 30–54 | Weak, incomplete, or conflicting support | Orange |
| **Very low confidence** | 0–29 | No supporting content found, or evidence is too weak to answer reliably | Rose |

#### Confidence component
- Render the current level in a compact frosted-glass badge beside the answer metadata. The badge includes an icon, text label, and color; color is never the only signal.
- Hovering the badge opens a glass popover that shows **all five confidence states**, their colors, meanings, the active state, the numeric score, and the short rationale for this answer.
- Keyboard focus and tap must provide the same popover behavior as hover. The popover must remain readable in light and dark modes and meet WCAG AA contrast.
- When confidence is Low or Very low, show the reason without requiring hover and suggest checking the cited pages or refining the query.

#### Acceptance criteria
- A completed answer with evidence shows at least one valid citation, an **Answered from** summary, and a confidence badge.
- Each citation resolves to the exact stored document and a reliable page/page range, or explicitly shows **Page unavailable** with a structural locator.
- A query whose answer is absent from the documents produces no invented citations, explains the evidence gap, and is rated Very low.
- The confidence popover lists all five states and is equivalent on hover, keyboard focus, and tap.
- Reopening a saved conversation reproduces the original answer, citations, source locations, and confidence state.

## 6. Architecture

```
┌─────────────────────────────┐
│   Frontend (React/Next.js)  │  Glass UI, chat, selectors, upload modal, history sidebar
└───────────────┬─────────────┘
                │ HTTP + SSE/streaming fetch
┌───────────────▼─────────────┐
│   Backend API (FastAPI)     │
│  - /chat   (RAG + LLM call) │
│  - /upload (password-gated) │
│  - /history (CRUD)          │
└───────┬───────────┬─────────┘
        │           │
┌───────▼─────┐ ┌───▼─────────────┐
│ Vector Store │ │ SQLite (history,│
│ (Chroma,     │ │ metadata,       │
│  local)      │ │ upload password │
└───────┬──────┘ │ hash)           │
        │        └─────────────────┘
┌───────▼──────────────┐
│ Local embedding model │  Chroma ONNX all-MiniLM-L6-v2 (free)
└───────────────────────┘
┌───────────────────────┐
│ LLM Provider Layer    │  Groq first; more adapters later
└───────────────────────┘
```

### 6.1 Ingestion Pipeline
1. Load documents from the source folder (or via upload).
2. Split into chunks (e.g. ~500–800 tokens, with overlap).
3. Embed each chunk.
4. Store vectors + provenance metadata (document ID, source filename/title, reader-facing page number or range when reliable, section/heading, chunk ID, chunk text, and content hash) in the vector DB.
5. On new uploads, only the new file(s) are processed — no full re-index needed.

### 6.2 Query Pipeline
1. User submits a question with a chosen model + speed mode.
2. (Deep mode only) Query is decomposed into sub-questions.
3. Relevant chunks retrieved (top-k per speed mode), optionally re-ranked.
4. Context + question sent to the selected LLM provider.
5. Grounded claims are mapped to source records, and the evidence-based confidence score/level is calculated.
6. Response is streamed back to the UI with citation markers, source metadata, and confidence metadata.
7. Turn, citations, and confidence snapshot are saved to the chat's history record.

## 7. Security (v1 scope)

- Upload endpoint gated by a single shared password (hashed, stored locally) — appropriate for a single-user localhost tool, not intended as real multi-tenant auth.
- API keys for LLM providers kept in a local `.env`, never exposed to the frontend.
- No public network exposure — app binds to `localhost` only.

## 8. Non-Functional Requirements

- Runs fully on localhost with a single start command (or two: frontend + backend).
- Should handle a "few hundred" documents comfortably in the local vector store.
- Streaming responses so answers feel responsive even in Deep mode.
- Should be easy to swap in a new LLM provider later (adapter pattern).
- Source locators and confidence metadata must be deterministic enough to persist and render identically when a past chat is reopened.
- Accessibility target: WCAG 2.2 AA for color contrast, keyboard access, focus states, and non-color confidence cues.

## 9. Suggested Tech Stack

| Layer | Recommendation | Why |
|---|---|---|
| Frontend | Next.js + Tailwind CSS | Fast to build glass/blur effects, good ChatGPT-like patterns available |
| Backend | Python + FastAPI | Best ecosystem for RAG (LangChain/LlamaIndex optional), easy streaming |
| Vector DB | Chroma (local, file-based) | Zero-infra, persists to disk, great for localhost |
| Embeddings | Local Chroma ONNX `all-MiniLM-L6-v2` | Free, private, and requires no embedding API |
| Chat history/metadata | SQLite | Zero-config, file-based, plenty for single-user |
| LLM providers | Groq for Phase 1; OpenAI/Gemini in Phase 2; optional Anthropic/Ollama later | Keeps every provider behind the same grounded answer contract |

## 10. Milestones

1. **MVP** — folder ingestion with page-aware provenance, single model, grounded chat, citations, and confidence output; no history/upload UI yet.
2. **Multi-model + Speed modes** — Groq, OpenAI, and Gemini adapters;
   availability-aware model selection; Quick vector, Medium hybrid, and Deep
   query-expansion/full-rerank retrieval.
3. **Password-protected upload** — add-to-index flow from the UI.
4. **Chat history** — sidebar, persistence, rename/delete, and pin/unpin.
5. **Glass UI polish** — final visual pass, answer source treatment, confidence badge/popover, light/dark mode, accessibility, and animations/transitions.

## 11. Open Questions

- Groq, OpenAI, and Gemini are the Phase 2 provider set. Anthropic/Ollama remain optional.
- Roughly how many documents / what total size will the full corpus contain?
- Do you want the docs folder auto-watched for changes, or is a manual "re-index" button enough?
- Any preference between Chroma and alternatives (e.g. Qdrant, FAISS) — Chroma is recommended for simplicity but not mandatory.
- One shared upload password is confirmed for the single-user localhost version.

---

*Next step: finish per-file asynchronous upload progress/retry, date-grouped
history, provider credential verification, and release hardening.*
