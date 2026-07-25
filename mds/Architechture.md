# Heritage RAG — Architecture

> This filename is retained for compatibility. The canonical project architecture is defined here.

**Status:** Phases 0–5 implemented; Phase 6 release hardening in progress

**Target:** Single-user localhost application

**Last updated:** 2026-07-30

## 1. System Context

Heritage RAG is a local document question-answering application. A Next.js client sends a question, model choice, and retrieval mode to a FastAPI backend. The backend retrieves relevant document chunks from Chroma, asks the selected LLM to answer only from that evidence, streams the result, and persists the turn in SQLite.

The system has four durable responsibilities:

1. Ingest files while preserving verifiable source locations.
2. Retrieve and rank evidence according to the selected speed mode.
3. Generate a grounded answer with citations and evidence-based confidence.
4. Preserve conversations, citations, and confidence metadata for later replay.

## 2. High-Level Architecture

```text
Browser
  └─ Next.js UI
      ├─ Shared-password login and session restoration
      ├─ Chat and streaming answer renderer
      ├─ Model and speed selectors
      ├─ Source/page preview
      ├─ Confidence badge and five-state popover
      ├─ History sidebar
      └─ Session-authorized upload dialog
             │ HTTP + SSE (or streaming fetch)
             ▼
      FastAPI application
      ├─ Chat orchestration service
      ├─ Retrieval and re-ranking service
      ├─ Citation/grounding service
      ├─ Confidence evaluator
      ├─ Ingestion service
      ├─ Provider router and adapters
      └─ History service
          ├─ Chroma: vectors + chunk provenance
          ├─ SQLite: chats, messages, documents, jobs
          ├─ Local documents directory
          └─ External LLM/embedding APIs when configured
```

Only the backend can read provider keys, compare the shared password hash,
issue the HTTP-only application session, write documents, or access the vector
store. All non-authentication API routes require that session.

## 3. Proposed Repository Layout

```text
apps/
  web/                    # Next.js frontend
  api/                    # FastAPI backend
    app/
      api/                # Route definitions
      core/               # Configuration, logging, security
      ingestion/          # Parsers, page metadata, chunking, embedding
      retrieval/          # Search, query rewriting, re-ranking
      grounding/          # Citation mapping and confidence evaluation
      providers/          # Groq, OpenAI Responses, Gemini Generate Content
      history/            # SQLite persistence
data/
  documents/              # Original local source files
  chroma/                 # Persistent vector index
  heritage.db             # SQLite database
mds/                      # Product and engineering documentation
```

Runtime data and `.env` files must be gitignored.

## 4. Component Responsibilities

### 4.1 Web client

- Own presentation and interaction state, not secrets or trust decisions.
- Send `message`, `chat_id`, `model`, and `retrieval_mode`.
- Render streaming text separately from final citations/confidence.
- Render inline citation markers and an **Answered from** footer.
- Open an accessible in-app source drawer at the cited page where the source
  format permits, with previous/next page controls and an original-file link.
- Provide equivalent hover, keyboard-focus, and tap access to the confidence legend.
- Rehydrate a historical message from stored source and confidence snapshots.
- Persist a device-local light/dark theme preference without sending it to the API.
- Abort an active answer stream on user request, preserve partial text as
  **Stopped**, and omit completed confidence/source metadata.

### 4.2 API and chat orchestrator

- Validate model and retrieval mode against server-side allowlists.
- Load conversation context without allowing prior messages to override grounding rules.
- Run retrieval, optional query decomposition, and re-ranking.
- Ask a provider adapter for a structured grounded response.
- Verify that every emitted citation maps to a retrieved chunk.
- Calculate confidence from evidence signals and stream the final metadata.
- Persist the completed turn atomically.

### 4.3 Ingestion service

- Accept PDF, DOCX, TXT, and MD in v1; CSV is optional.
- Detect duplicate content by checksum and make re-indexing idempotent.
- Extract text while retaining the reader-facing page number whenever reliable.
- For formats without stable pages, retain section, heading, paragraph, or line locators and set the page to `null`. Never manufacture a page number.
- Chunk at roughly 500–800 tokens with overlap without crossing page boundaries unnecessarily.
- Embed and upsert chunks; retain the original file for source preview.

### 4.4 Retrieval service

| Mode | Initial top-k | Re-ranking | Query rewriting |
|---|---:|---|---|
| Quick | 3 | Vector rank | No |
| Medium | 6–8 | Vector + lexical | No |
| Deep | 12 | Vector + BM25 + reciprocal-rank fusion | LLM expansion, then merge |

Retrieval returns normalized relevance, rank, and provenance. Parameters live in server configuration so they can be calibrated without changing the API.

### 4.5 Provider adapters

All providers implement the same interface: stream a response, generate a chat
title, expand a Deep retrieval query, and report key/model availability. Groq
uses Chat Completions, OpenAI uses the Responses API, and Gemini uses Generate
Content streaming. Provider output is converted to the same internal answer
schema. The confidence level is calculated by Heritage, not accepted from a
provider's self-assessment.

### 4.6 Citation and confidence service

The citation service accepts only retrieved chunk IDs. It rejects or removes a citation that cannot be resolved to stored provenance. Adjacent sources from the same document/page range may be deduplicated for display without losing chunk-level traceability.

The confidence evaluator produces:

- `score`: integer from 0 to 100
- `level`: `very_high`, `high`, `medium`, `low`, or `very_low`
- `rationale`: short user-facing explanation
- `factors`: diagnostic evidence signals for development and testing

Initial score inputs are citation coverage, retrieval/re-ranker strength, agreement between sources, directness of support, and source-location quality. Contradictions, unsupported claims, missing locators, and an explicit no-answer result apply penalties. Hard rules override the numeric result: no supporting source is Very low; partially supported answers cannot exceed Medium.

Phase 6 adds explicit completeness and contradiction factors. Partial support is
capped at 74/Medium, conflicting evidence at 54/Low, and absent or uncited
evidence remains Very low. The generated answer must acknowledge the gap or
conflict for automatic inference; deterministic evaluation can supply the
labeled evidence state directly.

## 5. Core Data Contracts

### 5.1 Chunk metadata

```json
{
  "chunk_id": "chk_...",
  "document_id": "doc_...",
  "file_name": "handbook.pdf",
  "title": "Employee Handbook",
  "page_start": 12,
  "page_end": 13,
  "section": "Leave Policy",
  "text": "...",
  "content_hash": "sha256:..."
}
```

`page_start` and `page_end` are nullable. Null is displayed as **Page unavailable**, accompanied by the best available text locator.

### 5.2 Final answer payload

```json
{
  "message_id": "msg_...",
  "answer": "Employees receive ... [1]",
  "answered_from": [
    {"document": "Employee Handbook", "pages": "12–13"}
  ],
  "citations": [
    {
      "id": 1,
      "chunk_id": "chk_...",
      "document_id": "doc_...",
      "document": "Employee Handbook",
      "file_name": "handbook.pdf",
      "page_start": 12,
      "page_end": 13,
      "section": "Leave Policy",
      "snippet": "..."
    }
  ],
  "confidence": {
    "score": 92,
    "level": "very_high",
    "rationale": "The answer is directly supported by a clearly located passage.",
    "factors": {
      "citation_coverage": 1.0,
      "retrieval_strength": 0.94,
      "source_agreement": 1.0,
      "location_quality": 1.0
    }
  },
  "model": "openai/gpt-oss-120b",
  "retrieval_mode": "medium"
}
```

### 5.3 Streaming events

Use Server-Sent Events or a streaming fetch response with typed events:

1. `chat.created` for a first message, including the API-generated title
2. `message.started`
3. `retrieval.completed` (optional user-safe progress only)
4. `answer.delta` repeated for text
5. `answer.completed` with the authoritative citations, **Answered from** summary, and confidence object
6. `error`

The UI must not treat a partial stream as a fully cited answer. A stopped or failed stream is labeled incomplete and is not assigned a high confidence state.

## 6. API Surface

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/auth/login` | Verify the shared password and issue the application session |
| `GET` | `/api/auth/session` | Restore or reject the current application session |
| `POST` | `/api/auth/logout` | Clear the application session |
| `POST` | `/api/chat/stream` | Ask a question and stream the grounded answer |
| `GET` | `/api/chats` | List chat history |
| `GET` | `/api/chats/{id}` | Load messages and source/confidence snapshots |
| `PATCH` | `/api/chats/{id}` | Rename or pin/unpin a chat |
| `DELETE` | `/api/chats/{id}` | Delete a chat after confirmation |
| `POST` | `/api/uploads/unlock` | Verify upload password and issue a short-lived local session |
| `GET` | `/api/uploads/session` | Check whether the short-lived upload session is active |
| `POST` | `/api/documents/upload` | Validate, store, and immediately index uploaded documents |
| `GET` | `/api/ingestion-jobs/{id}` | Read indexing status |
| `POST` | `/api/documents/reindex` | Manually scan the configured documents directory |
| `GET` | `/api/documents/{id}/content` | Serve a local source for authorized preview |
| `GET` | `/api/health` | Local health check |

## 7. Persistence

SQLite stores `chats`, `messages`, `documents`, and `ingestion_jobs`. Chat records
also persist their editable title and pinned state. An assistant message stores
its final rendered text, model, retrieval mode, citations JSON, confidence JSON,
timestamps, and status. Document records store identity, checksum, media type,
original path, ingestion state, and timestamps.

The SQLite history is installation-wide, not browser-local: all browsers
connected to the same backend list and modify the same chats. v1 has no user
identity or private history boundary.

Chroma stores embeddings and the chunk metadata needed to resolve a result. SQLite is the record of lifecycle state; Chroma is the retrieval index. Deleting or replacing a document must update both stores in one coordinated operation and report partial failures.

A new chat is created by `POST /api/chat/stream` when `chat_id` is omitted. The
backend calls Groq once to generate a concise title from the first user query,
persists that title with the chat, and returns it in `chat.created`. Later turns
send the existing `chat_id`; title generation is not repeated.

## 8. Security and Privacy

- Bind services to loopback by default.
- Keep API keys and the shared application password hash server-side.
- Require a valid 12-hour HTTP-only session for every non-authentication API
  route. Permit unauthenticated CORS preflight requests.
- Use a password hashing algorithm intended for passwords, such as Argon2id or bcrypt.
- Return a short-lived, HTTP-only upload-unlock cookie or token after password verification; rate-limit attempts.
- The local default password is `Password`, represented only by a configurable
  bcrypt hash. The application session expires after 12 hours and also
  authorizes uploads; the legacy upload-only session expires after 10 minutes.
- Validate file type by content and extension, sanitize file names, set file-size limits, and prevent path traversal.
- Treat document text as untrusted input. Serialize it as JSON, escape delimiter
  characters, keep it separate from the user question, and tell every provider
  not to follow instructions embedded in a source.
- Avoid logging document contents, prompts, provider keys, passwords, or full streamed answers by default.
- Make external provider use explicit because retrieved text leaves the machine when a cloud model or embedding provider is selected.

## 9. Reliability and Observability

- Ingestion is resumable and records per-file success/failure.
- A failed upload never makes a partially indexed document appear ready.
- Chat requests have timeouts and cancellation; provider errors use a common UI-safe error shape.
- Structured local logs include request ID, chat ID, provider, retrieval mode, latency, chunk IDs, and confidence factors, but not sensitive content.
- JSON Lines logs rotate locally at 5 MB with three archives. Field- and
  value-level redaction removes keys, authorization values, cookies, upload
  passwords, tokens, prompts/questions, answers, and document content.
- Health checks cover SQLite and Chroma availability; provider availability is reported separately.
- Provider health checks verify both key authentication and whether each
  configured model appears in that key's model catalog. Unavailable models are
  visible but disabled in the client.

## 10. Evaluation, Performance, and Recovery

- `evals/questions.json` scores expected document/page retrieval for the real
  corpus in Quick, Medium, and Deep modes.
- `evals/answer_cases.json` deterministically scores citation precision,
  groundedness, confidence labels, and no-answer behavior across direct,
  partial, conflicting, absent, and adversarial evidence.
- The synthetic benchmark creates an isolated temporary Chroma collection with
  300 documents and measures local embedding/indexing plus p50/p95 retrieval.
  It never modifies the production collection.
- Backups are versioned ZIP archives containing `DOCS/`, a consistent SQLite
  snapshot, Chroma files, a manifest, and per-file SHA-256 checksums. Secrets
  and logs are excluded.
- Restore validates version, paths, presence, and checksums before changing a
  target and refuses non-empty targets without explicit replacement.

## 11. Architecture Decisions and Defaults

- Next.js + Tailwind CSS for the web UI.
- FastAPI for the backend.
- Chroma for the local vector store and SQLite for relational persistence.
- Chroma's local ONNX `all-MiniLM-L6-v2` embedding function for Phase 1; no embedding API or hosted vector database.
- Server-Sent Events or streaming fetch for one-way answer streaming; WebSockets are unnecessary for v1.
- Manual folder re-index by default; auto-watch remains an open decision.
- Groq, OpenAI, and Gemini are implemented provider families. Anthropic and
  Ollama remain optional later adapters.
- Confidence is an application-owned evidence metric, never an LLM claim of truth.
