# Heritage Evaluation Set

**Status:** Pre-Phase-5 retrieval baseline complete

**Last updated:** 2026-07-30

`questions.json` contains 25 questions derived from the current `DOCS/`
corpus:

- 21 answerable questions with expected document and PDF page.
- 4 intentionally unsupported questions for refusal and Very low confidence checks.
- Direct, comparison, multi-step, calendar/date-list, and table lookups.

Run retrieval evaluation with:

```bash
npm run eval -- --mode quick
npm run eval -- --mode medium
npm run eval -- --mode deep
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
