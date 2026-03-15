"""CheeseCake — multi-agent growth intelligence. Streamlit entry point."""

import uuid

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from core.config import validate_env  # noqa: E402 — must run after load_dotenv
from storage.postgres import ensure_tables
from agents.orchestrator import run_all_agents
from agents.synthesis import synthesize
from renderer.artifacts import render_agent_status, render_report


@st.cache_resource
def _init_db() -> None:
    """Create all Postgres tables once per process."""
    ensure_tables()

st.set_page_config(page_title="CheeseCake", page_icon="🍰", layout="wide")

# --- Validate env at startup ---
try:
    validate_env()
except ValueError as e:
    st.error(str(e))
    st.stop()

_init_db()

# --- Session init ---
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "history" not in st.session_state:
    st.session_state.history = []
if "query" not in st.session_state:
    st.session_state.query = ""

# --- Sidebar ---
with st.sidebar:
    st.title("🍰 CheeseCake")
    st.caption("Growth Intelligence")
    if st.button("＋ New Chat", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.history = []
        st.session_state.query = ""
        st.rerun()
    if st.session_state.history:
        st.subheader("Prior Queries")
        for q in reversed(st.session_state.history):
            st.caption(q)

# --- Main ---
st.title("Growth Intelligence")

# Pre-built demo queries
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
    st.session_state.history.append(query)

    with st.status("Running 6 intelligence agents in parallel…", expanded=True) as status:
        st.write("Dispatching: Market · Competitive · Win/Loss · Pricing · Positioning · Adjacent")
        agent_results = run_all_agents(query, session_id)
        render_agent_status(agent_results)
        status.update(label="Synthesising findings…", state="running")
        report = synthesize(query, agent_results, session_id)
        status.update(label="Intelligence report ready ✓", state="complete")

    render_report(report)
