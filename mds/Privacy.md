# Heritage RAG — Privacy and Provider Disclosure

**Status:** Current for local v1

**Last updated:** 2026-07-30

## What Stays Local

- Original files in `DOCS/`.
- Chroma vectors and chunk provenance in `data/chroma/`.
- Chats, messages, citations, confidence snapshots, and document lifecycle
  records in `data/heritage.db`.
- Embedding generation through Chroma's local ONNX
  `all-MiniLM-L6-v2` model.
- Structured redacted logs in `data/logs/`.
- The shared application password hash and provider keys in the ignored local
  `.env`.

No hosted vector database or embedding API is used.

## What Cloud LLM Providers Receive

When a Groq, OpenAI, or Gemini model is selected, that provider receives:

- The current user question.
- Retrieved source passages needed to answer it.
- Document titles and source-location labels included with those passages.
- A system instruction that enforces grounding, formatting, citations, and
  malicious-document handling.

The selected provider may also receive the first query for title generation and
Deep-mode query rewriting. Heritage does not send the Chroma database, entire
document folder, upload password, local logs, or other provider keys.

Provider retention and training policies are controlled by the provider and
account plan, not by Heritage. Do not use a cloud model for material that the
provider is not permitted to receive.

## Local Sharing Boundary

The application has one installation-wide history. Any browser that can reach
the same local backend can view, rename, pin, delete, and continue all chats.
There are no user accounts or private per-browser conversations in v1.

The shared password protects the complete app and API through a 12-hour
HTTP-only session. It still does not establish identity: everyone who knows the
password sees the same chats, documents, and source previews.

## Logs and Backups

Default logs omit or redact document bodies, prompts, answers, passwords,
cookies, bearer values, API keys, and tokens. Metadata such as chat IDs,
provider/model choices, chunk IDs, latency, and confidence factors remains.

Backups contain original documents and chat history and must be protected like
the source corpus. Backups exclude `.env` and logs by design.

## Untrusted Documents

Document text is treated as untrusted data. It is JSON-encoded into a distinct
evidence section, delimiter characters are escaped, and provider system
instructions explicitly reject commands or role changes found inside sources.
Automated adversarial fixtures cover attempts to close the evidence delimiter,
override instructions, and request an API key.

Prompt-injection defenses reduce risk but cannot guarantee perfect behavior from
an external model. Citations, the Answered from footer, and confidence should
still be checked for important decisions.

## Deleting Data

- Delete chats in the sidebar to remove them from SQLite.
- Remove a source file and re-index to update the active corpus.
- Historical answers retain their saved citation/confidence snapshot.
- Delete `data/` only when intentionally resetting all local history and index;
  make a backup first.
- Provider-side deletion follows the chosen provider's own controls and policy.
