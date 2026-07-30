import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import {
  AnswerMarkdown,
  type Source,
} from "../app/page";

const source: Source = {
  id: 1,
  chunk_id: "chunk-1",
  document_id: "document-1",
  document: "Formatting Guide",
  file_name: "formatting-guide.pdf",
  page_start: 3,
  page_end: 3,
  section: null,
  snippet: "Formatting evidence.",
  relevance: 0.95,
};

const allFormats = `## Clear heading

A paragraph with **bold text**, *emphasis*, ~~removed text~~, \`inline code\`, an [external link](https://example.com), and evidence [1].

### Supporting heading

Line one with a hard break.  
Line two [1].

- First bullet [1].
  - Nested bullet [1].
- Second bullet [1].
- [x] Completed task [1].

1. First step [1].
2. Second step [1].

| Aspect | Option A | Option B |
|---|---|---|
| Method | Experiential [1] | Lecture-led [1] |
| Outcome | Understanding [1] | Recall [1] |

> A supported quotation-style callout [1].

---

\`\`\`text
multi-line
code block
\`\`\`

![Example image](https://example.com/example.png)
`;

test("every supported answer format renders as semantic HTML", () => {
  const html = renderToStaticMarkup(
    <AnswerMarkdown content={allFormats} sources={[source]} />,
  );

  assert.match(html, /<h2>Clear heading<\/h2>/);
  assert.match(html, /<h3>Supporting heading<\/h3>/);
  assert.match(html, /<p>A paragraph/);
  assert.match(html, /<br\/>/);
  assert.match(html, /<strong>bold text<\/strong>/);
  assert.match(html, /<em>emphasis<\/em>/);
  assert.match(html, /<del>removed text<\/del>/);
  assert.match(html, /<code>inline code<\/code>/);
  assert.match(html, /class="answer-link"/);
  assert.match(html, /<ul>/);
  assert.match(html, /<ol>/);
  assert.match(html, /type="checkbox" disabled="" checked=""/);
  assert.match(html, /<blockquote>/);
  assert.match(html, /<hr\/>/);
  assert.match(html, /<pre><code class="language-text">/);
  assert.match(html, /class="answer-table-wrap"/);
  assert.match(html, /aria-label="Answer table"/);
  assert.match(html, /<table>/);
  assert.match(html, /<thead>/);
  assert.match(html, /<tbody>/);
  assert.match(html, /<img src="https:\/\/example.com\/example.png"/);
  assert.match(html, /class="citation"/);
  assert.match(html, /document-1\/content#page=3/);
});

test("answer stylesheet covers spacing and every rendered format", () => {
  const css = readFileSync(
    new URL("../app/globals.css", import.meta.url),
    "utf8",
  );
  const requiredSelectors = [
    ".answer-copy p",
    ".answer-copy h1",
    ".answer-copy h5",
    ".answer-copy ol",
    ".answer-copy ul",
    ".answer-copy li",
    ".answer-copy blockquote",
    ".answer-copy hr",
    ".answer-copy code",
    ".answer-copy pre",
    ".answer-copy img",
    ".answer-copy .contains-task-list",
    ".answer-table-wrap",
    ".answer-table-wrap th",
    ".answer-table-wrap td",
    ".answer-link",
    ".citation",
  ];

  for (const selector of requiredSelectors) {
    assert.ok(css.includes(selector), `Missing answer style: ${selector}`);
  }
});

test("historical citation spacing is repaired while rendering", () => {
  const html = renderToStaticMarkup(
    <AnswerMarkdown
      content="Legacy answer with a citation [1] ."
      sources={[source]}
    />,
  );

  assert.match(html, />1<\/a>\.<\/p>/);
  assert.doesNotMatch(html, /<\/a> \.<\/p>/);
});

test("model and retrieval selector menus use an opaque surface", () => {
  const css = readFileSync(
    new URL("../app/globals.css", import.meta.url),
    "utf8",
  );

  assert.match(
    css,
    /\.selector-menu\s*\{[^}]*background:\s*#fbfbff;[^}]*backdrop-filter:\s*none;/s,
  );
});

test("all dropdown families share outside-click and Escape closing", () => {
  const page = readFileSync(
    new URL("../app/page.tsx", import.meta.url),
    "utf8",
  );

  assert.match(
    page,
    /\.tool-selector\[open], \.history-actions\[open]/,
  );
  assert.match(page, /addEventListener\("pointerdown", handleOutsidePointer\)/);
  assert.match(page, /if \(!menu\.contains\(target\)\) menu\.open = false/);
  assert.match(page, /addEventListener\("keydown", handleMenuEscape\)/);
});
