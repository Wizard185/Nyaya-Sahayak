"""
Template-driven document drafter: search templates -> fill fields ->
render .docx (+ optional single LLM polish per narrative field) ->
download as .docx or .pdf -> persisted history so a user can re-download
without re-generating.
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from auth.security import get_current_user
from db.mongo import drafts_collection
from document_gen.template_engine import find_template, render_template, search_templates
from llm.drafting import polish_narrative
router = APIRouter(prefix="/api", tags=["drafts"])

DRAFT_OUTPUT_PATH = os.getenv("DRAFT_OUTPUT_PATH", "/tmp/nyaya_drafts")
# Per narrative field. Kept well under the frontend's request timeout: on a
# slow CPU-only Ollama a long polish would otherwise fail the whole draft,
# so past this the user's own wording is used instead.
DRAFT_POLISH_TIMEOUT_SECONDS = float(os.getenv("DRAFT_POLISH_TIMEOUT_SECONDS", "120"))


class TemplateSummary(BaseModel):
    id: str
    name: str
    description: str


class TemplateField(BaseModel):
    key: str
    label: str
    type: str
    placeholder: Optional[str] = None
    narrative: bool = False


class TemplateDetail(TemplateSummary):
    fields: List[TemplateField]


class CreateDraftRequest(BaseModel):
    template_id: str
    field_values: Dict[str, str]


class DraftSummary(BaseModel):
    id: str
    template_id: str
    template_name: str
    created_at: datetime


def _template_summary(t: dict) -> TemplateSummary:
    return TemplateSummary(id=t["id"], name=t["name"], description=t.get("description", ""))


def _draft_summary(doc: dict) -> DraftSummary:
    return DraftSummary(
        id=str(doc["_id"]),
        template_id=doc["template_id"],
        template_name=doc["template_name"],
        created_at=doc["created_at"],
    )


def _oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Draft not found.")


@router.get("/templates", response_model=List[TemplateSummary])
def list_templates(query: str = ""):
    return [_template_summary(t) for t in search_templates(query)]


@router.get("/templates/{template_id}", response_model=TemplateDetail)
def get_template(template_id: str):
    try:
        t = find_template(template_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Template not found.")
    return TemplateDetail(**_template_summary(t).model_dump(), fields=[TemplateField(**f) for f in t["fields"]])


@router.post("/drafts", response_model=DraftSummary)
async def create_draft(req: CreateDraftRequest, user: dict = Depends(get_current_user)):
    try:
        template = find_template(req.template_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Template not found.")

    field_values = dict(req.field_values)
    for field in template["fields"]:
        if field.get("narrative") and field_values.get(field["key"], "").strip():
            try:
                field_values[field["key"]] = await asyncio.wait_for(
                    asyncio.to_thread(polish_narrative, field_values[field["key"]], field["label"]),
                    timeout=DRAFT_POLISH_TIMEOUT_SECONDS,
                )
            except Exception:
                # Fall back to the user's original wording if the LLM polish
                # step fails or times out — never block drafting on it.
                pass

    draft_id = ObjectId()
    output_dir = os.path.join(DRAFT_OUTPUT_PATH, str(user["_id"]))
    output_path = os.path.join(output_dir, f"{draft_id}.docx")

    try:
        render_template(req.template_id, field_values, output_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to render document: {e}")

    now = datetime.now(timezone.utc)
    doc = {
        "_id": draft_id,
        "user_id": user["_id"],
        "template_id": template["id"],
        "template_name": template["name"],
        "field_values": field_values,
        "docx_path": output_path,
        "created_at": now,
    }
    await drafts_collection().insert_one(doc)
    return _draft_summary(doc)


@router.get("/drafts", response_model=List[DraftSummary])
async def list_drafts(user: dict = Depends(get_current_user)):
    cursor = drafts_collection().find({"user_id": user["_id"]}).sort("created_at", -1)
    return [_draft_summary(doc) async for doc in cursor]


async def _get_owned_draft(draft_id: str, user: dict) -> dict:
    doc = await drafts_collection().find_one({"_id": _oid(draft_id), "user_id": user["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Draft not found.")
    return doc


@router.get("/drafts/{draft_id}/download")
async def download_draft(draft_id: str, format: str = "docx", user: dict = Depends(get_current_user)):
    doc = await _get_owned_draft(draft_id, user)
    docx_path = doc["docx_path"]

    if not os.path.isfile(docx_path):
        raise HTTPException(status_code=404, detail="The generated file is missing on disk.")

    if format == "docx":
        return FileResponse(
            docx_path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=f"{doc['template_name'].replace(' ', '_')}.docx",
        )

    if format == "pdf":
        pdf_path = docx_path[:-5] + ".pdf"
        if not os.path.isfile(pdf_path):
            try:
                from docx2pdf import convert

                await asyncio.to_thread(convert, docx_path, pdf_path)
            except Exception as e:
                raise HTTPException(
                    status_code=503,
                    detail=f"PDF conversion failed. This requires Microsoft Word to be installed on this machine. ({e})",
                )
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=f"{doc['template_name'].replace(' ', '_')}.pdf",
        )

    raise HTTPException(status_code=400, detail="format must be 'docx' or 'pdf'.")
