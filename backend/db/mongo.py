"""
Motor (async MongoDB driver) client + collection accessors.

All app data (users, chats, messages, drafts) lives in a single local
MongoDB database — no cloud account needed, matches the "run everything on
my own laptop next to Ollama" deployment target.
"""
import os
from typing import Optional

import certifi
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "nyaya_sahayak")

_client: Optional[AsyncIOMotorClient] = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        # mongodb+srv:// (Atlas) connections are TLS. macOS python.org builds
        # don't ship a system CA bundle, so SSL verification fails unless we
        # point it at certifi's bundle explicitly — this makes it work in
        # every terminal/shell regardless of SSL_CERT_FILE being set.
        kwargs = {"serverSelectionTimeoutMS": 5000}
        if MONGO_URL.startswith("mongodb+srv://"):
            kwargs["tlsCAFile"] = certifi.where()
        _client = AsyncIOMotorClient(MONGO_URL, **kwargs)
    return _client


def get_db():
    return get_client()[MONGO_DB_NAME]


def users_collection():
    return get_db()["users"]


def chats_collection():
    return get_db()["chats"]


def messages_collection():
    return get_db()["messages"]


def drafts_collection():
    return get_db()["drafts"]


async def ping() -> bool:
    try:
        await get_client().admin.command("ping")
        return True
    except Exception:
        return False
