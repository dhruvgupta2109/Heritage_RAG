# Heritage RAG — Known Limitations

**Status:** Local v1 release candidate

**Last updated:** 2026-07-30

- OCR is not implemented. Image-only or scanned PDFs may yield no searchable
  text.
- PDF page locations use extracted reader order. Printed page labels can differ
  when a document has covers, Roman-numbered front matter, or unusual metadata.
- DOCX, TXT, and Markdown do not have stable native pages; Heritage shows
  **Page unavailable** with a structural locator.
- Confidence estimates document support, not real-world truth. Current
  calibration is deterministic on the labeled local suite and must be expanded
  when the corpus or answer styles change.
- Conflict and partial-support penalties depend on the generated answer
  explicitly acknowledging missing or inconsistent evidence. Provider behavior
  remains probabilistic.
- Prompt-injection defenses and citation allowlisting reduce but cannot
  eliminate model-level attacks. Verify sensitive answers on the cited page.
- Cloud LLM providers receive the current question and retrieved passages.
- OpenAI and Gemini adapters are implemented, but live access remains dependent
  on a valid key and permission for the configured model IDs.
- The shared upload password is only an upload gate. There is no authentication,
  authorization, or per-user/private history.
- All browsers connected to the same backend share the same chat history and
  knowledge base.
- Manual folder re-indexing is supported; automatic filesystem watching is not.
- The 300-document benchmark measures synthetic local embedding/index/retrieval,
  not PDF parsing or cloud generation latency. Results vary by hardware.
- Synthetic benchmark hit rate is not a quality metric; the corpus-specific
  labeled evaluation measures expected document/page retrieval.
- Backups are local ZIP archives and are not encrypted. Store them securely.
- Restore must be run while the application is stopped and requires explicit
  replacement when targets are non-empty.
- The current Next.js dependency line includes a transitive PostCSS advisory.
  The app binds to localhost and does not process user-supplied CSS; upgrade when
  a compatible patched stable release is available.
