"use client";

import {
  AlertCircle,
  AlertTriangle,
  BookOpen,
  Check,
  CheckCheck,
  ChevronDown,
  CircleMinus,
  FileText,
  Library,
  LoaderCircle,
  Menu,
  PanelLeftClose,
  Plus,
  Search,
  Send,
  Sparkles,
  X,
} from "lucide-react";
import { FormEvent, KeyboardEvent, useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type ConfidenceLevel =
  | "very_high"
  | "high"
  | "medium"
  | "low"
  | "very_low";

type Confidence = {
  score: number;
  level: ConfidenceLevel;
  label: string;
  rationale: string;
};

type RetrievalMode = "quick" | "medium" | "deep";

type ModelOption = {
  id: string;
  label: string;
  description: string;
};

type RetrievalOption = {
  id: RetrievalMode;
  label: string;
  description: string;
};

type Source = {
  id: number;
  chunk_id: string;
  document_id: string;
  document: string;
  file_name: string;
  page_start: number | null;
  page_end: number | null;
  section: string | null;
  snippet: string;
  relevance: number;
};

type AnsweredFrom = {
  document_id: string;
  document: string;
  pages: string;
};

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  status?: "retrieving" | "streaming" | "completed" | "error";
  answeredFrom?: AnsweredFrom[];
  sources?: Source[];
  confidence?: Confidence;
  error?: string;
};

type ChatSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
};

type ChatDetail = ChatSummary & {
  messages: Array<{
    id: string;
    role: "user" | "assistant";
    content: string;
    answered_from: AnsweredFrom[];
    citations: Source[];
    confidence: Confidence | null;
    status: string;
    created_at: string;
  }>;
};

type ApiHealth = {
  status: string;
  model: string;
  models: ModelOption[];
  retrieval_modes: RetrievalOption[];
  documents: number;
  chunks: number;
  api_key_configured: boolean;
};

const fallbackModels: ModelOption[] = [
  {
    id: "openai/gpt-oss-120b",
    label: "GPT-OSS 120B",
    description: "Best answer quality",
  },
  {
    id: "openai/gpt-oss-20b",
    label: "GPT-OSS 20B",
    description: "Fastest responses",
  },
];

const fallbackRetrievalModes: RetrievalOption[] = [
  { id: "quick", label: "Quick", description: "3 chunks · fastest" },
  { id: "medium", label: "Medium", description: "7 chunks · balanced" },
  { id: "deep", label: "Deep", description: "15 chunks · thorough" },
];

type IndexResult = {
  indexed: string[];
  skipped: string[];
  failed: Record<string, string>;
  chunk_count: number;
};

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ??
  "http://127.0.0.1:8000";

const confidenceStates: Array<{
  level: ConfidenceLevel;
  label: string;
  range: string;
  detail: string;
  icon: typeof Check;
}> = [
  {
    level: "very_high",
    label: "Very high",
    range: "90–100",
    detail: "Direct, complete support",
    icon: CheckCheck,
  },
  {
    level: "high",
    label: "High",
    range: "75–89",
    detail: "Strong support, minor gaps",
    icon: Check,
  },
  {
    level: "medium",
    label: "Medium",
    range: "55–74",
    detail: "Useful but partial support",
    icon: CircleMinus,
  },
  {
    level: "low",
    label: "Low",
    range: "30–54",
    detail: "Weak or conflicting support",
    icon: AlertTriangle,
  },
  {
    level: "very_low",
    label: "Very low",
    range: "0–29",
    detail: "No reliable support found",
    icon: AlertCircle,
  },
];

function pageLabel(source: Source) {
  if (source.page_start === null) {
    return source.section
      ? `Page unavailable · ${source.section}`
      : "Page unavailable";
  }
  if (source.page_end && source.page_end !== source.page_start) {
    return `Pages ${source.page_start}–${source.page_end}`;
  }
  return `Page ${source.page_start}`;
}

function relativeTime(value: string) {
  const elapsedSeconds = Math.max(
    0,
    Math.floor((Date.now() - new Date(value).getTime()) / 1000),
  );
  if (elapsedSeconds < 60) return "Just now";
  if (elapsedSeconds < 3600) return `${Math.floor(elapsedSeconds / 60)}m ago`;
  if (elapsedSeconds < 86400) return `${Math.floor(elapsedSeconds / 3600)}h ago`;
  if (elapsedSeconds < 604800) return `${Math.floor(elapsedSeconds / 86400)}d ago`;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

function ConfidenceBadge({ confidence }: { confidence: Confidence }) {
  const active = confidenceStates.find(
    (state) => state.level === confidence.level,
  )!;
  const ActiveIcon = active.icon;

  return (
    <div className="confidence-wrap">
      <button
        className={`confidence-badge confidence-${confidence.level}`}
        aria-label={`${confidence.label}, ${confidence.score} out of 100. Show confidence scale.`}
        aria-describedby={`confidence-${confidence.level}-details`}
        type="button"
      >
        <ActiveIcon size={15} aria-hidden="true" />
        <span>{confidence.label}</span>
        <span className="confidence-score">{confidence.score}</span>
      </button>
      <div
        className="confidence-popover glass-strong"
        id={`confidence-${confidence.level}-details`}
        role="tooltip"
      >
        <div className="popover-heading">
          <span>Answer confidence</span>
          <strong>{confidence.score}/100</strong>
        </div>
        <p>{confidence.rationale}</p>
        <div className="confidence-scale">
          {confidenceStates.map((state) => {
            const Icon = state.icon;
            return (
              <div
                className={`confidence-row confidence-${state.level} ${
                  state.level === confidence.level ? "is-active" : ""
                }`}
                key={state.level}
              >
                <span className="confidence-icon">
                  <Icon size={14} aria-hidden="true" />
                </span>
                <span>
                  <strong>{state.label}</strong>
                  <small>{state.detail}</small>
                </span>
                <span className="confidence-range">{state.range}</span>
              </div>
            );
          })}
        </div>
        <small className="confidence-note">
          Confidence reflects support in your indexed documents, not a
          guarantee of factual truth.
        </small>
      </div>
    </div>
  );
}

function AnswerMarkdown({
  content,
  sources,
}: {
  content: string;
  sources: Source[];
}) {
  const cited = useMemo(
    () => new Map(sources.map((source) => [source.id, source])),
    [sources],
  );
  const markdown = content.replace(
    /\[(\d+)]/g,
    "[$1](#heritage-source-$1)",
  );

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({ href, children }) => {
          const match = href?.match(/^#heritage-source-(\d+)$/);
          if (!match) {
            return (
              <a href={href} target="_blank" rel="noreferrer">
                {children}
              </a>
            );
          }
          const source = cited.get(Number(match[1]));
          return (
            <a
              className="citation"
              href={
                source
                  ? `${API_URL}/api/documents/${source.document_id}/content${
                      source.page_start ? `#page=${source.page_start}` : ""
                    }`
                  : undefined
              }
              target="_blank"
              rel="noreferrer"
              aria-label={
                source
                  ? `Source ${source.id}: ${source.document}, ${pageLabel(source)}`
                  : `Source ${match[1]}`
              }
            >
              {children}
            </a>
          );
        },
      }}
    >
      {markdown}
    </ReactMarkdown>
  );
}

function Sources({
  sources,
  answeredFrom,
}: {
  sources: Source[];
  answeredFrom: AnsweredFrom[];
}) {
  return (
    <div className="evidence-block">
      <div className="answered-from">
        <BookOpen size={15} aria-hidden="true" />
        <span>Answered from:</span>
        {answeredFrom.length ? (
          answeredFrom.map((source) => (
            <strong key={source.document_id}>
              {source.document} · {source.pages}
            </strong>
          ))
        ) : (
          <strong>No supporting document found</strong>
        )}
      </div>
      {sources.length > 0 && (
        <details className="sources">
          <summary>
            <span>
              <Library size={15} aria-hidden="true" />
              Sources
            </span>
            <span className="source-count">{sources.length}</span>
            <ChevronDown className="summary-chevron" size={15} />
          </summary>
          <div className="source-list">
            {sources.map((source) => (
              <a
                className="source-row"
                href={`${API_URL}/api/documents/${source.document_id}/content${
                  source.page_start ? `#page=${source.page_start}` : ""
                }`}
                target="_blank"
                rel="noreferrer"
                key={source.chunk_id}
                aria-label={`Source ${source.id}: ${source.document}, ${pageLabel(source)}`}
              >
                <span className="source-number">{source.id}</span>
                <span className="source-copy">
                  <strong>{source.document}</strong>
                  <small>{pageLabel(source)}</small>
                  <span>{source.snippet}</span>
                </span>
              </a>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

function AssistantMessage({ message }: { message: Message }) {
  return (
    <article className="assistant-message">
      <div className="assistant-mark" aria-hidden="true">
        H
      </div>
      <div className="assistant-body">
        {message.status === "retrieving" && (
          <div className="thinking">
            <LoaderCircle className="spin" size={16} />
            Searching your documents
          </div>
        )}
        <div className="answer-copy">
          <AnswerMarkdown
            content={message.content}
            sources={message.sources ?? []}
          />
          {message.status === "streaming" && (
            <span className="stream-cursor" aria-hidden="true" />
          )}
        </div>
        {message.error && <p className="message-error">{message.error}</p>}
        {message.status === "completed" && (
          <>
            <Sources
              sources={message.sources ?? []}
              answeredFrom={message.answeredFrom ?? []}
            />
            {message.confidence && (
              <div className="confidence-area">
                <ConfidenceBadge confidence={message.confidence} />
                {(message.confidence.level === "low" ||
                  message.confidence.level === "very_low") && (
                  <p className="low-confidence-note">
                    {message.confidence.rationale}
                  </p>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </article>
  );
}

export default function Home() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileSidebar, setMobileSidebar] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [activeChatTitle, setActiveChatTitle] = useState("New conversation");
  const [historySearch, setHistorySearch] = useState("");
  const [loadingChat, setLoadingChat] = useState(false);
  const [health, setHealth] = useState<ApiHealth | null>(null);
  const [indexing, setIndexing] = useState(false);
  const [indexResult, setIndexResult] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [selectedModel, setSelectedModel] = useState(
    "openai/gpt-oss-120b",
  );
  const [retrievalMode, setRetrievalMode] =
    useState<RetrievalMode>("medium");

  async function loadHealth() {
    try {
      const response = await fetch(`${API_URL}/api/health`);
      if (!response.ok) throw new Error("API unavailable");
      const data: ApiHealth = await response.json();
      setHealth(data);
      setSelectedModel((current) =>
        data.models.some((model) => model.id === current)
          ? current
          : data.model,
      );
    } catch {
      setHealth(null);
    }
  }

  async function openChat(chat: ChatSummary) {
    if (isSending) return;
    setLoadingChat(true);
    setActiveChatId(chat.id);
    setActiveChatTitle(chat.title);
    setMobileSidebar(false);
    try {
      const response = await fetch(`${API_URL}/api/chats/${chat.id}`);
      if (!response.ok) throw new Error("Conversation unavailable");
      const detail: ChatDetail = await response.json();
      setMessages(
        detail.messages.map((message) => ({
          id: message.id,
          role: message.role,
          content: message.content,
          status:
            message.role === "assistant"
              ? message.status === "completed"
                ? "completed"
                : "error"
              : undefined,
          answeredFrom: message.answered_from,
          sources: message.citations,
          confidence: message.confidence ?? undefined,
        })),
      );
      setActiveChatTitle(detail.title);
    } catch {
      setMessages([]);
    } finally {
      setLoadingChat(false);
    }
  }

  async function loadChats(restoreLatest = false) {
    try {
      const response = await fetch(`${API_URL}/api/chats`);
      if (!response.ok) throw new Error("Chat history unavailable");
      const data: ChatSummary[] = await response.json();
      setChats(data);
      if (restoreLatest && data.length > 0) {
        await openChat(data[0]);
      }
    } catch {
      setChats([]);
    }
  }

  useEffect(() => {
    void loadHealth();
    void loadChats(true);
  }, []);

  function startNewChat() {
    if (isSending) return;
    setActiveChatId(null);
    setActiveChatTitle("New conversation");
    setMessages([]);
    setInput("");
    setMobileSidebar(false);
  }

  async function reindex() {
    setIndexing(true);
    setIndexResult(null);
    try {
      const response = await fetch(`${API_URL}/api/documents/reindex`, {
        method: "POST",
      });
      if (!response.ok) throw new Error("Indexing failed");
      const result: IndexResult = await response.json();
      const indexed = result.indexed.length;
      const skipped = result.skipped.length;
      setIndexResult(
        result.failed && Object.keys(result.failed).length
          ? `${indexed} indexed, ${Object.keys(result.failed).length} failed`
          : `${indexed} indexed, ${skipped} unchanged`,
      );
      await loadHealth();
    } catch {
      setIndexResult("Could not index documents");
    } finally {
      setIndexing(false);
    }
  }

  async function sendMessage(event?: FormEvent) {
    event?.preventDefault();
    const question = input.trim();
    if (!question || isSending) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: question,
    };
    const assistantId = crypto.randomUUID();
    const assistantMessage: Message = {
      id: assistantId,
      role: "assistant",
      content: "",
      status: "retrieving",
    };
    setMessages((current) => [
      ...current,
      userMessage,
      assistantMessage,
    ]);
    setInput("");
    setIsSending(true);
    const requestChatId = activeChatId;

    try {
      const response = await fetch(`${API_URL}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: question,
          chat_id: requestChatId,
          model: selectedModel,
          retrieval_mode: retrievalMode,
        }),
      });
      if (!response.ok || !response.body) {
        throw new Error("The answer service is unavailable.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let streamed = "";
      let receivedCompletion = false;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          const eventLine = block
            .split("\n")
            .find((line) => line.startsWith("event: "));
          const dataLine = block
            .split("\n")
            .find((line) => line.startsWith("data: "));
          if (!eventLine || !dataLine) continue;
          const eventName = eventLine.slice(7);
          const data = JSON.parse(dataLine.slice(6));

          if (eventName === "chat.created") {
            const createdChat = data as ChatSummary;
            setActiveChatId(createdChat.id);
            setActiveChatTitle(createdChat.title);
            setChats((current) => [
              createdChat,
              ...current.filter((chat) => chat.id !== createdChat.id),
            ]);
          }
          if (eventName === "answer.delta") {
            streamed += data.text;
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? { ...message, content: streamed, status: "streaming" }
                  : message,
              ),
            );
          }
          if (eventName === "answer.completed") {
            receivedCompletion = true;
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? {
                      ...message,
                      content: data.answer,
                      status: "completed",
                      answeredFrom: data.answered_from,
                      sources: data.citations,
                      confidence: data.confidence,
                    }
                  : message,
                ),
            );
          }
          if (eventName === "error") {
            throw new Error(data.message ?? "The answer could not be completed.");
          }
        }
      }
      if (!receivedCompletion) {
        throw new Error("The answer stream ended before completion.");
      }
      await loadChats();
    } catch (error) {
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                status: "error",
                error:
                  error instanceof Error
                    ? error.message
                    : "Something went wrong.",
              }
            : message,
        ),
      );
    } finally {
      setIsSending(false);
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  }

  const empty = messages.length === 0;
  const filteredChats = chats.filter((chat) =>
    chat.title.toLowerCase().includes(historySearch.trim().toLowerCase()),
  );
  const modelOptions = health?.models ?? fallbackModels;
  const retrievalOptions =
    health?.retrieval_modes ?? fallbackRetrievalModes;
  const selectedModelOption =
    modelOptions.find((model) => model.id === selectedModel) ??
    modelOptions[0];
  const selectedRetrievalOption =
    retrievalOptions.find((mode) => mode.id === retrievalMode) ??
    retrievalOptions[1];

  return (
    <main className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <aside
        className={`sidebar glass ${sidebarOpen ? "" : "is-collapsed"} ${
          mobileSidebar ? "is-mobile-open" : ""
        }`}
      >
        <div className="brand-row">
          <div className="brand">
            <span className="brand-mark">H</span>
            {sidebarOpen && <span>HERITAGE</span>}
          </div>
          <button
            className="icon-button desktop-only"
            onClick={() => setSidebarOpen((value) => !value)}
            aria-label={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
            type="button"
          >
            <PanelLeftClose
              size={18}
              className={sidebarOpen ? "" : "flipped"}
            />
          </button>
          <button
            className="icon-button mobile-only"
            onClick={() => setMobileSidebar(false)}
            aria-label="Close sidebar"
            type="button"
          >
            <X size={18} />
          </button>
        </div>

        <button
          className="new-chat"
          type="button"
          onClick={startNewChat}
          disabled={isSending}
        >
          <Plus size={17} />
          {sidebarOpen && <span>New conversation</span>}
        </button>

        {sidebarOpen && (
          <>
            <div className="sidebar-search">
              <Search size={15} aria-hidden="true" />
              <input
                value={historySearch}
                onChange={(event) => setHistorySearch(event.target.value)}
                placeholder="Search conversations"
                aria-label="Search conversations"
              />
            </div>
            <div className="history-label">Recent</div>
            <div className="history-list">
              {filteredChats.map((chat) => (
                <button
                  className={`history-item ${
                    chat.id === activeChatId ? "is-selected" : ""
                  }`}
                  type="button"
                  key={chat.id}
                  onClick={() => void openChat(chat)}
                  disabled={isSending}
                  aria-pressed={chat.id === activeChatId}
                >
                  <span>{chat.title}</span>
                  <small>{relativeTime(chat.updated_at)}</small>
                </button>
              ))}
              {chats.length === 0 && (
                <p className="history-empty">No conversations yet</p>
              )}
              {chats.length > 0 && filteredChats.length === 0 && (
                <p className="history-empty">No matching conversations</p>
              )}
            </div>
          </>
        )}

        <div className="sidebar-spacer" />
        <div className="knowledge-card">
          <div className="knowledge-icon">
            <Library size={17} />
          </div>
          {sidebarOpen && (
            <div>
              <strong>Your knowledge</strong>
              <span>
                {health
                  ? `${health.documents} document${health.documents === 1 ? "" : "s"} · ${health.chunks} chunks`
                  : "API offline"}
              </span>
            </div>
          )}
        </div>
        <button
          className="index-button"
          type="button"
          onClick={reindex}
          disabled={indexing}
        >
          {indexing ? (
            <LoaderCircle className="spin" size={16} />
          ) : (
            <FileText size={16} />
          )}
          {sidebarOpen && (
            <span>{indexing ? "Indexing…" : "Index documents"}</span>
          )}
        </button>
        {sidebarOpen && indexResult && (
          <p className="index-result">{indexResult}</p>
        )}
      </aside>

      {mobileSidebar && (
        <button
          className="mobile-scrim"
          type="button"
          aria-label="Close sidebar"
          onClick={() => setMobileSidebar(false)}
        />
      )}

      <section className="workspace">
        <header className="topbar">
          <button
            className="icon-button mobile-menu mobile-only"
            onClick={() => setMobileSidebar(true)}
            aria-label="Open sidebar"
            type="button"
          >
            <Menu size={20} />
          </button>
          <div className="conversation-title">
            <span className="eyebrow">DOCUMENT ASSISTANT</span>
            <strong>{activeChatTitle}</strong>
          </div>
          <div className="privacy-chip">
            <span className={`status-dot ${health ? "online" : ""}`} />
            {health ? "Local index ready" : "API offline"}
          </div>
        </header>

        <div className={`conversation ${empty ? "is-empty" : ""}`}>
          {loadingChat ? (
            <div className="chat-loading">
              <LoaderCircle className="spin" size={20} />
              Loading conversation
            </div>
          ) : empty ? (
            <div className="welcome">
              <div className="welcome-mark">
                <Sparkles size={24} />
              </div>
              <p className="eyebrow">YOUR DOCUMENTS, WITH RECEIPTS</p>
              <h1>Ask what your documents know.</h1>
              <p className="welcome-copy">
                Heritage answers from your local library, shows the exact page,
                and tells you how strongly the evidence supports each response.
              </p>
              <button
                className="prompt-card glass-strong"
                type="button"
                onClick={() =>
                  setInput(
                    "What are the four components of experiential learning?",
                  )
                }
              >
                <span>Try a grounded question</span>
                <strong>
                  What are the four components of experiential learning?
                </strong>
                <span className="prompt-arrow">↗</span>
              </button>
              {health && health.documents === 0 && (
                <button
                  className="index-callout"
                  onClick={reindex}
                  disabled={indexing}
                  type="button"
                >
                  <Library size={16} />
                  Index the document folder to begin
                </button>
              )}
            </div>
          ) : (
            <div className="message-list" aria-live="polite">
              {messages.map((message) =>
                message.role === "user" ? (
                  <div className="user-row" key={message.id}>
                    <div className="user-message">{message.content}</div>
                  </div>
                ) : (
                  <AssistantMessage message={message} key={message.id} />
                ),
              )}
            </div>
          )}
        </div>

        <div className="composer-zone">
          <form className="composer glass-strong" onSubmit={sendMessage}>
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleComposerKeyDown}
              placeholder="Ask your documents…"
              rows={1}
              aria-label="Ask your documents"
              disabled={isSending}
            />
            <div className="composer-tools">
              <div className="tool-chips">
                <details className="tool-selector model-selector" name="composer-tool">
                  <summary
                    className="tool-chip"
                    aria-label={`Model: ${selectedModelOption.label}`}
                  >
                    <span className="groq-mark">G</span>
                    {selectedModelOption.label}
                    <ChevronDown className="tool-chevron" size={13} />
                  </summary>
                  <div className="selector-menu glass-strong" role="menu">
                    <div className="selector-heading">
                      <span>Groq model</span>
                      <small>Applies to this message</small>
                    </div>
                    {modelOptions.map((model) => (
                      <button
                        className={`selector-option ${
                          model.id === selectedModel ? "is-selected" : ""
                        }`}
                        type="button"
                        role="menuitemradio"
                        aria-checked={model.id === selectedModel}
                        key={model.id}
                        onClick={(event) => {
                          setSelectedModel(model.id);
                          const details = event.currentTarget.closest("details");
                          if (details) details.open = false;
                        }}
                      >
                        <span className="selector-check">
                          {model.id === selectedModel && <Check size={13} />}
                        </span>
                        <span>
                          <strong>{model.label}</strong>
                          <small>{model.description}</small>
                        </span>
                      </button>
                    ))}
                  </div>
                </details>

                <details
                  className="tool-selector retrieval-selector"
                  name="composer-tool"
                >
                  <summary
                    className="tool-chip"
                    aria-label={`Retrieval depth: ${selectedRetrievalOption.label}`}
                  >
                    <span className={`depth-bars depth-${retrievalMode}`}>
                      <i />
                      <i />
                      <i />
                    </span>
                    {selectedRetrievalOption.label}
                    <ChevronDown className="tool-chevron" size={13} />
                  </summary>
                  <div className="selector-menu glass-strong" role="menu">
                    <div className="selector-heading">
                      <span>Retrieval depth</span>
                      <small>More depth may take longer</small>
                    </div>
                    {retrievalOptions.map((mode) => (
                      <button
                        className={`selector-option ${
                          mode.id === retrievalMode ? "is-selected" : ""
                        }`}
                        type="button"
                        role="menuitemradio"
                        aria-checked={mode.id === retrievalMode}
                        key={mode.id}
                        onClick={(event) => {
                          setRetrievalMode(mode.id);
                          const details = event.currentTarget.closest("details");
                          if (details) details.open = false;
                        }}
                      >
                        <span className="selector-check">
                          {mode.id === retrievalMode && <Check size={13} />}
                        </span>
                        <span>
                          <strong>{mode.label}</strong>
                          <small>{mode.description}</small>
                        </span>
                      </button>
                    ))}
                  </div>
                </details>
              </div>
              <button
                className="send-button"
                type="submit"
                disabled={!input.trim() || isSending}
                aria-label="Send message"
              >
                {isSending ? (
                  <LoaderCircle className="spin" size={18} />
                ) : (
                  <Send size={18} />
                )}
              </button>
            </div>
          </form>
          <p className="composer-note">
            Answers use indexed evidence. Verify important details on the cited
            pages.
          </p>
        </div>
      </section>
    </main>
  );
}
