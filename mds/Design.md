# Heritage RAG — Product Design System

**Status:** Proposed

**Applies to:** Web UI v1

**Last updated:** 2026-07-29

## 1. Design Direction

Heritage should feel calm, precise, and trustworthy: a focused document workspace rather than a decorative AI demo. Glass surfaces provide depth, while citations and confidence remain more prominent than visual effects.

Principles:

- **Evidence first:** make document and page provenance easy to scan and verify.
- **Quiet hierarchy:** one primary action per area, generous space, restrained color.
- **Honest uncertainty:** weak or missing evidence is visible without opening a tooltip.
- **Consistent glass:** blur, tint, border, and shadow come from shared tokens.
- **Accessible by default:** all hover behavior also works by keyboard focus and tap.

## 2. Application Layout

### Desktop

- A collapsible 280 px history sidebar.
- A centered conversation column with a comfortable maximum width of 800–900 px.
- A sticky glass input composer at the bottom.
- Source previews open in a right-side drawer where space permits.

### Small screens

- The history sidebar becomes an overlay drawer.
- The conversation uses the full width with 16 px outer padding.
- The source preview becomes a full-screen sheet.
- Model and speed controls may wrap, but the send control stays obvious.
- Model and retrieval dropdown panels use fully opaque surfaces so answer text
  and background gradients never show through their options.

## 3. Visual Tokens

Implement tokens as CSS custom properties and map them into Tailwind. Exact values can be tuned once screens are rendered.

```css
:root {
  --bg-start: #eef4ff;
  --bg-end: #f8f3ff;
  --text-primary: #152033;
  --text-muted: #5f6b7a;
  --glass-fill: rgba(255, 255, 255, 0.58);
  --glass-fill-strong: rgba(255, 255, 255, 0.78);
  --glass-border: rgba(255, 255, 255, 0.72);
  --glass-shadow: 0 16px 48px rgba(41, 55, 84, 0.12);
  --glass-blur: 18px;
  --focus-ring: #2563eb;
  --confidence-very-high: #047857;
  --confidence-high: #0f766e;
  --confidence-medium: #b45309;
  --confidence-low: #c2410c;
  --confidence-very-low: #be123c;
  --radius-panel: 20px;
  --radius-control: 14px;
}

[data-theme="dark"] {
  --bg-start: #0b1020;
  --bg-end: #171129;
  --text-primary: #f4f7fb;
  --text-muted: #abb6c8;
  --glass-fill: rgba(20, 27, 44, 0.60);
  --glass-fill-strong: rgba(20, 27, 44, 0.82);
  --glass-border: rgba(255, 255, 255, 0.12);
  --glass-shadow: 0 18px 56px rgba(0, 0, 0, 0.32);
  --confidence-very-high: #6ee7b7;
  --confidence-high: #5eead4;
  --confidence-medium: #fbbf24;
  --confidence-low: #fb923c;
  --confidence-very-low: #fda4af;
}
```

If `backdrop-filter` is unavailable or reduced transparency is enabled, use the strong opaque fill. Content readability must not depend on blur.

## 4. Core Components

### 4.1 History sidebar

- Product mark/name at the top, followed by **New chat**.
- Search/filter and chronological conversation groups.
- Rename, pin/unpin, and delete appear in an overflow menu; deletion requires confirmation.
- **Add documents** remains visually separate near the bottom and uses a lock/upload icon.
- Collapse state and selected conversation are visually clear.

### 4.2 Empty chat

- Short title and one sentence explaining that answers come from indexed documents.
- Two or three example prompts, never a crowded prompt gallery.
- Show indexing state if no documents are available.

### 4.3 Composer

- Rounded glass container with an auto-growing text area.
- Model and retrieval speed are labeled compact chips within the tools row.
- Default retrieval mode is Medium.
- Enter sends; Shift+Enter adds a line. The send button has an accessible name.
- While streaming, the send control becomes a stop control.

### 4.4 Messages and answers

User messages use a subtle tinted bubble. Assistant answers sit on a quiet glass surface or directly on the conversation canvas with enough separation to scan.

Every completed assistant answer follows this order:

1. Answer content with clickable citation markers such as `[1]`.
2. **Answered from:** compact document and page summary.
3. Confidence badge.
4. Expandable **Sources** list with document, page/range, section, and snippet.
5. Message actions such as copy or retry.

Within the answer content, use the structure that best matches the information:
short prose for a direct fact, bullets for an unordered set, numbered lists for
steps or sequences, and compact tables for comparisons, schedules, or repeated
attributes. Use descriptive headings only when the answer contains multiple
distinct sections. Avoid unnecessary headings, one-column tables, and decorative
formatting. Citations stay attached to the factual sentence, list item, or table
row they support.

Rendered Markdown uses consistent vertical rhythm for paragraphs, headings,
lists, nested lists, quotations, code, and separators. Tables use a bordered
header/row grid with comfortable cell padding and alternating row tint. A table
that exceeds the answer width scrolls horizontally inside its own
keyboard-focusable region instead of compressing or overlapping columns.

The **Answered from** row is always visible. If a reliable page does not exist, display **Page unavailable · Section name**; never infer a page for visual consistency. If no evidence exists, display **Answered from: No supporting document found** and omit citation markers.

### 4.5 Sources list and preview

- A source row reads like `Employee Handbook · pp. 12–13 · Leave Policy`.
- Use `p. 8` for one page and `pp. 8–10` for a range.
- Selecting a source opens the original document at that page when supported and highlights the matching snippet when practical.
- Snippets are short evidence previews, not entire document passages.
- Conflicting sources receive a neutral **Conflict noted** label and both remain visible.

## 5. Confidence Glass Component

### 5.1 Badge

The confidence badge is a compact glass pill beside answer metadata. It contains:

- A distinct icon or shape.
- The full state label, such as **High confidence**.
- Optional numeric score, such as `84`, in expanded layouts.
- A tinted dot/border/fill based on the current state.

The five visual states are:

| State | Token | Accent | Icon cue |
|---|---|---|---|
| Very high confidence | `--confidence-very-high` | Emerald `#047857` | Double check |
| High confidence | `--confidence-high` | Teal `#0F766E` | Check |
| Medium confidence | `--confidence-medium` | Amber `#B45309` | Minus |
| Low confidence | `--confidence-low` | Orange `#C2410C` | Alert triangle |
| Very low confidence | `--confidence-very-low` | Rose `#BE123C` | Alert circle |

Use lighter/darker companion fills per theme while maintaining WCAG AA text contrast. The label and icon are mandatory because color alone is insufficient.

### 5.2 Hover/focus/tap popover

Hovering or focusing the badge opens a frosted-glass popover. Tapping toggles it on touch devices. The popover contains:

- `Answer confidence: 84/100`
- A one-sentence rationale tied to evidence.
- All five states in descending order, each with its color, label, score range, and short meaning.
- A strong outline/check on the active state.
- A note: `Confidence reflects support in your indexed documents, not a guarantee of factual truth.`

The popover does not disappear while the pointer moves from badge to content. Escape closes it, focus returns to the badge, and outside click closes it.

### 5.3 Low-confidence treatment

For Low and Very low confidence, the rationale is also rendered inline below the badge. Use direct copy:

- Low: `The documents provide only partial or conflicting support. Check the cited pages.`
- Very low: `I couldn't find reliable support for this in the indexed documents.`

Do not hide these warnings behind hover and do not render a confident-looking answer when no evidence exists.

## 6. Upload Experience

1. User chooses **Add documents**.
2. A small unlock dialog requests the upload password.
3. On success, a larger glass panel accepts drag-and-drop or file selection.
4. Each file shows validation, upload, parsing, embedding, and indexed states.
5. Completion states list exactly what was indexed, skipped as duplicate, or failed.

Password errors are generic. Unsupported file type and size errors are specific and actionable.

## 7. Feedback and System States

- Stream answer text without animating every character excessively.
- Show retrieval progress with simple status text, especially in Deep mode.
- Preserve partial answer text if canceled, label it **Stopped**, and do not show a completed confidence rating.
- Empty Sources means a controlled no-answer state, not an empty expandable panel.
- Provider, network, parsing, and indexing errors have human-readable recovery actions.
- The model menu shows provider identity. A model whose key is missing, invalid,
  or lacks access remains visible but disabled with a user-safe status message.
- Toasts are reserved for brief confirmations; durable problems stay near the affected content.

## 8. Accessibility

- Meet WCAG 2.2 AA contrast for text, controls, focus indicators, and state colors.
- All controls are reachable and operable with a keyboard.
- Use semantic buttons, dialogs, lists, and disclosure elements.
- Confidence popover content is associated with its badge using ARIA and announced without relying on hover.
- Citation markers have names such as `Source 1: Employee Handbook, pages 12 to 13`.
- Respect reduced motion and reduced transparency preferences.
- Minimum pointer target is 44 × 44 px where practical.

## 9. Motion and Voice

Use 120–200 ms fades and small translations for drawers, menus, and popovers. Disable nonessential motion when requested by the OS. Avoid bouncing, glowing, or continuous ambient animations.

Writing is concise, factual, and explicit about evidence. Prefer `I couldn't find this in your indexed documents` to vague statements such as `I may not have enough context`.

## 10. Design Acceptance Checklist

- Light and dark themes both preserve readable glass surfaces.
- The current model and retrieval mode are visible before sending.
- Every completed grounded answer shows document/page provenance.
- All five confidence states are distinguishable by label, icon, and color.
- Hover, focus, and tap expose the same five-state confidence legend.
- Low and Very low warnings are visible without interaction.
- Citation, dialog, drawer, and streaming flows pass keyboard testing.
- Responsive layouts work at 360 px, tablet, and desktop widths.
