# Heritage RAG — Local Operations Guide

**Status:** Phase 6 release-hardening guide

**Last updated:** 2026-07-30

## 1. Fresh Installation

Prerequisites:

- macOS, Linux, or Windows with a Unix-compatible shell.
- Node.js 20.9 or newer.
- Python 3.11.
- `uv`.
- At least 2 GB of free memory and space for the document corpus, local index,
  backups, and the approximately 80 MB local embedding model download.

From the repository root:

```bash
cp .env.example .env
npm install
uv sync --project apps/api
npm run index
npm run dev
```

Set `GROQ_API_KEY` in `.env` before asking model-generated questions. OpenAI and
Gemini keys are optional; their model choices remain visible but unavailable
until the key authenticates and grants access to the configured model.

Open `http://127.0.0.1:3000`. The API uses `http://127.0.0.1:8000`. Both bind to
loopback by default. Enter the shared application password `Password` to open
the workspace. The server issues a 12-hour HTTP-only session by default; change
`APP_SESSION_TTL_SECONDS` in `.env` if a different duration is required.

## 2. Release Verification

Run:

```bash
npm run test:api
npm run test:web
npm run build
npm run eval -- --mode quick
npm run eval -- --mode medium
npm run eval -- --mode deep
npm run eval:answers
npm run benchmark -- --documents 300 --queries 24
```

The deterministic checks do not require a valid cloud-provider key. Live
provider authentication and wording checks do.

Current release targets:

| Measure | Target |
|---|---:|
| Quick expected document/page hit rate | At least 80% |
| Medium expected document/page hit rate | At least 95% |
| Deep expected document/page hit rate | At least 95% |
| Labeled citation precision | 100% |
| Labeled no-answer accuracy | 100% |
| 300-document local retrieval p95 | Under 2 seconds |
| 300-document synthetic indexing | Under 120 seconds |

Recorded results live in `evals/results/`.

## 3. Back Up

Backups include the original `DOCS/` files, the Chroma index, and the SQLite
database. They deliberately exclude `.env`, API keys, upload-password hashes,
logs, dependencies, and build output.

Create a timestamped backup:

```bash
npm run backup
```

Or choose a path:

```bash
npm run backup -- --output /safe/location/heritage.zip
```

Validate checksums and inspect the manifest:

```bash
npm run backup:inspect -- --archive /safe/location/heritage.zip
```

Treat backups as sensitive: they contain the original documents and complete
chat history.

## 4. Restore

1. Stop `npm run dev`.
2. Make a current backup before replacing anything.
3. Inspect the archive.
4. Restore with explicit replacement:

```bash
npm run backup:inspect -- --archive /safe/location/heritage.zip
npm run restore -- --archive /safe/location/heritage.zip --replace
```

Without `--replace`, restore refuses to overwrite non-empty targets. The
archive is checked for path traversal, missing files, unsupported versions, and
checksum failures before any target is changed.

Start the application and run `npm run eval -- --mode medium` after restoration.

## 5. Structured Logs

The API writes JSON Lines to `data/logs/heritage.jsonl` and mirrors them to the
terminal. Rotation keeps three 5 MB archives.

Logs include request ID, route, status, latency, chat/message IDs, provider,
model, retrieval mode, retrieved chunk IDs, and confidence factors. They redact
passwords, cookies, authorization values, API keys, tokens, prompts, questions,
answers, and document content.

Change verbosity with `LOG_LEVEL` in `.env`. Do not attach logs publicly without
reviewing them; metadata such as file-derived chunk IDs and chat IDs can still
be sensitive.

## 6. Troubleshooting

| Symptom | Check |
|---|---|
| The login screen returns | The shared session expired or the API restarted; enter `Password` again. In-memory sessions intentionally do not survive backend restarts. |
| Model is disabled | Refresh provider health; confirm the key is valid and the configured model is allowed for that key. |
| API offline | Confirm port 8000 is free and `uv sync --project apps/api` completed. |
| Documents show zero chunks | Run `npm run index`; inspect parsing failures in the command output and structured log. |
| An uploaded file is rejected | Confirm PDF/DOCX/TXT/MD, valid file content, and size under 25 MB. |
| The shared password stops working | Wait for the rate-limit window after repeated failures; the default is `Password` unless `UPLOAD_PASSWORD_HASH` was changed. |
| Citation opens the wrong place | Re-index the source and confirm the PDF reader-facing page matches extracted page order. |
| A non-PDF has no page | This is expected when native pagination is unavailable; use the structural locator. |
| An answer has Very low confidence | The final answer had no valid supporting citation; refine the question or add the missing document. |
| Chroma model downloads on first run | Allow the one-time local ONNX embedding download; no hosted vector database is required. |
| Restore refuses to run | Stop the app, inspect the archive, then use `--replace` only after making a current backup. |

## 7. Routine Care

- Back up before replacing documents, upgrading Chroma, or changing persistence.
- Re-run evaluation after adding a materially different document collection.
- Expand labeled direct, partial, conflicting, and absent cases when new failure
  patterns appear.
- Rotate cloud-provider keys outside the repository and never commit `.env`.
- Upgrade dependencies only with the complete release verification sequence.
