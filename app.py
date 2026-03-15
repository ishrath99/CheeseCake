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
from renderer.artifacts import render_agent_status, render_artifacts_panel
from guardrails import check_input

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

# ── Main layout ───────────────────────────────────────────────────────────────
sid = st.session_state.session_id
messages = _get_messages(sid)

col_chat, col_artifacts = st.columns([3, 2])

with col_chat:
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

    for msg in messages:
        if msg.get("type") == "report":
            with st.chat_message("assistant"):
                summary = msg["content"].get("summary", "") if isinstance(msg.get("content"), dict) else ""
                n = len(msg["content"].get("top_findings", [])) if isinstance(msg.get("content"), dict) else 0
                if summary:
                    st.markdown(summary)
                st.caption(f"📋 {n} findings in the Artifacts panel →")
        else:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

with col_artifacts:
    report_count = sum(1 for m in messages if m.get("type") == "report")
    st.subheader(f"📋 Artifacts ({report_count})")
    render_artifacts_panel(messages)

# ── Input (pinned to bottom) ───────────────────────────────────────────────────
user_input = st.chat_input("Ask anything…") or st.session_state.pop("_quick", None)

if user_input:
    is_first = len(messages) == 0

    # Show user message immediately — before guardrail LLM call
    with col_chat:
        with st.chat_message("user"):
            st.markdown(user_input)

    # ── Guardrails ────────────────────────────────────────────────────────────
    guard = check_input(user_input, messages)
    messages.append({"role": "user", "content": user_input, "type": "text"})

    if not guard.passed:
        reply_text = guard.reply or f"I can't help with that — {guard.reason}"
        with col_chat:
            with st.chat_message("assistant"):
                st.markdown(reply_text)
        messages.append({"role": "assistant", "content": reply_text, "type": "text"})
        _save(sid)
        st.rerun()

    # Use cleaned query (PII redacted) for all downstream processing
    user_input = guard.cleaned_query

    if is_first:
        with col_chat:
            with st.status("Running intelligence agents…", expanded=True) as status:
                agent_results = run_all_agents(user_input, sid)
                render_agent_status(agent_results)
                status.update(label="Synthesising…", state="running")
                report = synthesize(user_input, agent_results, sid)
                status.update(label="Done ✓", state="complete")
        messages.append({"role": "assistant", "content": report, "type": "report"})
    else:
        with col_chat:
            with st.chat_message("assistant"):
                with st.spinner("Thinking…"):
                    reply = chat(user_input, sid)
                st.markdown(reply)
        messages.append({"role": "assistant", "content": reply, "type": "text"})

    _save(sid)
    st.rerun()
