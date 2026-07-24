# Heritage Evaluation Set

**Status:** Phase 6 retrieval, answer, confidence, adversarial, and performance baselines recorded

**Last updated:** 2026-07-30

`questions.json` contains 25 questions derived from the current `DOCS/`
corpus:

- 21 answerable questions with expected document and PDF page.
- 4 intentionally unsupported questions for refusal and Very low confidence checks.
- Direct, comparison, multi-step, calendar/date-list, and table lookups.

`answer_cases.json` adds deterministic final-answer cases for:

- Direct and multi-source support.
- Partial support.
- Conflicting sources.
- Absent evidence and the exact no-support contract.
- A malicious document containing instruction-override and secret-exfiltration
  text.

Run retrieval evaluation with:

```bash
npm run eval -- --mode quick
npm run eval -- --mode medium
npm run eval -- --mode deep
npm run eval:answers
```

Current baseline:

| Mode | Expected document/page hits |
|---|---:|
| Quick | 18/21 (85.7%) |
| Medium | 21/21 (100%) |
| Deep, without provider expansion | 21/21 (100%) |

Deep mode in the running chat adds up to three LLM-generated query variants
before vector/BM25/reciprocal-rank fusion. The CLI baseline intentionally runs
without provider calls so retrieval regression tests remain free and
deterministic.

No-answer cases are not scored as retrieval misses because retrieving a related
passage does not mean the requested fact is present. They must pass the final
generation contract: no invented citation, no fabricated page, the explicit
no-support sentence, and Very low confidence. The live Groq check for the
unsupported Grade 8 tuition-fee question passed that contract.

Current deterministic answer baseline:

| Measure | Result |
|---|---:|
| Citation precision | 100% |
| Answer groundedness | 100% |
| Confidence classification | 100% |
| No-answer behavior | 100% |

Run the isolated performance measurement with:

```bash
npm run benchmark -- --documents 300 --queries 24
```

The recorded local run indexed 300 synthetic documents in 3.142 seconds.
Retrieval p95 was 68.56 ms Quick, 68.89 ms Medium, and 68.77 ms Deep. This
measures local embedding/Chroma retrieval rather than provider generation or
real PDF parsing. Machine-readable reports are in `evals/results/`.
