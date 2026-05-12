import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from .chat import ChatService
from .config import get_settings
from .database import Database
from .ingestion import IngestionService
from .observability import configure_logging, log_event
from .providers.gemini import GeminiProvider
from .providers.groq import GroqProvider
from .providers.openai import OpenAIProvider
from .providers.router import ProviderRouter
from .retrieval import RetrievalService
from .schemas import (
    AppLoginRequest,
    AppSessionStatus,
    ChatDetail,
    ChatRequest,
    ChatSummary,
    ChatUpdate,
    DocumentRecord,
    IndexResult,
    UploadSessionStatus,
    UploadUnlockRequest,
)
from .upload_auth import InvalidUploadPassword, UploadAccess, UploadRateLimited
from .uploads import DocumentUploadService
from .vector_store import VectorStore

UPLOAD_SESSION_COOKIE = "heritage_upload_session"
APP_SESSION_COOKIE = "heritage_app_session"
PUBLIC_API_PATHS = {
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/session",
}
settings = get_settings()
logger = configure_logging(settings.log_path, settings.log_level)
database = Database(settings.sqlite_path)
vector_store = VectorStore(settings.chroma_path, settings.collection_name)
ingestion = IngestionService(settings.docs_dir, database, vector_store)
retrieval = RetrievalService(
    vector_store=vector_store,
    candidate_k=settings.retrieval_candidate_k,
    top_k=settings.retrieval_top_k,
    minimum_relevance=settings.minimum_relevance,
)
provider = ProviderRouter(
    groq=GroqProvider(
        api_key=settings.groq_api_key.get_secret_value() if settings.groq_api_key else None,
        model=settings.groq_model,
    ),
    openai=OpenAIProvider(
        api_key=(settings.openai_api_key.get_secret_value() if settings.openai_api_key else None),
    ),
    gemini=GeminiProvider(
        api_key=(settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None),
    ),
    default_model=settings.groq_model,
)
chat_service = ChatService(retrieval, provider, database)
upload_access = UploadAccess(
    password_hash=settings.upload_password_hash.get_secret_value(),
    session_ttl_seconds=settings.upload_session_ttl_seconds,
    max_attempts=settings.upload_max_attempts,
    attempt_window_seconds=settings.upload_attempt_window_seconds,
)
app_access = UploadAccess(
    password_hash=settings.upload_password_hash.get_secret_value(),
    session_ttl_seconds=settings.app_session_ttl_seconds,
    max_attempts=settings.upload_max_attempts,
    attempt_window_seconds=settings.upload_attempt_window_seconds,
)
document_uploads = DocumentUploadService(
    docs_dir=settings.docs_dir,
    database=database,
    vector_store=vector_store,
    ingestion=ingestion,
    max_file_bytes=settings.upload_max_file_bytes,
)


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


@app.middleware("http")
async def require_app_session(request: Request, call_next):
    if (
        request.method != "OPTIONS"
        and request.url.path.startswith("/api/")
        and request.url.path not in PUBLIC_API_PATHS
        and not app_access.is_unlocked(request.cookies.get(APP_SESSION_COOKIE))
    ):
        return JSONResponse(
            status_code=401,
            content={"detail": "Enter the Heritage password to continue."},
        )
    return await call_next(request)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = request.headers.get("x-request-id", "")
    if not request_id or len(request_id) > 100 or not request_id.replace("-", "").isalnum():
        request_id = uuid.uuid4().hex
    request.state.request_id = request_id
    started = perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        log_event(
            logger,
            "http.request.completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            latency_ms=round((perf_counter() - started) * 1000, 2),
        )


@app.post("/api/auth/login", response_model=AppSessionStatus)
def login(
    login_request: AppLoginRequest,
    request: Request,
    response: Response,
) -> dict:
    client_key = request.client.host if request.client else "local"
    try:
        token = app_access.unlock(login_request.password, client_key)
    except InvalidUploadPassword as exc:
        raise HTTPException(status_code=401, detail="The password is incorrect.") from exc
    except UploadRateLimited as exc:
        raise HTTPException(
            status_code=429,
            detail="Login is temporarily unavailable. Try again later.",
        ) from exc
    response.set_cookie(
        key=APP_SESSION_COOKIE,
        value=token,
        max_age=settings.app_session_ttl_seconds,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/api",
    )
    return {
        "authenticated": True,
        "expires_in_seconds": settings.app_session_ttl_seconds,
    }


@app.get("/api/auth/session", response_model=AppSessionStatus)
def app_session(request: Request) -> dict:
    authenticated = app_access.is_unlocked(
        request.cookies.get(APP_SESSION_COOKIE)
    )
    return {
        "authenticated": authenticated,
        "expires_in_seconds": (
            settings.app_session_ttl_seconds if authenticated else None
        ),
    }


@app.post("/api/auth/logout", status_code=204)
def logout(response: Response) -> Response:
    response.delete_cookie(
        key=APP_SESSION_COOKIE,
        path="/api",
        httponly=True,
        samesite="lax",
    )
    response.status_code = 204
    return response


@app.get("/api/health")
async def health(refresh: bool = False) -> dict:
    providers = await provider.health(refresh=refresh)
    models = provider.models_with_status()
    indexed_documents = database.list_documents()
    available_models = [model for model in models if model["available"]]
    default_model = (
        settings.groq_model
        if any(model["id"] == settings.groq_model for model in available_models)
        else (available_models[0]["id"] if available_models else settings.groq_model)
    )
    return {
        "status": "ok",
        "provider": "multi",
        "model": default_model,
        "models": models,
        "providers": providers,
        "retrieval_modes": [
            {
                "id": "quick",
                "label": "Quick",
                "description": "3 chunks · vector search",
            },
            {
                "id": "medium",
                "label": "Medium",
                "description": "7 chunks · hybrid ranking",
            },
            {
                "id": "deep",
                "label": "Deep",
                "description": "15 chunks · query expansion + full re-rank",
            },
        ],
        "documents": len(indexed_documents),
        "pages": sum(
            int(document["page_count"] or 0)
            for document in indexed_documents
        ),
        "chunks": vector_store.count,
        "api_key_configured": any(item["configured"] for item in providers),
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


@app.patch("/api/chats/{chat_id}", response_model=ChatSummary)
def update_chat(chat_id: str, update: ChatUpdate) -> dict:
    if update.title is None and update.pinned is None:
        raise HTTPException(status_code=400, detail="No chat changes supplied")
    if update.title is not None and not database.rename_chat(chat_id, update.title):
        raise HTTPException(status_code=404, detail="Conversation not found")
    if update.pinned is not None and not database.set_chat_pinned(chat_id, update.pinned):
        raise HTTPException(status_code=404, detail="Conversation not found")
    chat = database.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {key: value for key, value in chat.items() if key != "messages"}


@app.delete("/api/chats/{chat_id}", status_code=204)
def delete_chat(chat_id: str) -> Response:
    if not database.delete_chat(chat_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return Response(status_code=204)


@app.post("/api/uploads/unlock", response_model=UploadSessionStatus)
def unlock_uploads(
    unlock_request: UploadUnlockRequest,
    request: Request,
    response: Response,
) -> dict:
    client_key = request.client.host if request.client else "local"
    try:
        token = upload_access.unlock(unlock_request.password, client_key)
    except InvalidUploadPassword as exc:
        raise HTTPException(status_code=401, detail="The upload password is incorrect.") from exc
    except UploadRateLimited as exc:
        raise HTTPException(
            status_code=429,
            detail="Upload access is temporarily unavailable. Try again later.",
        ) from exc
    response.set_cookie(
        key=UPLOAD_SESSION_COOKIE,
        value=token,
        max_age=settings.upload_session_ttl_seconds,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/api",
    )
    return {
        "unlocked": True,
        "expires_in_seconds": settings.upload_session_ttl_seconds,
    }


@app.get("/api/uploads/session", response_model=UploadSessionStatus)
def upload_session(request: Request) -> dict:
    unlocked = (
        app_access.is_unlocked(request.cookies.get(APP_SESSION_COOKIE))
        or upload_access.is_unlocked(request.cookies.get(UPLOAD_SESSION_COOKIE))
    )
    return {
        "unlocked": unlocked,
        "expires_in_seconds": settings.upload_session_ttl_seconds if unlocked else None,
    }


@app.post("/api/documents/upload", response_model=IndexResult)
async def upload_documents(
    request: Request,
    files: list[UploadFile] = File(...),
) -> IndexResult:
    if not (
        app_access.is_unlocked(request.cookies.get(APP_SESSION_COOKIE))
        or upload_access.is_unlocked(request.cookies.get(UPLOAD_SESSION_COOKIE))
    ):
        raise HTTPException(status_code=401, detail="Unlock document uploads first.")
    return await document_uploads.upload(files)


@app.post("/api/chat/stream")
async def chat_stream(chat_request: ChatRequest, request: Request) -> StreamingResponse:
    return StreamingResponse(
        chat_service.stream(
            chat_request,
            request_id=getattr(request.state, "request_id", None),
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
