"""
Multi-tenant chat routes. Every chat and message is scoped by user_id and
ownership is checked on every read/write — chats are never visible across
accounts.
"""
from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth.security import get_current_user
from db.mongo import chats_collection, messages_collection
from qa.service import run_qa

router = APIRouter(prefix="/api/chats", tags=["chats"])


class ChatSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    citations: List[dict] = []
    hallucination_flags: List[str] = []
    detected_language: str = "en"
    # "answer", or "clarification" when the assistant asked follow-up
    # questions instead of answering.
    kind: str = "answer"
    created_at: datetime


class ChatDetail(ChatSummary):
    messages: List[MessageOut] = []


class RenameChatRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class PostMessageRequest(BaseModel):
    query: str = Field(min_length=1)
    language: str = "auto"


def _oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Chat not found.")


def _chat_summary(doc: dict) -> ChatSummary:
    return ChatSummary(
        id=str(doc["_id"]),
        title=doc["title"],
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


def _message_out(doc: dict) -> MessageOut:
    return MessageOut(
        id=str(doc["_id"]),
        role=doc["role"],
        content=doc["content"],
        citations=doc.get("citations", []),
        hallucination_flags=doc.get("hallucination_flags", []),
        detected_language=doc.get("detected_language", "en"),
        kind=doc.get("kind", "answer"),
        created_at=doc["created_at"],
    )


async def _get_owned_chat(chat_id: str, user: dict) -> dict:
    chat = await chats_collection().find_one({"_id": _oid(chat_id), "user_id": user["_id"]})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found.")
    return chat


@router.post("", response_model=ChatSummary)
async def create_chat(user: dict = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    doc = {"user_id": user["_id"], "title": "New Chat", "created_at": now, "updated_at": now}
    result = await chats_collection().insert_one(doc)
    doc["_id"] = result.inserted_id
    return _chat_summary(doc)


@router.get("", response_model=List[ChatSummary])
async def list_chats(user: dict = Depends(get_current_user)):
    cursor = chats_collection().find({"user_id": user["_id"]}).sort("updated_at", -1)
    return [_chat_summary(doc) async for doc in cursor]


@router.get("/{chat_id}", response_model=ChatDetail)
async def get_chat(chat_id: str, user: dict = Depends(get_current_user)):
    chat = await _get_owned_chat(chat_id, user)
    cursor = messages_collection().find({"chat_id": chat["_id"]}).sort("created_at", 1)
    msgs = [_message_out(doc) async for doc in cursor]
    return ChatDetail(**_chat_summary(chat).model_dump(), messages=msgs)


@router.patch("/{chat_id}", response_model=ChatSummary)
async def rename_chat(chat_id: str, req: RenameChatRequest, user: dict = Depends(get_current_user)):
    chat = await _get_owned_chat(chat_id, user)
    await chats_collection().update_one(
        {"_id": chat["_id"]}, {"$set": {"title": req.title.strip(), "updated_at": datetime.now(timezone.utc)}}
    )
    chat["title"] = req.title.strip()
    return _chat_summary(chat)


@router.delete("/{chat_id}")
async def delete_chat(chat_id: str, user: dict = Depends(get_current_user)):
    chat = await _get_owned_chat(chat_id, user)
    await messages_collection().delete_many({"chat_id": chat["_id"]})
    await chats_collection().delete_one({"_id": chat["_id"]})
    return {"status": "ok"}


@router.post("/{chat_id}/messages", response_model=MessageOut)
async def post_message(chat_id: str, req: PostMessageRequest, user: dict = Depends(get_current_user)):
    chat = await _get_owned_chat(chat_id, user)
    now = datetime.now(timezone.utc)

    # Recent messages, oldest first, so the model can ask follow-up
    # questions and then use the user's replies. content_en is the English
    # text the model actually saw/wrote (older messages predate it).
    cursor = messages_collection().find({"chat_id": chat["_id"]}).sort("created_at", -1).limit(10)
    history = [
        {
            "role": doc["role"],
            "content": doc.get("content_en", doc["content"]),
            "kind": doc.get("kind", "answer"),
        }
        async for doc in cursor
    ][::-1]

    user_msg = {
        "chat_id": chat["_id"],
        "user_id": user["_id"],
        "role": "user",
        "content": req.query,
        "citations": [],
        "hallucination_flags": [],
        "detected_language": "en",
        "created_at": now,
    }
    user_insert = await messages_collection().insert_one(user_msg)

    result = await run_qa(req.query, req.language, history)

    await messages_collection().update_one(
        {"_id": user_insert.inserted_id}, {"$set": {"content_en": result["query_en"]}}
    )

    assistant_msg = {
        "chat_id": chat["_id"],
        "user_id": user["_id"],
        "role": "assistant",
        "content": result["answer"],
        "content_en": result["answer_en"],
        "kind": result["kind"],
        "citations": result["citations"],
        "hallucination_flags": result["hallucination_flags"],
        "detected_language": result["detected_language"],
        "created_at": datetime.now(timezone.utc),
    }
    insert_result = await messages_collection().insert_one(assistant_msg)
    assistant_msg["_id"] = insert_result.inserted_id

    update_fields = {"updated_at": datetime.now(timezone.utc)}
    if chat["title"] == "New Chat":
        update_fields["title"] = req.query.strip()[:60]
    await chats_collection().update_one({"_id": chat["_id"]}, {"$set": update_fields})

    return _message_out(assistant_msg)
