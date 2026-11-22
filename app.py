"""Local RAG chat app — Streamlit + Ollama. Run with:  streamlit run app.py"""
from __future__ import annotations

import streamlit as st

import core
import style

st.set_page_config(page_title="Local RAG", page_icon="📚", layout="wide")
style.inject()


@st.cache_resource
def get_conn():
    return core.connect()


@st.cache_data(ttl=5, show_spinner=False)
def fetch_models():
    try:
        return core.list_models(), None
    except Exception as e:  # noqa: BLE001
        return [], str(e)


conn = get_conn()
ss = st.session_state
ss.setdefault("chat_id", None)
ss.setdefault("up_key", 0)
ss.setdefault("index_report", [])
ss.setdefault("rag_mode", True)


# ----------------------------------------------------------------- callbacks #
def new_chat():
    ss.chat_id = None


def select_chat(chat_id: int):
    ss.chat_id = chat_id


def remove_chat(chat_id: int):
    core.delete_chat(conn, chat_id)
    if ss.chat_id == chat_id:
        ss.chat_id = None


def toggle_doc(doc_id: int):
    core.set_document_enabled(conn, doc_id, bool(ss[f"doc_on_{doc_id}"]))


def remove_doc(doc_id: int):
    core.delete_document(conn, doc_id)
    ss.pop(f"doc_on_{doc_id}", None)


def run_indexing(files):
    report = []
    bar = st.progress(0.0, text="Starting…")
    for fi, f in enumerate(files):

        def cb(done, total, fi=fi, name=f.name):
            bar.progress((fi + done / total) / len(files), text=f"{name}: {done}/{total} chunks")

        try:
            status, n = core.index_document(
                conn, f.name, f.getvalue(), ss.embed_model, ss.chunk_size, ss.overlap, cb
            )
        except Exception as e:  # noqa: BLE001
            report.append(("error", f"{f.name}: {e}"))
            continue
        if status == "ok":
            report.append(("success", f"{f.name}: indexed {n} chunks"))
        elif status == "duplicate":
            report.append(("info", f"{f.name}: already indexed (same content)"))
        else:
            report.append(("warning", f"{f.name}: no extractable text (scanned PDF? OCR isn't supported)"))
    ss.index_report = report
    ss.up_key += 1
    st.rerun()


USER_AVATAR, BOT_AVATAR = "🙂", "✨"


def render_sources(sources: list[dict]):
    if not sources:
        return
    with st.expander(f"📎 Sources ({len(sources)})"):
        st.markdown(style.source_cards(sources), unsafe_allow_html=True)


def show_mode(mode: str):
    st.markdown(style.mode_pill(mode, small=True), unsafe_allow_html=True)


# ------------------------------------------------------------------- sidebar #
models, models_err = fetch_models()
chat_models = [m for m in models if not core.is_embed_model(m)]
embed_models = [m for m in models if core.is_embed_model(m)] or models

with st.sidebar:
    st.markdown('<div class="brand">📚 Local <span>RAG</span></div>', unsafe_allow_html=True)
    st.toggle("Answer from my documents (RAG)", key="rag_mode")
    if ss.rag_mode:
        st.caption("Answers are grounded in your indexed documents, with sources.")
    else:
        st.caption("Plain chat with the model. Your documents are ignored.")
    if models_err:
        st.error(f"Can't reach Ollama: {models_err}\n\nStart it with `ollama serve`.")

    chats_tab, docs_tab, settings_tab = st.tabs(["💬 Chats", "📄 Documents", "⚙️ Settings"])

    # Settings first, so later widgets can read their values.
    with settings_tab:
        if not chat_models:
            st.warning("No chat models found. Pull one, e.g. `ollama pull qwen3.5-4b`.")
            ss.chat_model = None
        else:
            if ss.get("chat_model") not in chat_models:
                ss.chat_model = next((m for m in chat_models if "qwen" in m.lower()), chat_models[0])
            st.selectbox("Chat model", chat_models, key="chat_model")
        if not embed_models:
            st.warning("No embedding model found. Run `ollama pull nomic-embed-text`.")
            ss.embed_model = None
        else:
            if ss.get("embed_model") not in embed_models:
                ss.embed_model = next((m for m in embed_models if "nomic" in m.lower()), embed_models[0])
            st.selectbox(
                "Embedding model",
                embed_models,
                key="embed_model",
                help="Documents are searchable only with the embedding model they were indexed with.",
            )
        st.slider("Passages to retrieve (top-k)", 1, 10, 4, key="top_k")
        st.slider(
            "Minimum similarity",
            0.0,
            0.9,
            0.35,
            0.05,
            key="min_score",
            help="Passages scoring below this are dropped. Lower it if nothing is being found.",
        )
        st.slider("Temperature", 0.0, 1.5, 0.3, 0.1, key="temperature")
        st.select_slider("Context window (tokens)", [2048, 4096, 8192, 16384], value=4096, key="num_ctx")
        st.slider("Past messages sent as memory", 0, 12, 6, key="history_turns")
        st.toggle("Show model thinking", value=False, key="show_thinking")
        st.markdown("**Chunking** (applies to newly indexed files)")
        st.slider("Chunk size (chars)", 300, 2000, 800, 50, key="chunk_size")
        st.slider("Chunk overlap (chars)", 0, 400, 120, 10, key="overlap")

    with chats_tab:
        st.button(
            "➕ New chat",
            on_click=new_chat,
            use_container_width=True,
            type="primary" if ss.chat_id is None else "secondary",
        )
        chats = core.list_chats(conn)
        if not chats:
            st.caption("No saved chats yet. They'll appear here and persist across restarts.")
        for c in chats:
            a, b = st.columns([6, 1])
            a.button(
                c["title"],
                key=f"chat_{c['id']}",
                on_click=select_chat,
                args=(c["id"],),
                use_container_width=True,
                type="primary" if c["id"] == ss.chat_id else "secondary",
            )
            b.button("✕", key=f"delchat_{c['id']}", on_click=remove_chat, args=(c["id"],), help="Delete chat")

    with docs_tab:
        for level, msg in ss.index_report:
            getattr(st, level)(msg)
        ss.index_report = []

        files = st.file_uploader(
            "Upload PDF, DOCX, TXT or Markdown",
            type=core.SUPPORTED_TYPES,
            accept_multiple_files=True,
            key=f"uploader_{ss.up_key}",
        )
        if files and st.button(
            f"Index {len(files)} file(s)",
            type="primary",
            use_container_width=True,
            disabled=not ss.get("embed_model"),
        ):
            run_indexing(files)

        docs = core.list_documents(conn)
        st.markdown(f"**Library** · {len(docs)} document(s)")
        if not docs:
            st.caption("Nothing indexed yet. Upload files above.")
        for d in docs:
            a, b = st.columns([6, 1])
            with a:
                st.checkbox(
                    d["name"],
                    value=bool(d["enabled"]),
                    key=f"doc_on_{d['id']}",
                    on_change=toggle_doc,
                    args=(d["id"],),
                    help="Untick to exclude this document from answers.",
                )
                note = f"{d['n_chunks']} chunks · {d['embed_model']}"
                if d["embed_model"] != ss.get("embed_model"):
                    note += " · ⚠️ different embedding model, not searchable now"
                st.caption(note)
            b.button("✕", key=f"deldoc_{d['id']}", on_click=remove_doc, args=(d["id"],), help="Delete document")


# ---------------------------------------------------------------------- main #
messages = core.get_messages(conn, ss.chat_id) if ss.chat_id else []
chat_title = next((c["title"] for c in core.list_chats(conn) if c["id"] == ss.chat_id), "New chat")
st.markdown(style.hero(chat_title, ss.rag_mode), unsafe_allow_html=True)

if not messages:
    has_docs = core.count_active_chunks(conn, ss.get("embed_model") or "") > 0
    st.markdown(style.welcome(ss.rag_mode, has_docs), unsafe_allow_html=True)

for m in messages:
    with st.chat_message(m["role"], avatar=USER_AVATAR if m["role"] == "user" else BOT_AVATAR):
        if m["role"] == "assistant":
            show_mode(m["mode"])
        st.markdown(m["content"])
        if m["role"] == "assistant":
            render_sources(m["sources"])

prompt = st.chat_input(
    "Ask about your documents…" if ss.rag_mode else "Ask me anything…",
    disabled=not ss.get("chat_model"),
)

if prompt:
    mode = "rag" if ss.rag_mode else "general"

    if mode == "rag" and (not ss.get("embed_model") or core.count_active_chunks(conn, ss.embed_model) == 0):
        st.warning(
            "No enabled documents are indexed for the selected embedding model. "
            "Upload some in the Documents tab, or turn the RAG switch off for general chat."
        )
        st.stop()

    history = [{"role": m["role"], "content": m["content"]} for m in messages]
    history = history[-ss.history_turns :] if ss.history_turns else []

    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=BOT_AVATAR):
        show_mode(mode)
        hits: list[core.Hit] = []
        if mode == "rag":
            with st.spinner("Searching your documents…"):
                try:
                    qtext = prompt
                    prev_users = [m["content"] for m in messages if m["role"] == "user"]
                    if len(prompt.split()) < 6 and prev_users:
                        qtext = f"{prev_users[-1]} {prompt}"  # short follow-up: add context
                    qv = core.embed([qtext], ss.embed_model, is_query=True)[0]
                    hits = core.search(conn, qv, ss.embed_model, ss.top_k, ss.min_score)
                except Exception as e:  # noqa: BLE001
                    st.error(f"Retrieval failed: {e}")
                    st.stop()
            if not hits:
                st.info("No passages passed the similarity threshold. Try lowering it in Settings.")
            api_messages = core.build_rag_messages(prompt, hits, history)
        else:
            api_messages = core.build_general_messages(prompt, history)

        think_ph = None
        if ss.show_thinking:
            think_ph = st.expander("🧠 Thinking").empty()
        out = st.empty()
        answer, thinking = "", ""
        try:
            for kind, piece in core.chat_stream(
                api_messages, ss.chat_model, ss.temperature, ss.num_ctx, ss.show_thinking
            ):
                if kind == "thinking":
                    thinking += piece
                    if think_ph is not None:
                        think_ph.markdown(thinking)
                    elif not answer:
                        out.caption("🧠 Thinking…")
                else:
                    answer += piece
                    out.markdown(answer + "▌")
            out.markdown(answer)
        except Exception as e:  # noqa: BLE001
            out.markdown(answer)
            st.error(f"Generation failed: {e}")

        sources = [
            {"n": h.n, "doc": h.doc, "page": h.page, "score": h.score, "text": h.text} for h in hits
        ]
        if answer.strip():
            render_sources(sources)

    if answer.strip():
        created = ss.chat_id is None
        if created:
            title = " ".join(prompt.split())[:40] or "New chat"
            ss.chat_id = core.create_chat(conn, title)
        core.add_message(conn, ss.chat_id, "user", prompt, mode)
        core.add_message(conn, ss.chat_id, "assistant", answer, mode, sources)
        if created:
            st.rerun()  # refresh the sidebar chat list
