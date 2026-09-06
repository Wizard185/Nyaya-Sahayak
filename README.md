# Nyaya Sahayak (न्याय सहायक)

A multi-tenant, RAG-based, multilingual Indian Legal AI Assistant. Users sign
up with email/password, chat with an AI grounded in IPC/CrPC/Constitution
citations, generate court-ready drafts (bail applications, affidavits, etc.)
from predefined templates, and download them as Word or PDF — with full
per-user chat and drafting history.

The LLM (Ollama) runs entirely on your own machine. Vector search (Pinecone)
and Hindi/Kannada translation (Google Translate) are the only external
network calls — everything else, including all user data, stays local.

## Architecture

```
Browser (React + Vite + Tailwind, :5173)
   │  axios → :8000, credentials via JWT bearer token
   ▼
FastAPI backend (:8000)
   ├─ auth/            — signup/login/profile, bcrypt + JWT
   ├─ chats/            — multi-tenant chat CRUD + message posting (run_qa)
   ├─ qa/service.py     — translate-in → hybrid retrieval → Ollama → translate-out,
   │                      each step wrapped in its own timeout + specific error
   ├─ drafts/           — template search, draft creation, docx/pdf download, history
   ├─ document_gen/     — docxtpl template rendering
   ├─ rag/               — BGE-M3 embeddings, Pinecone (dense) + BM25 (sparse), RRF fusion
   ├─ llm/               — Ollama chain (Q&A) + single-call narrative polish (drafting)
   ├─ multilingual/      — langdetect + deep-translator (Google Translate)
   ├─ guided/            — YAML decision-tree walker
   ├─ admin/             — dev-only ingestion routes, never linked from the frontend
   └─ db/mongo.py        — Motor async client: users / chats / messages / drafts
   ▼
MongoDB (local)           Pinecone (cloud)           Ollama (local)
```

Backend and frontend run as two independent servers and talk over CORS —
this is intentional so each can be deployed/restarted separately.

## Prerequisites (Windows)

1. **Python 3.10+** — https://www.python.org/downloads/ (check "Add to PATH" during install)
2. **Node.js 18+** — https://nodejs.org
3. **Ollama** — https://ollama.com/download/windows, then in a terminal:
   ```
   ollama serve
   ollama pull llama3.2:3b
   ```
   A smaller model (`llama3.2:3b`) is the default because most Windows
   laptops run Ollama on CPU — a full 8B model is usually too slow for a
   5-second response target. You can switch to a bigger model later by
   changing `OLLAMA_MODEL` in `backend/.env` if your machine is fast enough.
4. **MongoDB Community Server** — https://www.mongodb.com/try/download/community
   Install as a Windows service (default installer option) so it starts
   automatically; it will be listening on `mongodb://localhost:27017`.
5. **A Pinecone account + API key** — https://www.pinecone.io (free tier is
   enough for the demo corpus). Create an API key from the Pinecone console.

## Setup

**1. Backend**
```
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```
Edit `backend/.env` and set:
- `PINECONE_API_KEY` — from your Pinecone account
- `JWT_SECRET_KEY` — any long random string (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`)
- `ADMIN_API_KEY` — any random string, used only for the dev-only ingestion routes below

Then, one-time, ingest the seed legal corpus into Pinecone + build the local BM25 index:
```
python corpus\ingest.py
```

Start the backend:
```
uvicorn main:app --reload --port 8000
```

**2. Frontend**
```
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**, sign up for an account, and start chatting.

## Verifying it works

- `GET http://localhost:8000/api/health` should report `ollama: true`,
  `pinecone: true`, and `mongodb: true`.
- Sign up → log in → start a new chat → ask "What is Section 498A IPC?" —
  you should get a grounded answer citing IPC 498A within a few seconds,
  with citation cards and a hallucination-check badge.
- Open **Document Drafter**, search "bail", fill in the fields, generate,
  and download both Word and PDF — then revisit **My Drafts** and
  re-download the same file without regenerating it.

## Adding your own document templates

Two placeholder templates ship in `backend/corpus/templates/` (Bail
Application, Affidavit) as a starting point. To add a real template:

1. Add an entry to `backend/corpus/templates/manifest.json` with an `id`,
   `name`, `aliases` (for search), `description`, `docx_template` filename,
   and a `fields` list (each with `key`, `label`, `type`, and optionally
   `narrative: true` for free-text fields that should get an LLM polish pass).
2. Author a `.docx` file with the same field `key`s as Jinja2 `{{ field_key }}`
   placeholders (using [docxtpl](https://docxtpl.readthedocs.io/) syntax),
   and save it under `backend/corpus/templates/` with the filename referenced
   above.

No code changes needed — the drafter reads the manifest at request time.

## Adding your own legal corpus (IPC/Constitution/other statutes)

Replace or extend `backend/corpus/sample_ipc.json` (array of
`{ section_id, act, title, text }` objects), then either:
- re-run `python corpus/ingest.py`, or
- call the dev-only `POST /admin/ingest/corpus` route with an
  `X-Admin-Key` header matching `ADMIN_API_KEY` in `.env` (this route is
  never called from the frontend — it's for you, the developer, to
  re-index without restarting the server).

## Project structure

```
nyaya-sahayak/
├── backend/     FastAPI app: auth, multi-tenant chats/drafts, RAG pipeline,
│                Ollama LLM calls, translation, guided decision trees,
│                template-driven document generation, admin ingestion routes
└── frontend/    React 18 + Vite + Tailwind UI
```

See `backend/main.py` for the full list of registered routes.

## Known limitations

- This is a reference legal assistant, not legal advice — the UI and
  prompts say so; please keep it that way if you extend the app.
- Requires outbound internet access for Pinecone (vector search) and
  Google Translate (Hindi/Kannada translation) even though the LLM itself
  runs fully offline via Ollama.
- PDF download converts the generated `.docx` on demand and requires
  Microsoft Word to be installed on the machine running the backend
  (`docx2pdf` automates Word). Word/docx download always works regardless.
- The BGE-M3 embedding model (~2 GB) and your chosen Ollama model are
  downloaded on first use — expect the first corpus ingest and first
  `ollama pull` to take a while depending on your connection.
