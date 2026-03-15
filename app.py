"""CheeseCake — multi-agent growth intelligence. Streamlit entry point."""

import uuid
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from core.config import validate_env  # noqa: E402
from storage.postgres import delete_session, ensure_tables, list_sessions, load_artifact, save_artifact
from agents.orchestrator import run_all_agents
from agents.synthesis import chat, synthesize
from renderer.artifacts import render_agent_status, render_report

st.set_page_config(page_title="CheeseCake", page_icon="🍰", layout="wide")

try:
    validate_env()
except ValueError as e:
    st.error(str(e))
    st.stop()


@st.cache_resource
def _init_db() -> None:
    ensure_tables()


_init_db()

# ── State ─────────────────────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = {}


def _get_messages(sid: str) -> list:
    if sid not in st.session_state.messages:
        artifact = load_artifact(sid)
        st.session_state.messages[sid] = artifact["messages"] if artifact else []
    return st.session_state.messages[sid]


def _save(sid: str) -> None:
    msgs = st.session_state.messages.get(sid, [])
    report = next((m["content"] for m in reversed(msgs) if m.get("type") == "report"), None)
    save_artifact(sid, report, msgs)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🍰 CheeseCake")
    st.caption("Growth Intelligence")

    if st.button("＋ New Chat", use_container_width=True, type="primary"):
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

    st.divider()
    st.caption("Sessions")

    for sess in list_sessions():
        sid = sess["session_id"]
        is_active = sid == st.session_state.session_id
        ts = datetime.fromtimestamp(sess["created_at"]).strftime("%b %d, %H:%M") if sess["created_at"] else ""
        label = sess["query"][:36] + ("…" if len(sess["query"]) > 36 else "")

        col_btn, col_del = st.sidebar.columns([5, 1])
        if col_btn.button(label, key=f"s_{sid}", use_container_width=True,
                          help=ts, type="primary" if is_active else "secondary"):
            st.session_state.session_id = sid
            st.rerun()
        if col_del.button("🗑", key=f"d_{sid}", help="Delete"):
            delete_session(sid)
            st.session_state.messages.pop(sid, None)
            if is_active:
                st.session_state.session_id = str(uuid.uuid4())
            st.rerun()

# ── Main ──────────────────────────────────────────────────────────────────────
sid = st.session_state.session_id
messages = _get_messages(sid)

# Quick-start prompts for empty sessions
if not messages:
    st.title("Growth Intelligence")
    for label, query in [
        ("📈 Vector DB market trends", "Key trends driving growth in the vector database market?"),
        ("⚔️ Pinecone competitors", "Main competitors to Pinecone and how they are positioning?"),
        ("🎯 AI agent framework feedback", "What are developers saying about AI agent frameworks?"),
    ]:
        if st.button(label):
            st.session_state["_quick"] = query
            st.rerun()

# Render stored conversation history
for msg in messages:
    with st.chat_message(msg["role"]):
        if msg.get("type") == "report":
            render_report(msg["content"])
        else:
            st.markdown(msg["content"])

# ── Input ─────────────────────────────────────────────────────────────────────
user_input = st.chat_input("Ask anything…") or st.session_state.pop("_quick", None)

if user_input:
    is_first = len(messages) == 0

    # 1. Show user message immediately — before any agent work
    with st.chat_message("user"):
        st.markdown(user_input)
    messages.append({"role": "user", "content": user_input, "type": "text"})

    # 2. Run agents or follow-up chat
    if is_first:
        with st.status("Running intelligence agents…", expanded=True) as status:
            agent_results = run_all_agents(user_input, sid)
            render_agent_status(agent_results)
            status.update(label="Synthesising…", state="running")
            report = synthesize(user_input, agent_results, sid)
            status.update(label="Done ✓", state="complete")
        with st.chat_message("assistant"):
            render_report(report)
        messages.append({"role": "assistant", "content": report, "type": "report"})
    else:
        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                reply = chat(user_input, sid)
            st.markdown(reply)
        messages.append({"role": "assistant", "content": reply, "type": "text"})

    _save(sid)
