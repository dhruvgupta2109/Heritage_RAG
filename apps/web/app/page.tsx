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
  FileUp,
  Library,
  LoaderCircle,
  LockKeyhole,
  Menu,
  MoreHorizontal,
  PanelLeftClose,
  Pencil,
  Pin,
  PinOff,
  Plus,
  RotateCcw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import {
  ChangeEvent,
  DragEvent,
  FormEvent,
  KeyboardEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
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
  provider: "groq" | "openai" | "gemini";
  provider_label: string;
  label: string;
  description: string;
  available: boolean;
  status: string;
};

type RetrievalOption = {
  id: RetrievalMode;
  label: string;
  description: string;
};

export type Source = {
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

export type ChatSummary = {
  id: string;
  title: string;
  pinned: boolean;
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
  providers: Array<{
    id: string;
    label: string;
    configured: boolean;
    available: boolean;
    message: string;
  }>;
  retrieval_modes: RetrievalOption[];
  documents: number;
  chunks: number;
  api_key_configured: boolean;
};

const fallbackModels: ModelOption[] = [
  {
    id: "openai/gpt-oss-120b",
    provider: "groq",
    provider_label: "Groq",
    label: "GPT-OSS 120B",
    description: "Best answer quality",
    available: true,
    status: "Ready",
  },
  {
    id: "openai/gpt-oss-20b",
    provider: "groq",
    provider_label: "Groq",
    label: "GPT-OSS 20B",
    description: "Fastest responses",
    available: true,
    status: "Ready",
  },
];

const fallbackRetrievalModes: RetrievalOption[] = [
  { id: "quick", label: "Quick", description: "3 chunks · vector search" },
  { id: "medium", label: "Medium", description: "7 chunks · hybrid ranking" },
  {
    id: "deep",
    label: "Deep",
    description: "15 chunks · query expansion + full re-rank",
  },
];

type IndexResult = {
  indexed: string[];
  skipped: string[];
  failed: Record<string, string>;
  chunk_count: number;
};

type UploadStep = "checking" | "locked" | "ready" | "uploading";

type UploadItemStatus =
  | "ready"
  | "queued"
  | "uploading"
  | "indexing"
  | "indexed"
  | "duplicate"
  | "failed";

type UploadItem = {
  id: string;
  file: File;
  status: UploadItemStatus;
  progress: number;
  error?: string;
  chunkCount?: number;
};

export type ChatHistoryGroup = {
  label: string;
  chats: ChatSummary[];
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

function chatSort(left: ChatSummary, right: ChatSummary) {
  if (left.pinned !== right.pinned) return left.pinned ? -1 : 1;
  return (
    new Date(right.updated_at).getTime() -
    new Date(left.updated_at).getTime()
  );
}

function calendarDay(value: Date) {
  return Date.UTC(value.getFullYear(), value.getMonth(), value.getDate());
}

export function groupChatsByDate(
  chats: ChatSummary[],
  now = new Date(),
): ChatHistoryGroup[] {
  const ordered = [...chats].sort(chatSort);
  const pinned = ordered.filter((chat) => chat.pinned);
  const groups: ChatHistoryGroup[] = pinned.length
    ? [{ label: "Pinned", chats: pinned }]
    : [];
  const buckets = new Map<string, ChatSummary[]>();
  const today = calendarDay(now);
  const dayMilliseconds = 24 * 60 * 60 * 1000;

  for (const chat of ordered) {
    if (chat.pinned) continue;
    const updated = new Date(chat.updated_at);
    let label = "Older";

    if (!Number.isNaN(updated.getTime())) {
      const daysAgo = Math.floor(
        (today - calendarDay(updated)) / dayMilliseconds,
      );
      if (daysAgo <= 0) label = "Today";
      else if (daysAgo === 1) label = "Yesterday";
      else if (daysAgo <= 7) label = "Previous 7 days";
      else if (daysAgo <= 30) label = "Previous 30 days";
      else {
        label = new Intl.DateTimeFormat("en-US", {
          month: "long",
          year: "numeric",
        }).format(updated);
      }
    }

    const group = buckets.get(label);
    if (group) group.push(chat);
    else buckets.set(label, [chat]);
  }

  for (const [label, group] of buckets) {
    groups.push({ label, chats: group });
  }
  return groups;
}

function formatFileSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function responseError(response: Response, fallback: string) {
  try {
    const body = await response.json();
    return typeof body.detail === "string" ? body.detail : fallback;
  } catch {
    return fallback;
  }
}

class UploadRequestError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "UploadRequestError";
    this.status = status;
  }
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

export function AnswerMarkdown({
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
  const markdown = content
    .replace(/\[(\d+)]\s+([,.;:!?])/g, "[$1]$2")
    .replace(/\[(\d+)]/g, "[$1](#heritage-source-$1)");

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({ href, children }) => {
          const match = href?.match(/^#heritage-source-(\d+)$/);
          if (!match) {
            return (
              <a
                className="answer-link"
                href={href}
                target="_blank"
                rel="noreferrer"
              >
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
        table: ({ children }) => (
          <div
            className="answer-table-wrap"
            role="region"
            aria-label="Answer table"
            tabIndex={0}
          >
            <table>{children}</table>
          </div>
        ),
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
  const [renameChat, setRenameChat] = useState<ChatSummary | null>(null);
  const [renameTitle, setRenameTitle] = useState("");
  const [deleteChat, setDeleteChat] = useState<ChatSummary | null>(null);
  const [chatActionError, setChatActionError] = useState<string | null>(null);
  const [chatActionBusy, setChatActionBusy] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadStep, setUploadStep] = useState<UploadStep>("checking");
  const [uploadPassword, setUploadPassword] = useState("");
  const [uploadFiles, setUploadFiles] = useState<UploadItem[]>([]);
  const [uploadFeedback, setUploadFeedback] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [draggingFiles, setDraggingFiles] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
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
        data.models.some((model) => model.id === current && model.available)
          ? current
          : (data.models.find((model) => model.available)?.id ?? data.model),
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

  useEffect(() => {
    const menuSelector = ".tool-selector[open], .history-actions[open]";

    function handleOutsidePointer(event: PointerEvent) {
      const target = event.target;
      if (!(target instanceof Node)) return;
      document
        .querySelectorAll<HTMLDetailsElement>(menuSelector)
        .forEach((menu) => {
          if (!menu.contains(target)) menu.open = false;
        });
    }

    function handleMenuEscape(event: globalThis.KeyboardEvent) {
      if (event.key !== "Escape") return;
      const openMenus =
        document.querySelectorAll<HTMLDetailsElement>(menuSelector);
      const returnFocus = openMenus[0]?.querySelector<HTMLElement>("summary");
      openMenus.forEach((menu) => {
        menu.open = false;
      });
      returnFocus?.focus();
    }

    document.addEventListener("pointerdown", handleOutsidePointer);
    document.addEventListener("keydown", handleMenuEscape);
    return () => {
      document.removeEventListener("pointerdown", handleOutsidePointer);
      document.removeEventListener("keydown", handleMenuEscape);
    };
  }, []);

  useEffect(() => {
    if (!renameChat && !deleteChat && !uploadOpen) return;
    function handleEscape(event: globalThis.KeyboardEvent) {
      if (event.key !== "Escape" || chatActionBusy || uploadStep === "uploading") {
        return;
      }
      setRenameChat(null);
      setDeleteChat(null);
      setUploadOpen(false);
    }
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [renameChat, deleteChat, uploadOpen, chatActionBusy, uploadStep]);

  function startNewChat() {
    if (isSending) return;
    setActiveChatId(null);
    setActiveChatTitle("New conversation");
    setMessages([]);
    setInput("");
    setMobileSidebar(false);
  }

  async function pinChat(chat: ChatSummary) {
    if (chatActionBusy) return;
    setChatActionBusy(true);
    setChatActionError(null);
    try {
      const response = await fetch(`${API_URL}/api/chats/${chat.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pinned: !chat.pinned }),
      });
      if (!response.ok) {
        throw new Error(await responseError(response, "Could not update conversation."));
      }
      const updated: ChatSummary = await response.json();
      setChats((current) =>
        current
          .map((item) => (item.id === updated.id ? updated : item))
          .sort(chatSort),
      );
    } catch (error) {
      setChatActionError(
        error instanceof Error ? error.message : "Could not update conversation.",
      );
    } finally {
      setChatActionBusy(false);
    }
  }

  function beginRename(chat: ChatSummary) {
    setChatActionError(null);
    setRenameChat(chat);
    setRenameTitle(chat.title);
  }

  async function submitRename(event: FormEvent) {
    event.preventDefault();
    const title = renameTitle.trim();
    if (!renameChat || !title || chatActionBusy) return;
    setChatActionBusy(true);
    setChatActionError(null);
    try {
      const response = await fetch(`${API_URL}/api/chats/${renameChat.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      if (!response.ok) {
        throw new Error(await responseError(response, "Could not rename conversation."));
      }
      const updated: ChatSummary = await response.json();
      setChats((current) =>
        current
          .map((item) => (item.id === updated.id ? updated : item))
          .sort(chatSort),
      );
      if (activeChatId === updated.id) setActiveChatTitle(updated.title);
      setRenameChat(null);
    } catch (error) {
      setChatActionError(
        error instanceof Error ? error.message : "Could not rename conversation.",
      );
    } finally {
      setChatActionBusy(false);
    }
  }

  async function confirmDeleteChat() {
    if (!deleteChat || chatActionBusy || isSending) return;
    setChatActionBusy(true);
    setChatActionError(null);
    try {
      const response = await fetch(`${API_URL}/api/chats/${deleteChat.id}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(await responseError(response, "Could not delete conversation."));
      }
      setChats((current) => current.filter((chat) => chat.id !== deleteChat.id));
      if (activeChatId === deleteChat.id) startNewChat();
      setDeleteChat(null);
    } catch (error) {
      setChatActionError(
        error instanceof Error ? error.message : "Could not delete conversation.",
      );
    } finally {
      setChatActionBusy(false);
    }
  }

  async function openUploadDialog() {
    setUploadOpen(true);
    setUploadStep("checking");
    setUploadError(null);
    setUploadFeedback(null);
    setUploadFiles([]);
    try {
      const response = await fetch(`${API_URL}/api/uploads/session`, {
        credentials: "include",
      });
      if (!response.ok) throw new Error("Could not check upload access.");
      const session: { unlocked: boolean } = await response.json();
      setUploadStep(session.unlocked ? "ready" : "locked");
    } catch {
      setUploadStep("locked");
      setUploadError("The upload service is unavailable.");
    }
  }

  function closeUploadDialog() {
    if (uploadStep === "uploading") return;
    setUploadOpen(false);
    setUploadPassword("");
    setDraggingFiles(false);
  }

  async function unlockUploads(event: FormEvent) {
    event.preventDefault();
    if (!uploadPassword || uploadStep === "checking") return;
    setUploadError(null);
    try {
      const response = await fetch(`${API_URL}/api/uploads/unlock`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: uploadPassword }),
      });
      if (!response.ok) {
        throw new Error(await responseError(response, "Could not unlock uploads."));
      }
      setUploadPassword("");
      setUploadStep("ready");
    } catch (error) {
      setUploadError(
        error instanceof Error ? error.message : "Could not unlock uploads.",
      );
    }
  }

  function selectUploadFiles(files: FileList | File[]) {
    const selected = Array.from(files).slice(0, 20);
    setUploadFiles(
      selected.map((file) => ({
        id: crypto.randomUUID(),
        file,
        status: "ready",
        progress: 0,
      })),
    );
    setUploadFeedback(null);
    setUploadError(
      selected.length < files.length
        ? "You can upload up to 20 documents at a time."
        : null,
    );
  }

  function handleFileInput(event: ChangeEvent<HTMLInputElement>) {
    if (event.target.files) selectUploadFiles(event.target.files);
  }

  function handleFileDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDraggingFiles(false);
    if (event.dataTransfer.files.length) {
      selectUploadFiles(event.dataTransfer.files);
    }
  }

  function updateUploadItem(id: string, changes: Partial<UploadItem>) {
    setUploadFiles((current) =>
      current.map((item) =>
        item.id === id ? { ...item, ...changes } : item,
      ),
    );
  }

  function uploadDocument(item: UploadItem) {
    return new Promise<IndexResult>((resolve, reject) => {
      const request = new XMLHttpRequest();
      const form = new FormData();
      form.append("files", item.file);

      request.open("POST", `${API_URL}/api/documents/upload`);
      request.withCredentials = true;
      request.setRequestHeader("Accept", "application/json");

      request.upload.addEventListener("loadstart", () => {
        updateUploadItem(item.id, {
          status: "uploading",
          progress: 0,
          error: undefined,
        });
      });
      request.upload.addEventListener("progress", (event) => {
        updateUploadItem(item.id, {
          status: "uploading",
          progress: event.lengthComputable
            ? Math.min(100, Math.round((event.loaded / event.total) * 100))
            : 0,
        });
      });
      request.upload.addEventListener("load", () => {
        updateUploadItem(item.id, {
          status: "indexing",
          progress: 100,
        });
      });
      request.addEventListener("load", () => {
        let payload: unknown = null;
        try {
          payload = request.responseText
            ? JSON.parse(request.responseText)
            : null;
        } catch {
          payload = null;
        }

        if (request.status >= 200 && request.status < 300) {
          resolve(payload as IndexResult);
          return;
        }
        const detail =
          payload &&
          typeof payload === "object" &&
          "detail" in payload &&
          typeof payload.detail === "string"
            ? payload.detail
            : "Could not upload this document.";
        reject(new UploadRequestError(detail, request.status));
      });
      request.addEventListener("error", () => {
        reject(
          new UploadRequestError(
            "The upload could not reach the local API. Try again.",
            0,
          ),
        );
      });
      request.addEventListener("abort", () => {
        reject(new UploadRequestError("The upload was stopped.", 0));
      });
      request.send(form);
    });
  }

  async function uploadDocuments(items = uploadFiles.filter(
    (item) => item.status === "ready",
  )) {
    if (!items.length || uploadStep !== "ready") return;
    setUploadStep("uploading");
    setUploadError(null);
    setUploadFeedback(null);
    setUploadFiles((current) =>
      current.map((item) =>
        items.some((candidate) => candidate.id === item.id)
          ? { ...item, status: "queued", progress: 0, error: undefined }
          : item,
      ),
    );

    let indexed = 0;
    let duplicates = 0;
    let failed = 0;
    let chunkCount = 0;
    let sessionExpired = false;

    for (const item of items) {
      try {
        const result = await uploadDocument(item);
        if (result.indexed.length > 0) {
          indexed += 1;
          chunkCount += result.chunk_count;
          updateUploadItem(item.id, {
            status: "indexed",
            progress: 100,
            chunkCount: result.chunk_count,
          });
        } else if (result.skipped.length > 0) {
          duplicates += 1;
          updateUploadItem(item.id, {
            status: "duplicate",
            progress: 100,
          });
        } else {
          failed += 1;
          updateUploadItem(item.id, {
            status: "failed",
            error:
              Object.values(result.failed)[0] ??
              "The document was not indexed.",
          });
        }
      } catch (error) {
        failed += 1;
        const message =
          error instanceof Error
            ? error.message
            : "Could not upload this document.";
        updateUploadItem(item.id, { status: "failed", error: message });
        if (error instanceof UploadRequestError && error.status === 401) {
          sessionExpired = true;
          setUploadFiles((current) =>
            current.map((candidate) =>
              candidate.status === "queued"
                ? { ...candidate, status: "ready" }
                : candidate,
            ),
          );
          setUploadError(
            "Upload access expired. Unlock uploads, then retry the failed document.",
          );
          setUploadStep("locked");
          break;
        }
      }
    }

    const resultParts: string[] = [];
    if (indexed) {
      resultParts.push(
        `${indexed} indexed (${chunkCount} chunk${chunkCount === 1 ? "" : "s"})`,
      );
    }
    if (duplicates) resultParts.push(`${duplicates} already indexed`);
    if (failed) resultParts.push(`${failed} failed`);
    setUploadFeedback(resultParts.join(" · ") || "No documents were added.");
    if (indexed) await loadHealth();
    if (!sessionExpired) setUploadStep("ready");
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
  const filteredChats = useMemo(
    () =>
      chats.filter((chat) =>
        chat.title.toLowerCase().includes(historySearch.trim().toLowerCase()),
      ),
    [chats, historySearch],
  );
  const historyGroups = useMemo(
    () => groupChatsByDate(filteredChats),
    [filteredChats],
  );
  const readyUploadCount = uploadFiles.filter(
    (item) => item.status === "ready",
  ).length;
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
          {sidebarOpen && (
            <div className="brand">
              <span className="brand-mark" aria-hidden="true">
                <img src="/heritage-logo.png" alt="" />
              </span>
              <span>HERITAGE</span>
            </div>
          )}
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
            <div className="history-list">
              {historyGroups.map((group) => (
                <div className="history-group" key={group.label}>
                  <div className="history-label">{group.label}</div>
                  {group.chats.map((chat) => (
                    <div
                      className={`history-entry ${
                        chat.id === activeChatId ? "is-selected" : ""
                      }`}
                      key={chat.id}
                    >
                      <button
                        className="history-item"
                        type="button"
                        onClick={() => void openChat(chat)}
                        disabled={isSending}
                        aria-pressed={chat.id === activeChatId}
                      >
                        <span className="history-title">
                          {chat.pinned && (
                            <Pin size={11} aria-label="Pinned conversation" />
                          )}
                          <span>{chat.title}</span>
                        </span>
                        <small>{relativeTime(chat.updated_at)}</small>
                      </button>
                      <details className="history-actions">
                        <summary
                          aria-label={`Actions for ${chat.title}`}
                          title="Conversation actions"
                        >
                          <MoreHorizontal size={16} />
                        </summary>
                        <div className="history-menu glass-strong" role="menu">
                          <button
                            type="button"
                            role="menuitem"
                            onClick={(event) => {
                              beginRename(chat);
                              const details =
                                event.currentTarget.closest("details");
                              if (details) details.open = false;
                            }}
                          >
                            <Pencil size={14} />
                            Rename
                          </button>
                          <button
                            type="button"
                            role="menuitem"
                            onClick={(event) => {
                              void pinChat(chat);
                              const details =
                                event.currentTarget.closest("details");
                              if (details) details.open = false;
                            }}
                          >
                            {chat.pinned ? (
                              <PinOff size={14} />
                            ) : (
                              <Pin size={14} />
                            )}
                            {chat.pinned ? "Unpin" : "Pin"}
                          </button>
                          <button
                            className="danger-action"
                            type="button"
                            role="menuitem"
                            disabled={isSending}
                            onClick={(event) => {
                              setChatActionError(null);
                              setDeleteChat(chat);
                              const details =
                                event.currentTarget.closest("details");
                              if (details) details.open = false;
                            }}
                          >
                            <Trash2 size={14} />
                            Delete
                          </button>
                        </div>
                      </details>
                    </div>
                  ))}
                </div>
              ))}
              {chats.length === 0 && (
                <p className="history-empty">No conversations yet</p>
              )}
              {chats.length > 0 && filteredChats.length === 0 && (
                <p className="history-empty">No matching conversations</p>
              )}
              {chatActionError && !renameChat && !deleteChat && (
                <p className="history-error">{chatActionError}</p>
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
          className="add-documents"
          type="button"
          onClick={() => void openUploadDialog()}
          disabled={indexing}
        >
          <LockKeyhole size={16} />
          {sidebarOpen && <span>Add documents</span>}
        </button>
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
                    <span
                      className={`provider-mark provider-${selectedModelOption.provider}`}
                    >
                      {selectedModelOption.provider_label.slice(0, 1)}
                    </span>
                    {selectedModelOption.label}
                    <ChevronDown className="tool-chevron" size={13} />
                  </summary>
                  <div className="selector-menu glass-strong" role="menu">
                    <div className="selector-heading">
                      <span>Answer model</span>
                      <small>Unavailable providers activate when their key works</small>
                    </div>
                    {modelOptions.map((model) => (
                      <button
                        className={`selector-option ${
                          model.id === selectedModel ? "is-selected" : ""
                        } ${model.available ? "" : "is-unavailable"}`}
                        type="button"
                        role="menuitemradio"
                        aria-checked={model.id === selectedModel}
                        aria-disabled={!model.available}
                        disabled={!model.available}
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
                          <small>
                            {model.provider_label} ·{" "}
                            {model.available ? model.description : model.status}
                          </small>
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

      {renameChat && (
        <div
          className="modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !chatActionBusy) {
              setRenameChat(null);
            }
          }}
        >
          <section
            className="modal-card compact-modal glass-strong"
            role="dialog"
            aria-modal="true"
            aria-labelledby="rename-chat-title"
          >
            <div className="modal-heading">
              <div>
                <span className="modal-icon">
                  <Pencil size={17} />
                </span>
                <div>
                  <h2 id="rename-chat-title">Rename conversation</h2>
                  <p>Choose a title that will be easy to find later.</p>
                </div>
              </div>
              <button
                className="icon-button"
                type="button"
                onClick={() => setRenameChat(null)}
                disabled={chatActionBusy}
                aria-label="Close rename dialog"
              >
                <X size={18} />
              </button>
            </div>
            <form onSubmit={submitRename}>
              <label className="field-label" htmlFor="rename-chat-input">
                Conversation title
              </label>
              <input
                className="modal-input"
                id="rename-chat-input"
                value={renameTitle}
                onChange={(event) => setRenameTitle(event.target.value)}
                maxLength={120}
                autoFocus
              />
              {chatActionError && (
                <p className="modal-error">{chatActionError}</p>
              )}
              <div className="modal-actions">
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => setRenameChat(null)}
                  disabled={chatActionBusy}
                >
                  Cancel
                </button>
                <button
                  className="primary-button"
                  type="submit"
                  disabled={!renameTitle.trim() || chatActionBusy}
                >
                  {chatActionBusy && <LoaderCircle className="spin" size={15} />}
                  Save title
                </button>
              </div>
            </form>
          </section>
        </div>
      )}

      {deleteChat && (
        <div
          className="modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !chatActionBusy) {
              setDeleteChat(null);
            }
          }}
        >
          <section
            className="modal-card compact-modal glass-strong"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="delete-chat-title"
            aria-describedby="delete-chat-description"
          >
            <div className="modal-heading">
              <div>
                <span className="modal-icon danger-icon">
                  <Trash2 size={17} />
                </span>
                <div>
                  <h2 id="delete-chat-title">Delete conversation?</h2>
                  <p id="delete-chat-description">
                    “{deleteChat.title}” and all its saved messages will be
                    permanently removed.
                  </p>
                </div>
              </div>
            </div>
            {chatActionError && (
              <p className="modal-error">{chatActionError}</p>
            )}
            <div className="modal-actions">
              <button
                className="secondary-button"
                type="button"
                onClick={() => setDeleteChat(null)}
                disabled={chatActionBusy}
              >
                Cancel
              </button>
              <button
                className="danger-button"
                type="button"
                onClick={() => void confirmDeleteChat()}
                disabled={chatActionBusy || isSending}
                autoFocus
              >
                {chatActionBusy && <LoaderCircle className="spin" size={15} />}
                Delete conversation
              </button>
            </div>
          </section>
        </div>
      )}

      {uploadOpen && (
        <div
          className="modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeUploadDialog();
          }}
        >
          <section
            className="modal-card upload-modal glass-strong"
            role="dialog"
            aria-modal="true"
            aria-labelledby="upload-title"
          >
            <div className="modal-heading">
              <div>
                <span className="modal-icon">
                  {uploadStep === "locked" ? (
                    <LockKeyhole size={18} />
                  ) : (
                    <FileUp size={18} />
                  )}
                </span>
                <div>
                  <h2 id="upload-title">Add documents</h2>
                  <p>
                    {uploadStep === "locked"
                      ? "Unlock this protected action to continue."
                      : "New files are stored locally and indexed immediately."}
                  </p>
                </div>
              </div>
              <button
                className="icon-button"
                type="button"
                onClick={closeUploadDialog}
                disabled={uploadStep === "uploading"}
                aria-label="Close document upload"
              >
                <X size={18} />
              </button>
            </div>

            {uploadStep === "checking" && (
              <div className="upload-checking">
                <LoaderCircle className="spin" size={20} />
                Checking upload access
              </div>
            )}

            {uploadStep === "locked" && (
              <form className="unlock-form" onSubmit={unlockUploads}>
                <label className="field-label" htmlFor="upload-password">
                  Upload password
                </label>
                <div className="password-field">
                  <LockKeyhole size={16} />
                  <input
                    id="upload-password"
                    type="password"
                    value={uploadPassword}
                    onChange={(event) => setUploadPassword(event.target.value)}
                    placeholder="Enter password"
                    autoComplete="current-password"
                    autoFocus
                  />
                </div>
                {uploadError && <p className="modal-error">{uploadError}</p>}
                <button
                  className="primary-button full-button"
                  type="submit"
                  disabled={!uploadPassword}
                >
                  <ShieldCheck size={16} />
                  Unlock document uploads
                </button>
                <p className="security-note">
                  Access expires after 10 minutes. The password is checked by
                  your local API and is not stored in the browser.
                </p>
              </form>
            )}

            {(uploadStep === "ready" || uploadStep === "uploading") && (
              <div className="upload-panel">
                <div
                  className={`drop-zone ${draggingFiles ? "is-dragging" : ""}`}
                  onDragEnter={(event) => {
                    event.preventDefault();
                    setDraggingFiles(true);
                  }}
                  onDragOver={(event) => event.preventDefault()}
                  onDragLeave={(event) => {
                    if (event.currentTarget === event.target) {
                      setDraggingFiles(false);
                    }
                  }}
                  onDrop={handleFileDrop}
                >
                  <Upload size={24} />
                  <strong>Drop documents here</strong>
                  <span>PDF, DOCX, TXT, or MD · up to 25 MB each</span>
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploadStep === "uploading"}
                  >
                    Choose files
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.docx,.txt,.md"
                    multiple
                    onChange={handleFileInput}
                    tabIndex={-1}
                    aria-hidden="true"
                  />
                </div>

                {uploadFiles.length > 0 && (
                  <div className="selected-files">
                    <div className="selected-files-heading">
                      <span>
                        {uploadFiles.length} document
                        {uploadFiles.length === 1 ? "" : "s"} selected
                      </span>
                      <button
                        type="button"
                        onClick={() => {
                          setUploadFiles([]);
                          if (fileInputRef.current) {
                            fileInputRef.current.value = "";
                          }
                        }}
                        disabled={uploadStep === "uploading"}
                      >
                        Clear
                      </button>
                    </div>
                    <div className="selected-file-list">
                      {uploadFiles.map((item) => (
                        <div
                          className={`selected-file is-${item.status}`}
                          key={item.id}
                        >
                          <FileText size={15} />
                          <div className="selected-file-copy">
                            <span>{item.file.name}</span>
                            <small>{formatFileSize(item.file.size)}</small>
                          </div>
                          <div
                            className="selected-file-status"
                            aria-live="polite"
                          >
                            {item.status === "queued" && (
                              <LoaderCircle className="spin" size={13} />
                            )}
                            {item.status === "uploading" && (
                              <Upload size={13} />
                            )}
                            {item.status === "indexing" && (
                              <LoaderCircle className="spin" size={13} />
                            )}
                            {item.status === "indexed" && (
                              <Check size={13} />
                            )}
                            {item.status === "duplicate" && (
                              <CheckCheck size={13} />
                            )}
                            {item.status === "failed" && (
                              <AlertCircle size={13} />
                            )}
                            <span>
                              {item.status === "ready" && "Ready"}
                              {item.status === "queued" && "Queued"}
                              {item.status === "uploading" &&
                                (item.progress
                                  ? `Uploading ${item.progress}%`
                                  : "Uploading…")}
                              {item.status === "indexing" &&
                                "Processing & indexing"}
                              {item.status === "indexed" &&
                                `Indexed · ${item.chunkCount ?? 0} chunk${
                                  item.chunkCount === 1 ? "" : "s"
                                }`}
                              {item.status === "duplicate" &&
                                "Already indexed"}
                              {item.status === "failed" && "Failed"}
                            </span>
                            {item.status === "failed" &&
                              uploadStep === "ready" && (
                                <button
                                  className="file-retry"
                                  type="button"
                                  onClick={() => void uploadDocuments([item])}
                                >
                                  <RotateCcw size={12} />
                                  Retry
                                </button>
                              )}
                          </div>
                          {item.status === "uploading" && (
                            <div
                              className="file-progress"
                              role="progressbar"
                              aria-label={`Uploading ${item.file.name}`}
                              aria-valuemin={0}
                              aria-valuemax={100}
                              aria-valuenow={item.progress}
                            >
                              <span style={{ width: `${item.progress}%` }} />
                            </div>
                          )}
                          {item.status === "failed" && item.error && (
                            <p className="file-error">{item.error}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {uploadFeedback && (
                  <p className="upload-success">
                    <Check size={15} />
                    {uploadFeedback}
                  </p>
                )}
                {uploadError && <p className="modal-error">{uploadError}</p>}

                <button
                  className="primary-button full-button"
                  type="button"
                  onClick={() => void uploadDocuments()}
                  disabled={
                    uploadStep === "uploading" ||
                    readyUploadCount === 0
                  }
                >
                  {uploadStep === "uploading" ? (
                    <LoaderCircle className="spin" size={16} />
                  ) : (
                    <FileUp size={16} />
                  )}
                  {uploadStep === "uploading"
                    ? "Uploading and indexing…"
                    : readyUploadCount > 0
                      ? `Upload ${readyUploadCount} document${
                          readyUploadCount === 1 ? "" : "s"
                        }`
                      : "All documents processed"}
                </button>
              </div>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
