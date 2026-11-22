"""Visual styling for the app: one CSS block injected into Streamlit."""
from __future__ import annotations

import html

import streamlit as st

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

:root {
  --violet: #8B5CF6;
  --pink: #EC4899;
  --orange: #F59E0B;
  --teal: #14B8A6;
  --cyan: #22D3EE;
  --ink: #F3EEFF;
  --muted: #A99FCC;
  --card: rgba(255, 255, 255, 0.05);
  --line: rgba(255, 255, 255, 0.10);
  --grad: linear-gradient(135deg, #8B5CF6 0%, #EC4899 55%, #F59E0B 100%);
}

html, body, [class*="css"], .stApp {
  font-family: 'Plus Jakarta Sans', system-ui, -apple-system, 'Segoe UI', sans-serif;
}

/* ---------- page background ---------- */
.stApp {
  background:
    radial-gradient(900px 500px at 8% -8%, rgba(139, 92, 246, 0.28), transparent 60%),
    radial-gradient(800px 480px at 100% 0%, rgba(236, 72, 153, 0.20), transparent 60%),
    radial-gradient(700px 500px at 60% 110%, rgba(20, 184, 166, 0.14), transparent 60%),
    #0E0A1F;
}
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2.2rem; max-width: 980px; }

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #1D1040 0%, #150C2E 55%, #0F0922 100%);
  border-right: 1px solid var(--line);
}
.brand {
  font-size: 1.55rem; font-weight: 800; letter-spacing: -0.02em; margin: 0 0 .4rem 0;
}
.brand span {
  background: var(--grad); -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent;
}

/* tabs */
button[data-baseweb="tab"] { font-weight: 600; color: var(--muted); }
button[data-baseweb="tab"][aria-selected="true"] { color: var(--ink); }
[data-baseweb="tab-highlight"] { background: var(--grad) !important; height: 3px; border-radius: 3px; }
[data-baseweb="tab-border"] { background: var(--line) !important; }

/* ---------- buttons ---------- */
[data-testid="stBaseButton-primary"] {
  background: var(--grad); border: 0; color: #fff; font-weight: 700;
  border-radius: 12px; box-shadow: 0 6px 20px rgba(139, 92, 246, 0.35);
  transition: transform .12s ease, box-shadow .12s ease, filter .12s ease;
}
[data-testid="stBaseButton-primary"]:hover {
  transform: translateY(-1px); filter: brightness(1.08);
  box-shadow: 0 10px 26px rgba(236, 72, 153, 0.35); color: #fff; border: 0;
}
[data-testid="stBaseButton-secondary"] {
  background: var(--card); border: 1px solid var(--line); color: var(--ink);
  border-radius: 12px; transition: all .12s ease;
}
[data-testid="stBaseButton-secondary"]:hover {
  border-color: var(--violet); background: rgba(139, 92, 246, 0.14); color: #fff;
}

/* ---------- inputs ---------- */
[data-baseweb="select"] > div, [data-testid="stFileUploaderDropzone"] {
  background: var(--card); border: 1px solid var(--line); border-radius: 12px;
}
[data-testid="stFileUploaderDropzone"] { border: 1.5px dashed rgba(167, 139, 250, 0.55); }
[data-testid="stFileUploaderDropzone"]:hover { background: rgba(139, 92, 246, 0.10); }

[data-testid="stChatInput"] {
  background: rgba(26, 18, 54, 0.85); border: 1px solid rgba(167, 139, 250, 0.4);
  border-radius: 18px; box-shadow: 0 10px 40px rgba(139, 92, 246, 0.18);
}
[data-testid="stChatInput"]:focus-within {
  border-color: var(--pink); box-shadow: 0 0 0 3px rgba(236, 72, 153, 0.22), 0 10px 40px rgba(139, 92, 246, 0.25);
}
[data-testid="stChatInput"] button { background: var(--grad); color: #fff; border-radius: 12px; }

/* ---------- chat bubbles ---------- */
[data-testid="stChatMessage"] {
  border-radius: 20px; padding: 1rem 1.2rem; margin-bottom: .8rem;
  background: var(--card); border: 1px solid var(--line); backdrop-filter: blur(6px);
}
[data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) {
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.26), rgba(236, 72, 153, 0.18));
  border-color: rgba(167, 139, 250, 0.5);
}
[data-testid="stChatMessage"]:has([aria-label="Chat message from assistant"]) {
  background: linear-gradient(135deg, rgba(20, 184, 166, 0.10), rgba(255, 255, 255, 0.03));
  border-color: rgba(34, 211, 238, 0.28);
}
[data-testid="stChatMessage"] > div[aria-hidden="true"] {
  background: var(--grad) !important; border-radius: 50%;
  box-shadow: 0 4px 14px rgba(139, 92, 246, 0.4);
}

/* ---------- hero header ---------- */
.hero { display: flex; align-items: center; gap: .9rem; flex-wrap: wrap; margin-bottom: .6rem; }
.hero-title {
  font-size: 2rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1.15;
  background: var(--grad); -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent;
}
.pill {
  display: inline-block; padding: .22rem .75rem; border-radius: 999px;
  font-size: .78rem; font-weight: 700; color: #06121A; letter-spacing: .01em;
}
.pill-rag { background: linear-gradient(135deg, #14B8A6, #22D3EE); }
.pill-general { background: linear-gradient(135deg, #F59E0B, #F472B6); }
.pill-sm { font-size: .72rem; padding: .12rem .6rem; margin-bottom: .45rem; }

/* ---------- welcome cards ---------- */
.welcome { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 1rem; margin: 1.2rem 0 2rem; }
.wcard {
  padding: 1.1rem 1.2rem; border-radius: 18px; background: var(--card);
  border: 1px solid var(--line); position: relative; overflow: hidden;
}
.wcard::before { content: ""; position: absolute; inset: 0 0 auto 0; height: 3px; background: var(--c, var(--grad)); }
.wcard .ico { font-size: 1.6rem; }
.wcard h4 { margin: .35rem 0 .2rem; font-size: 1.02rem; font-weight: 700; color: var(--ink); }
.wcard p { margin: 0; color: var(--muted); font-size: .88rem; line-height: 1.45; }

/* ---------- source cards ---------- */
.src {
  padding: .8rem 1rem; margin: .5rem 0; border-radius: 14px; background: var(--card);
  border: 1px solid var(--line); border-left: 4px solid var(--violet);
}
.src-head { display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; font-weight: 700; font-size: .9rem; }
.src-n {
  display: inline-flex; align-items: center; justify-content: center; width: 1.5rem; height: 1.5rem;
  border-radius: 50%; background: var(--grad); color: #fff; font-size: .78rem;
}
.src-loc { color: var(--ink); }
.src-score { margin-left: auto; color: var(--muted); font-weight: 600; font-size: .78rem; }
.bar { height: 5px; border-radius: 5px; background: rgba(255, 255, 255, 0.08); margin: .5rem 0; overflow: hidden; }
.bar > i { display: block; height: 100%; background: linear-gradient(90deg, #14B8A6, #22D3EE, #A78BFA); }
.src-text { color: var(--muted); font-size: .85rem; line-height: 1.5; white-space: pre-wrap; }

/* ---------- expanders / misc ---------- */
[data-testid="stExpander"] { border: 1px solid var(--line); border-radius: 14px; background: rgba(255, 255, 255, 0.03); }
[data-testid="stExpander"] summary { font-weight: 600; }
[data-testid="stAlert"] { border-radius: 14px; }
[data-testid="stProgress"] > div > div > div > div { background: var(--grad); }
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-thumb { background: rgba(167, 139, 250, 0.35); border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: rgba(167, 139, 250, 0.6); }
"""


def inject() -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def mode_pill(mode: str, small: bool = False) -> str:
    cls = "pill-rag" if mode == "rag" else "pill-general"
    label = "📚 From your documents" if mode == "rag" else "💬 General chat"
    return f'<span class="pill {cls}{" pill-sm" if small else ""}">{label}</span>'


def hero(title: str, rag: bool) -> str:
    cls = "pill-rag" if rag else "pill-general"
    label = "📚 Document mode" if rag else "💬 General mode"
    return (
        f'<div class="hero"><div class="hero-title">{esc(title)}</div>'
        f'<span class="pill {cls}">{label}</span></div>'
    )


def welcome(rag: bool, has_docs: bool) -> str:
    if rag:
        cards = [
            ("📄", "Add your documents", "Upload PDFs, Word files, text or Markdown from the Documents tab.", "linear-gradient(90deg,#8B5CF6,#EC4899)"),
            ("🔎", "Ask anything", "Questions are matched to the most relevant passages in your files.", "linear-gradient(90deg,#14B8A6,#22D3EE)"),
            ("📎", "See the sources", "Every answer lists the passages and pages it came from.", "linear-gradient(90deg,#F59E0B,#EC4899)"),
        ]
        if has_docs:
            cards[0] = ("✅", "Library ready", "Your documents are indexed. Ask a question below.", "linear-gradient(90deg,#22C55E,#14B8A6)")
    else:
        cards = [
            ("💬", "Free chat", "Talk to the local model directly. Your documents are ignored.", "linear-gradient(90deg,#F59E0B,#F472B6)"),
            ("🧠", "Remembers context", "Recent messages are sent along so follow-ups make sense.", "linear-gradient(90deg,#8B5CF6,#22D3EE)"),
            ("🔒", "Fully local", "Everything runs on your machine through Ollama.", "linear-gradient(90deg,#14B8A6,#22D3EE)"),
        ]
    items = "".join(
        f'<div class="wcard" style="--c:{c}"><div class="ico">{i}</div><h4>{esc(t)}</h4><p>{esc(d)}</p></div>'
        for i, t, d, c in cards
    )
    return f'<div class="welcome">{items}</div>'


def source_cards(sources: list[dict]) -> str:
    out = []
    for s in sources:
        loc = s["doc"] + (f", p.{s['page']}" if s.get("page") else "")
        pct = max(0.0, min(1.0, float(s["score"]))) * 100
        out.append(
            f'<div class="src"><div class="src-head"><span class="src-n">{s["n"]}</span>'
            f'<span class="src-loc">{esc(loc)}</span>'
            f'<span class="src-score">similarity {float(s["score"]):.2f}</span></div>'
            f'<div class="bar"><i style="width:{pct:.0f}%"></i></div>'
            f'<div class="src-text">{esc(s["text"])}</div></div>'
        )
    return "".join(out)
