"""FastAPI API routes."""
import os
import shutil
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage

from app.core.config import settings
from app.services.ingestion import ingest_pdf, list_documents
from app.services.agent import run_agent
from app.services.evaluation import evaluate_rag

router = APIRouter()

# ── In-memory conversation history (keyed by session_id) ─────────────────────
_sessions: dict[str, list] = {}


# ─── Schemas ──────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    session_id: str = "default"
    query: str
    filename_filter: str | None = None

class ChatResponse(BaseModel):
    answer: str
    sources: List[dict]
    route_used: str
    session_id: str

class EvalRequest(BaseModel):
    questions: List[str]
    answers: List[str]
    contexts: List[List[str]]
    ground_truths: List[str] | None = None


# ─── Upload PDF ───────────────────────────────────────────────────────────────
@router.post("/upload", summary="Upload and ingest a PDF")
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    save_path = os.path.join(settings.UPLOAD_DIR, file.filename)

    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Run ingestion in background so upload returns fast
    def do_ingest():
        ingest_pdf(save_path, file.filename)

    background_tasks.add_task(do_ingest)

    return {"message": f"'{file.filename}' uploaded. Ingestion started in background."}


# ─── List documents ───────────────────────────────────────────────────────────
@router.get("/documents", summary="List all ingested documents")
async def get_documents():
    return {"documents": list_documents()}


# ─── Chat ─────────────────────────────────────────────────────────────────────
@router.post("/chat", response_model=ChatResponse, summary="Chat with the agent")
async def chat(req: ChatRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    history = _sessions.get(req.session_id, [])

    result = await run_agent(
        query=req.query,
        history=history,
        filename_filter=req.filename_filter,
    )

    # Persist updated history
    history = history + [
        HumanMessage(content=req.query),
        AIMessage(content=result["answer"]),
    ]
    _sessions[req.session_id] = history[-20:]   # keep last 20 messages

    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        route_used=result["route_used"],
        session_id=req.session_id,
    )


# ─── Clear session ────────────────────────────────────────────────────────────
@router.delete("/session/{session_id}", summary="Clear conversation history")
async def clear_session(session_id: str):
    _sessions.pop(session_id, None)
    return {"message": f"Session '{session_id}' cleared."}


# ─── RAGAS Evaluation ─────────────────────────────────────────────────────────
@router.post("/evaluate", summary="Run RAGAS evaluation on RAG outputs")
async def evaluate(req: EvalRequest):
    results = evaluate_rag(
        questions=req.questions,
        answers=req.answers,
        contexts=req.contexts,
        ground_truths=req.ground_truths,
    )
    return {"ragas_scores": results}


# ─── Health check ─────────────────────────────────────────────────────────────
@router.get("/health")
async def health():
    return {"status": "ok", "model": settings.OLLAMA_MODEL}
