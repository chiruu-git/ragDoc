"""Core logic for the local RAG app.

Storage (SQLite), document parsing, chunking, the Ollama client and retrieval.
Nothing in here imports Streamlit, so it can be tested on its own.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Optional

import numpy as np
import requests

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

DATA_DIR = Path(os.environ.get("RAG_DATA_DIR", Path(__file__).parent / "data"))
DB_PATH = DATA_DIR / "rag.db"

EMBED_HINTS = ("embed", "nomic", "bge", "minilm", "mxbai", "arctic")


def base_url() -> str:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").strip()
    if not host.startswith(("http://", "https://")):
        host = "http://" + host
    return host.rstrip("/")


def is_embed_model(name: str) -> bool:
    n = name.lower()
    return any(h in n for h in EMBED_HINTS)


# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    sha         TEXT NOT NULL UNIQUE,
    kind        TEXT NOT NULL,
    n_chunks    INTEGER NOT NULL,
    embed_model TEXT NOT NULL,
    enabled     INTEGER NOT NULL DEFAULT 1,
    added_at    REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    idx     INTEGER NOT NULL,
    page    INTEGER,
    text    TEXT NOT NULL,
    emb     BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
CREATE TABLE IF NOT EXISTS chats (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id    INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    mode       TEXT NOT NULL DEFAULT 'general',
    sources    TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id);
"""


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


# ---- chats ----------------------------------------------------------------- #

def create_chat(conn: sqlite3.Connection, title: str) -> int:
    now = time.time()
    with conn:
        cur = conn.execute(
            "INSERT INTO chats(title, created_at, updated_at) VALUES (?,?,?)",
            (title.strip() or "New chat", now, now),
        )
    return int(cur.lastrowid)


def list_chats(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM chats ORDER BY updated_at DESC").fetchall()


def delete_chat(conn: sqlite3.Connection, chat_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM chats WHERE id=?", (chat_id,))


def add_message(
    conn: sqlite3.Connection,
    chat_id: int,
    role: str,
    content: str,
    mode: str,
    sources: Optional[list[dict]] = None,
) -> None:
    now = time.time()
    with conn:
        conn.execute(
            "INSERT INTO messages(chat_id, role, content, mode, sources, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (chat_id, role, content, mode, json.dumps(sources) if sources else None, now),
        )
        conn.execute("UPDATE chats SET updated_at=? WHERE id=?", (now, chat_id))


def get_messages(conn: sqlite3.Connection, chat_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT role, content, mode, sources FROM messages WHERE chat_id=? ORDER BY id",
        (chat_id,),
    ).fetchall()
    out = []
    for r in rows:
        out.append(
            {
                "role": r["role"],
                "content": r["content"],
                "mode": r["mode"],
                "sources": json.loads(r["sources"]) if r["sources"] else [],
            }
        )
    return out


# ---- documents ------------------------------------------------------------- #

def list_documents(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM documents ORDER BY added_at DESC").fetchall()


def set_document_enabled(conn: sqlite3.Connection, doc_id: int, enabled: bool) -> None:
    with conn:
        conn.execute("UPDATE documents SET enabled=? WHERE id=?", (int(enabled), doc_id))


def delete_document(conn: sqlite3.Connection, doc_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))


def count_active_chunks(conn: sqlite3.Connection, embed_model: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM chunks c JOIN documents d ON d.id=c.doc_id "
        "WHERE d.enabled=1 AND d.embed_model=?",
        (embed_model,),
    ).fetchone()
    return int(row["n"])


# --------------------------------------------------------------------------- #
# Parsing + chunking
# --------------------------------------------------------------------------- #

SUPPORTED_TYPES = ["pdf", "docx", "txt", "md"]


def extract_pages(name: str, data: bytes) -> list[tuple[Optional[int], str]]:
    """Return [(page_number_or_None, text), ...]."""
    ext = Path(name).suffix.lower()
    if ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
    if ext == ".docx":
        import docx

        d = docx.Document(io.BytesIO(data))
        parts = [p.text for p in d.paragraphs]
        for table in d.tables:
            for row in table.rows:
                parts.append(" | ".join(c.text.strip() for c in row.cells))
        return [(None, "\n".join(parts))]
    if ext in (".txt", ".md", ".markdown"):
        return [(None, data.decode("utf-8", errors="ignore"))]
    raise ValueError(f"Unsupported file type: {ext or name}")


def _split_long(p: str, size: int, overlap: int) -> list[str]:
    out: list[str] = []
    start = 0
    while start < len(p):
        end = min(start + size, len(p))
        if end < len(p):
            window = p[start:end]
            cut = max(window.rfind(". "), window.rfind("? "), window.rfind("! "), window.rfind("\n"))
            if cut < size * 0.5:
                cut = window.rfind(" ")
            if cut > size * 0.3:
                end = start + cut + 1
        out.append(p[start:end].strip())
        if end >= len(p):
            break
        start = max(end - overlap, start + 1)
    return [c for c in out if c]


def chunk_text(text: str, size: int = 800, overlap: int = 120) -> list[str]:
    """Paragraph-aware chunking with a small character overlap between chunks."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []
    chunks: list[str] = []
    cur = ""
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if len(para) > size:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.extend(_split_long(para, size, overlap))
            continue
        if cur and len(cur) + len(para) + 2 > size:
            chunks.append(cur)
            tail = cur[-overlap:] if overlap else ""
            if " " in tail:
                tail = tail[tail.find(" ") + 1 :]
            cur = f"{tail}\n\n{para}" if tail else para
        else:
            cur = f"{cur}\n\n{para}" if cur else para
    if cur:
        chunks.append(cur)
    return chunks


# --------------------------------------------------------------------------- #
# Ollama client
# --------------------------------------------------------------------------- #

def list_models() -> list[str]:
    r = requests.get(f"{base_url()}/api/tags", timeout=5)
    r.raise_for_status()
    return [m["name"] for m in r.json().get("models", [])]


def _prefix(model: str, is_query: bool) -> str:
    # nomic-embed-text was trained with task prefixes; retrieval quality drops without them.
    if "nomic" in model.lower():
        return "search_query: " if is_query else "search_document: "
    return ""


def embed(texts: list[str], model: str, is_query: bool = False) -> np.ndarray:
    pre = _prefix(model, is_query)
    r = requests.post(
        f"{base_url()}/api/embed",
        json={"model": model, "input": [pre + t for t in texts]},
        timeout=300,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Embedding failed ({r.status_code}): {r.text[:300]}")
    vecs = np.array(r.json()["embeddings"], dtype=np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / np.clip(norms, 1e-12, None)


class ThinkSplitter:
    """Splits inline <think>...</think> blocks out of a streamed text, across chunk boundaries."""

    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self) -> None:
        self.buf = ""
        self.in_think = False

    def _kind(self) -> str:
        return "thinking" if self.in_think else "content"

    def feed(self, s: str) -> list[tuple[str, str]]:
        self.buf += s
        out: list[tuple[str, str]] = []
        while True:
            tag = self.CLOSE if self.in_think else self.OPEN
            i = self.buf.find(tag)
            if i >= 0:
                if i:
                    out.append((self._kind(), self.buf[:i]))
                self.buf = self.buf[i + len(tag) :]
                self.in_think = not self.in_think
                continue
            keep = 0
            for k in range(min(len(tag) - 1, len(self.buf)), 0, -1):
                if tag.startswith(self.buf[-k:]):
                    keep = k
                    break
            emit = self.buf[: len(self.buf) - keep]
            if emit:
                out.append((self._kind(), emit))
            self.buf = self.buf[len(self.buf) - keep :]
            return out

    def flush(self) -> list[tuple[str, str]]:
        out = [(self._kind(), self.buf)] if self.buf else []
        self.buf = ""
        return out


def chat_stream(
    messages: list[dict],
    model: str,
    temperature: float = 0.3,
    num_ctx: int = 4096,
    think: bool = False,
) -> Iterator[tuple[str, str]]:
    """Yield ("thinking" | "content", text) pieces from Ollama's /api/chat."""
    url = f"{base_url()}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "think": bool(think),
        "options": {"temperature": temperature, "num_ctx": num_ctx},
    }
    r = requests.post(url, json=payload, stream=True, timeout=(10, 600))
    if r.status_code == 400 and "think" in r.text.lower():
        # Model doesn't support the `think` flag: retry without it.
        r.close()
        payload.pop("think")
        r = requests.post(url, json=payload, stream=True, timeout=(10, 600))
    if r.status_code != 200:
        raise RuntimeError(f"Chat failed ({r.status_code}): {r.text[:300]}")

    splitter = ThinkSplitter()
    try:
        for line in r.iter_lines():
            if not line:
                continue
            data = json.loads(line)
            if "error" in data:
                raise RuntimeError(data["error"])
            msg = data.get("message") or {}
            if msg.get("thinking"):
                yield ("thinking", msg["thinking"])
            if msg.get("content"):
                yield from splitter.feed(msg["content"])
            if data.get("done"):
                break
        yield from splitter.flush()
    finally:
        r.close()


# --------------------------------------------------------------------------- #
# Indexing + retrieval
# --------------------------------------------------------------------------- #

def index_document(
    conn: sqlite3.Connection,
    name: str,
    data: bytes,
    embed_model: str,
    chunk_size: int = 800,
    overlap: int = 120,
    progress: Optional[Callable[[int, int], None]] = None,
) -> tuple[str, int]:
    """Parse, chunk, embed and store a file. Returns (status, n_chunks).

    status is one of: "ok", "duplicate", "empty".
    """
    sha = hashlib.sha256(data).hexdigest()
    if conn.execute("SELECT 1 FROM documents WHERE sha=?", (sha,)).fetchone():
        return "duplicate", 0

    pieces: list[tuple[Optional[int], str]] = []
    for page, text in extract_pages(name, data):
        for c in chunk_text(text, chunk_size, overlap):
            pieces.append((page, c))
    if not pieces:
        return "empty", 0

    batch = 16
    vectors = []
    for i in range(0, len(pieces), batch):
        vectors.append(embed([p[1] for p in pieces[i : i + batch]], embed_model, is_query=False))
        if progress:
            progress(min(i + batch, len(pieces)), len(pieces))
    mat = np.vstack(vectors).astype(np.float32)

    with conn:
        cur = conn.execute(
            "INSERT INTO documents(name, sha, kind, n_chunks, embed_model, added_at) "
            "VALUES (?,?,?,?,?,?)",
            (name, sha, Path(name).suffix.lower().lstrip("."), len(pieces), embed_model, time.time()),
        )
        doc_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO chunks(doc_id, idx, page, text, emb) VALUES (?,?,?,?,?)",
            [(doc_id, i, pg, tx, mat[i].tobytes()) for i, (pg, tx) in enumerate(pieces)],
        )
    return "ok", len(pieces)


@dataclass
class Hit:
    n: int
    doc: str
    page: Optional[int]
    score: float
    text: str

    @property
    def label(self) -> str:
        return f"{self.doc}, p.{self.page}" if self.page else self.doc


def search(
    conn: sqlite3.Connection,
    query_vec: np.ndarray,
    embed_model: str,
    k: int = 4,
    min_score: float = 0.0,
) -> list[Hit]:
    rows = conn.execute(
        "SELECT c.text, c.page, c.emb, d.name FROM chunks c JOIN documents d ON d.id=c.doc_id "
        "WHERE d.enabled=1 AND d.embed_model=?",
        (embed_model,),
    ).fetchall()
    if not rows:
        return []
    mat = np.vstack([np.frombuffer(r["emb"], dtype=np.float32) for r in rows])
    scores = mat @ query_vec.astype(np.float32)
    order = np.argsort(-scores)[:k]
    hits: list[Hit] = []
    for i in order:
        if scores[i] < min_score:
            continue
        r = rows[int(i)]
        hits.append(Hit(len(hits) + 1, r["name"], r["page"], float(scores[i]), r["text"]))
    return hits


# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #

RAG_SYSTEM = (
    "You answer questions using excerpts from the user's own documents. "
    "Rely only on the numbered context excerpts in the final message. "
    "If the answer is not in them, say you couldn't find it in the documents instead of guessing. "
    "Cite the excerpts you used like [1] or [2][3]. Be clear and concise."
)
GENERAL_SYSTEM = "You are a helpful, concise assistant."


def build_rag_messages(question: str, hits: list[Hit], history: list[dict]) -> list[dict]:
    if hits:
        context = "\n\n".join(f"[{h.n}] ({h.label})\n{h.text}" for h in hits)
    else:
        context = "(no relevant excerpts were found)"
    user = f"Context excerpts:\n{context}\n\nQuestion: {question}"
    return [{"role": "system", "content": RAG_SYSTEM}, *history, {"role": "user", "content": user}]


def build_general_messages(question: str, history: list[dict]) -> list[dict]:
    return [
        {"role": "system", "content": GENERAL_SYSTEM},
        *history,
        {"role": "user", "content": question},
    ]
