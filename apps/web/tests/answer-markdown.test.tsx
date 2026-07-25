import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import {
  AnswerMarkdown,
  LoginScreen,
  groupChatsByDate,
  type ChatSummary,
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
  const page = readFileSync(
    new URL("../app/page.tsx", import.meta.url),
    "utf8",
  );
  const css = readFileSync(
    new URL("../app/globals.css", import.meta.url),
    "utf8",
  );

  assert.match(page, /12 chunks · query expansion \+ full re-rank/);
  assert.doesNotMatch(page, /15 chunks · query expansion \+ full re-rank/);
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

test("chat history is grouped by pinned and calendar date", () => {
  const now = new Date(2026, 6, 30, 12);
  const daysAgo = (days: number) => {
    const value = new Date(now);
    value.setDate(value.getDate() - days);
    return value.toISOString();
  };
  const chat = (
    id: string,
    updatedAt: string,
    pinned = false,
  ): ChatSummary => ({
    id,
    title: `Chat ${id}`,
    pinned,
    created_at: updatedAt,
    updated_at: updatedAt,
    message_count: 2,
  });
  const chats = [
    chat("previous-month", daysAgo(45)),
    chat("previous-30", daysAgo(12)),
    chat("pinned", daysAgo(1), true),
    chat("today", daysAgo(0)),
    chat("previous-7", daysAgo(3)),
    chat("yesterday", daysAgo(1)),
  ];

  const groups = groupChatsByDate(chats, now);

  assert.deepEqual(
    groups.map((group) => group.label),
    [
      "Pinned",
      "Today",
      "Yesterday",
      "Previous 7 days",
      "Previous 30 days",
      "June 2026",
    ],
  );
  assert.deepEqual(
    groups.map((group) => group.chats.map((item) => item.id)),
    [
      ["pinned"],
      ["today"],
      ["yesterday"],
      ["previous-7"],
      ["previous-30"],
      ["previous-month"],
    ],
  );
});

test("chat history fills the available sidebar height", () => {
  const css = readFileSync(
    new URL("../app/globals.css", import.meta.url),
    "utf8",
  );
  const historyList = css.match(
    /\.history-list\s*\{([\s\S]*?)\n\}/,
  )?.[1];

  assert.ok(historyList);
  assert.match(historyList, /min-height:\s*0/);
  assert.match(historyList, /flex:\s*1/);
  assert.match(historyList, /max-height:\s*none/);
  assert.doesNotMatch(historyList, /42vh|360px|padding:[^;]*110px/);
});

test("the complete app is gated by the shared password session", () => {
  const html = renderToStaticMarkup(
    <LoginScreen
      checking={false}
      theme="light"
      onToggleTheme={() => undefined}
      onAuthenticated={async () => undefined}
    />,
  );
  const page = readFileSync(
    new URL("../app/page.tsx", import.meta.url),
    "utf8",
  );
  const css = readFileSync(
    new URL("../app/globals.css", import.meta.url),
    "utf8",
  );

  assert.match(html, /Heritage — Staff Access/);
  assert.match(
    html,
    /This portal is restricted to authorized staff\. Enter the access password to continue\./,
  );
  assert.match(html, /type="password"/);
  assert.match(html, /autoComplete="current-password"/);
  assert.match(html, />Continue</);
  assert.match(page, /api\/auth\/session/);
  assert.match(page, /credentials: "include"/);
  assert.match(page, /authStatus !== "authenticated"/);
  assert.match(
    page,
    /async function completeAuthentication\(\)[\s\S]*?startNewChat\(\);[\s\S]*?loadChats\(\)/,
  );
  assert.doesNotMatch(page, /loadChats\(true\)/);
  assert.ok(css.includes(".login-card"));
  assert.ok(css.includes(".login-password-field"));
});

test("document uploads expose real per-file progress, indexing, and retry states", () => {
  const page = readFileSync(
    new URL("../app/page.tsx", import.meta.url),
    "utf8",
  );
  const css = readFileSync(
    new URL("../app/globals.css", import.meta.url),
    "utf8",
  );

  assert.match(page, /new XMLHttpRequest\(\)/);
  assert.match(page, /request\.upload\.addEventListener\("progress"/);
  assert.match(page, /status: "indexing"/);
  assert.match(page, /Processing & indexing/);
  assert.match(page, /Already indexed/);
  assert.match(page, /uploadDocuments\(\[item]\)/);
  assert.ok(css.includes(".file-progress"));
  assert.ok(css.includes(".file-retry"));
  assert.ok(css.includes(".file-error"));
});

test("citations can open the in-app source preview", () => {
  const html = renderToStaticMarkup(
    <AnswerMarkdown
      content="Supported answer [1]."
      sources={[source]}
      onSourceSelect={() => undefined}
    />,
  );

  assert.match(html, /<button class="citation"/);
  assert.match(html, /aria-label="Source 1: Formatting Guide, Page 3"/);
});

test("Phase 5 theme, stop, confidence, and source interactions are wired", () => {
  const page = readFileSync(
    new URL("../app/page.tsx", import.meta.url),
    "utf8",
  );
  const layout = readFileSync(
    new URL("../app/layout.tsx", import.meta.url),
    "utf8",
  );

  assert.match(layout, /heritage-theme/);
  assert.match(layout, /prefers-color-scheme: dark/);
  assert.match(page, /className="theme-toggle"/);
  assert.match(page, /answerAbortRef\.current\?\.abort\(\)/);
  assert.match(page, /Stopped — partial answer retained/);
  assert.match(page, /className="source-drawer glass-strong"/);
  assert.match(page, /aria-label="Source page navigation"/);
  assert.match(page, /aria-expanded=\{open\}/);
  assert.match(page, /handleOutsidePointer/);
  assert.match(page, /containModalFocus/);
  assert.match(page, /returnFocus\?\.focus\(\)/);
});

test("empty state offers three questions grounded in the indexed corpus", () => {
  const page = readFileSync(
    new URL("../app/page.tsx", import.meta.url),
    "utf8",
  );

  assert.match(
    page,
    /What are the four components of experiential learning\?/,
  );
  assert.match(
    page,
    /Compare Heritage's CBSE offering with a typical CBSE school in a table\./,
  );
  assert.match(
    page,
    /In one concise paragraph, explain why hands-on learning is not always the same as experiential learning\./,
  );
  assert.match(page, /starterPrompts\.map/);
  assert.match(page, /sendMessage\(undefined, prompt\.question\)/);
});

test("queries and responses expose familiar edit, copy, and retry actions", () => {
  const page = readFileSync(
    new URL("../app/page.tsx", import.meta.url),
    "utf8",
  );
  const css = readFileSync(
    new URL("../app/globals.css", import.meta.url),
    "utf8",
  );

  assert.match(
    page,
    /aria-label=\{copied \? "Query copied" : "Copy query"\}/,
  );
  assert.match(page, /aria-label="Edit and resend query"/);
  assert.match(
    page,
    /aria-label=\{copied \? "Response copied" : "Copy response"\}/,
  );
  assert.match(page, /aria-label="Retry response"/);
  assert.match(page, /function copyToClipboard/);
  assert.match(page, /function editQuery/);
  assert.match(page, /function retryResponse/);
  assert.ok(css.includes(".message-actions"));
  assert.ok(css.includes(".edit-context"));
});

test("Phase 5 stylesheet includes dark, responsive, and reduced-effect modes", () => {
  const css = readFileSync(
    new URL("../app/globals.css", import.meta.url),
    "utf8",
  );

  assert.match(css, /html\[data-theme="dark"]\s*\{/);
  assert.match(css, /@media \(min-width: 761px\) and \(max-width: 1100px\)/);
  assert.match(css, /@media \(max-width: 760px\)/);
  assert.match(css, /@media \(max-width: 480px\)/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
  assert.match(css, /@media \(prefers-reduced-transparency: reduce\)/);
  assert.ok(css.includes(".source-drawer"));
  assert.ok(css.includes(".confidence-wrap.is-open .confidence-popover"));
});

test("confidence colors meet AA contrast in both themes", () => {
  const css = readFileSync(
    new URL("../app/globals.css", import.meta.url),
    "utf8",
  );
  const lightBlock = css.match(/:root\s*\{([\s\S]*?)\n\}/)?.[1] ?? "";
  const darkBlock =
    css.match(/html\[data-theme="dark"]\s*\{([\s\S]*?)\n\}/)?.[1] ?? "";
  const tokens = ["very-high", "high", "medium", "low", "very-low"];

  function token(block: string, name: string) {
    const value = block.match(
      new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`),
    )?.[1];
    assert.ok(value, `Missing confidence token: ${name}`);
    return value;
  }

  function luminance(hex: string) {
    const channels = hex
      .match(/[0-9a-fA-F]{2}/g)!
      .map((value) => Number.parseInt(value, 16) / 255)
      .map((value) =>
        value <= 0.03928
          ? value / 12.92
          : ((value + 0.055) / 1.055) ** 2.4,
      );
    return (
      0.2126 * channels[0] +
      0.7152 * channels[1] +
      0.0722 * channels[2]
    );
  }

  function contrast(foreground: string, background: string) {
    const foregroundLuminance = luminance(foreground);
    const backgroundLuminance = luminance(background);
    return (
      (Math.max(foregroundLuminance, backgroundLuminance) + 0.05) /
      (Math.min(foregroundLuminance, backgroundLuminance) + 0.05)
    );
  }

  for (const name of tokens) {
    assert.ok(
      contrast(token(lightBlock, name), "#ffffff") >= 4.5,
      `${name} fails light-theme AA contrast`,
    );
    assert.ok(
      contrast(token(darkBlock, name), "#1b1f2d") >= 4.5,
      `${name} fails dark-theme AA contrast`,
    );
    assert.ok(
      contrast("#172034", token(darkBlock, name)) >= 4.5,
      `${name} score fails dark-theme AA contrast`,
    );
  }
});
