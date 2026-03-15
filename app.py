"""CheeseCake — multi-agent growth intelligence. Streamlit entry point."""

import uuid
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from core.config import validate_env  # noqa: E402
from storage.postgres import delete_session, ensure_tables, list_sessions
from agents.orchestrator import run_all_agents
from agents.synthesis import synthesize
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

# --- State init ---
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "query" not in st.session_state:
    st.session_state.query = ""
if "reports" not in st.session_state:
    st.session_state.reports: dict = {}  # {session_id: report}


# --- Sidebar ---
def _fmt_ts(ts: int | None) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(ts).strftime("%b %d, %H:%M")


with st.sidebar:
    st.title("🍰 CheeseCake")
    st.caption("Growth Intelligence")

    if st.button("＋ New Chat", use_container_width=True, type="primary"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.query = ""
        st.rerun()

    st.divider()
    st.caption("Sessions")

    sessions = list_sessions()
    for sess in sessions:
        sid = sess["session_id"]
        label = sess["query"]
        ts = _fmt_ts(sess["created_at"])
        is_active = sid == st.session_state.session_id

        col_btn, col_del = st.sidebar.columns([5, 1])

        btn_label = f"**{label[:38]}**\n\n{ts}" if is_active else f"{label[:38]}\n\n{ts}"
        if col_btn.button(
            btn_label,
            key=f"s_{sid}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            st.session_state.session_id = sid
            st.session_state.query = label
            st.rerun()

        if col_del.button("🗑", key=f"d_{sid}", help="Delete session"):
            delete_session(sid)
            st.session_state.reports.pop(sid, None)
            if sid == st.session_state.session_id:
                st.session_state.session_id = str(uuid.uuid4())
                st.session_state.query = ""
            st.rerun()


# --- Main ---
st.title("Growth Intelligence")

col1, col2, col3 = st.columns(3)
if col1.button("📈 Vector DB market trends"):
    st.session_state.query = "What are the key trends driving growth in the vector database market?"
if col2.button("⚔️ Pinecone competitors"):
    st.session_state.query = "Who are the main competitors to Pinecone and how are they positioning?"
if col3.button("🎯 AI agent framework feedback"):
    st.session_state.query = "What are developers saying about AI agent frameworks on Reddit and review sites?"

query = st.text_input(
    "Ask a growth intelligence question",
    value=st.session_state.query,
    placeholder="e.g. What funding activity is happening in the AI observability market?",
)

if st.button("Run Intelligence 🔍", type="primary", disabled=not query.strip()):
    session_id = st.session_state.session_id
    with st.status("Running intelligence agents in parallel…", expanded=True) as status:
        st.write("Dispatching agents…")
        agent_results = run_all_agents(query, session_id)
        render_agent_status(agent_results)
        status.update(label="Synthesising findings…", state="running")
        report = synthesize(query, agent_results, session_id)
        status.update(label="Intelligence report ready ✓", state="complete")
    st.session_state.reports[session_id] = report
    st.session_state.query = query
    st.rerun()

# Show cached report for the active session
active_report = st.session_state.reports.get(st.session_state.session_id)
if active_report:
    render_report(active_report)
