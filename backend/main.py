"""
Nyaya Sahayak backend — FastAPI application wiring auth, multi-tenant chats,
the template-driven document drafter, guided scenarios, and admin-only
ingestion routes together.
"""
import os
from typing import List, Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from admin.routes import router as admin_router  # noqa: E402
from auth.routes import router as auth_router  # noqa: E402
from chats.routes import router as chats_router  # noqa: E402
from db.mongo import ping as mongo_ping  # noqa: E402
from drafts.routes import router as drafts_router  # noqa: E402
from guided.engine import get_engine  # noqa: E402
from multilingual.translator import detect_language  # noqa: E402
from rag.retriever import get_retriever  # noqa: E402

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")]

app = FastAPI(title="Nyaya Sahayak API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(chats_router)
app.include_router(drafts_router)
app.include_router(admin_router)


# ---------------------------------------------------------------------------
# Guided scenario endpoints
# ---------------------------------------------------------------------------

class GuidedStartRequest(BaseModel):
    scenario: str


class GuidedStepResponse(BaseModel):
    step_id: str
    question: Optional[str]
    options: List[str]
    progress: int
    result: Optional[str] = None


class GuidedNextRequest(BaseModel):
    step_id: str
    answer: str
    scenario: str


class ScenarioInfo(BaseModel):
    id: str
    title: str
    description: str
    icon: str


class ScenariosResponse(BaseModel):
    scenarios: List[ScenarioInfo]


class DetectResponse(BaseModel):
    detected_language: str


class HealthResponse(BaseModel):
    status: str
    ollama: bool
    pinecone: bool
    mongodb: bool


@app.post("/api/guided/start", response_model=GuidedStepResponse)
def guided_start(req: GuidedStartRequest):
    engine = get_engine()
    try:
        step = engine.start_scenario(req.scenario)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return GuidedStepResponse(**step)


@app.post("/api/guided/next", response_model=GuidedStepResponse)
def guided_next(req: GuidedNextRequest):
    engine = get_engine()
    try:
        step = engine.process_answer(req.scenario, req.step_id, req.answer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return GuidedStepResponse(**step)


@app.get("/api/scenarios", response_model=ScenariosResponse)
def scenarios():
    engine = get_engine()
    return ScenariosResponse(scenarios=[ScenarioInfo(**s) for s in engine.list_scenarios()])


# ---------------------------------------------------------------------------
# Utility endpoints
# ---------------------------------------------------------------------------

@app.get("/api/detect", response_model=DetectResponse)
def detect(text: str = ""):
    return DetectResponse(detected_language=detect_language(text))


@app.get("/api/health", response_model=HealthResponse)
async def health():
    ollama_ok = False
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        ollama_ok = resp.status_code == 200
    except Exception:
        ollama_ok = False

    pinecone_ok = False
    try:
        retriever = get_retriever()
        retriever.pinecone_index.describe_index_stats()
        pinecone_ok = True
    except Exception:
        pinecone_ok = False

    mongodb_ok = await mongo_ping()

    return HealthResponse(status="ok", ollama=ollama_ok, pinecone=pinecone_ok, mongodb=mongodb_ok)
