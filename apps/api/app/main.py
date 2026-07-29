from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from .chat import ChatService
from .config import GROQ_MODELS, get_settings
from .database import Database
from .ingestion import IngestionService
from .providers.groq import GroqProvider
from .retrieval import RetrievalService
from .schemas import ChatDetail, ChatRequest, ChatSummary, DocumentRecord, IndexResult
from .vector_store import VectorStore

settings = get_settings()
database = Database(settings.sqlite_path)
vector_store = VectorStore(settings.chroma_path, settings.collection_name)
ingestion = IngestionService(settings.docs_dir, database, vector_store)
retrieval = RetrievalService(
    vector_store=vector_store,
    candidate_k=settings.retrieval_candidate_k,
    top_k=settings.retrieval_top_k,
    minimum_relevance=settings.minimum_relevance,
)
provider = GroqProvider(
    api_key=settings.groq_api_key.get_secret_value() if settings.groq_api_key else None,
    model=settings.groq_model,
)
chat_service = ChatService(retrieval, provider, database)


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.initialize()
    yield


app = FastAPI(
    title="Heritage RAG API",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_origin,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "provider": "groq",
        "model": settings.groq_model,
        "models": GROQ_MODELS,
        "retrieval_modes": [
            {
                "id": "quick",
                "label": "Quick",
                "description": "3 chunks · fastest",
            },
            {
                "id": "medium",
                "label": "Medium",
                "description": "7 chunks · balanced",
            },
            {
                "id": "deep",
                "label": "Deep",
                "description": "15 chunks · thorough",
            },
        ],
        "documents": len(database.list_documents()),
        "chunks": vector_store.count,
        "api_key_configured": bool(settings.groq_api_key),
    }


@app.post("/api/documents/reindex", response_model=IndexResult)
def reindex() -> IndexResult:
    return ingestion.index_all()


@app.get("/api/documents", response_model=list[DocumentRecord])
def documents() -> list[dict]:
    return database.list_documents()


@app.get("/api/documents/{document_id}/content")
def document_content(document_id: str) -> FileResponse:
    matches = [document for document in database.list_documents() if document["id"] == document_id]
    if not matches:
        raise HTTPException(status_code=404, detail="Document not found")
    candidate = (settings.docs_dir / matches[0]["relative_path"]).resolve()
    try:
        candidate.relative_to(settings.docs_dir.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid document path") from exc
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Source file is unavailable")
    return FileResponse(
        path=Path(candidate),
        filename=matches[0]["file_name"],
        content_disposition_type="inline",
    )


@app.get("/api/chats", response_model=list[ChatSummary])
def chats() -> list[dict]:
    return database.list_chats()


@app.get("/api/chats/{chat_id}", response_model=ChatDetail)
def chat_detail(chat_id: str) -> dict:
    chat = database.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return chat


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        chat_service.stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
