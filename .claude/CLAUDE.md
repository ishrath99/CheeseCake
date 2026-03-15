# CheeseCake

Multi-agent growth intelligence system. Single Streamlit conversational page. User asks a question, 6 parallel specialised agents gather live signals via MCP-connected tools, a synthesis agent produces a structured report rendered as inline artifacts. Sessions and memory persist in Postgres.

---

## Environment Setup

- Python 3.11+
- Always use `.venv`: `python -m venv .venv && source .venv/bin/activate`
- Node.js required (for `npx`-based MCP servers) — verify with `node --version`
- All keys loaded from `.env` via `python-dotenv`. Raise `ValueError` at startup for any missing required key.

### Infrastructure — Postgres (Agno PgVector image)

Start before running the app:

```
docker run -d \
  -e POSTGRES_DB=ai \
  -e POSTGRES_USER=ai \
  -e POSTGRES_PASSWORD=ai \
  -e PGDATA=/var/lib/postgresql/data/pgdata \
  -v pgvolume:/var/lib/postgresql/data \
  -p 5532:5432 \
  --name pgvector \
  agno/pgvector:16
```

Connection string: `postgresql+psycopg://ai:ai@localhost:5532/ai`

### `.env`
```
GEMINI_API_KEY=
SERP_API_KEY=
FIRECRAWL_API_KEY=
META_ACCESS_TOKEN=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USERNAME=
REDDIT_PASSWORD=
POSTGRES_URL=postgresql+psycopg://ai:ai@localhost:5532/ai
```

### `requirements.txt`
```
agno[google,firecrawl,psycopg,mcp]
streamlit
python-dotenv
pydantic
requests
praw
psycopg[binary]
mcp
```

---

## Project Structure

```
CheeseCake/
├── CLAUDE.md
├── .env
├── .gitignore            # .venv, .env, __pycache__
├── requirements.txt
├── app.py                # Streamlit entry point
├── core/
│   ├── __init__.py
│   ├── config.py         # env vars, constants, DB URL, MCP server configs
│   └── models.py         # Pydantic: Finding, IntelReport, Confidence
├── storage/
│   ├── __init__.py
│   └── postgres.py       # factory functions: get_agent_storage(), get_memory_db()
├── agents/
│   ├── __init__.py
│   ├── domain_agents.py  # 6 domain agents, each with MCPTools
│   ├── orchestrator.py   # parallel dispatch + session_id threading
│   └── synthesis.py      # synthesis agent + synthesize()
├── tools/
│   ├── __init__.py
│   └── reddit.py         # PRAW-based Reddit tool (plain Python, no MCP)
└── renderer/
    ├── __init__.py
    └── artifacts.py
```

---

## Tech Stack

| Layer | Choice |
|---|---|
| Agent framework | Agno |
| LLM | `Gemini(id="gemini-2.0-flash")` via `agno.models.google` |
| MCP integration | Agno `MCPTools` — wraps MCP servers as native agent tools |
| Parallelism | `concurrent.futures.ThreadPoolExecutor`, 6 workers |
| Session persistence | Agno `PostgresStorage` — per-agent, keyed by `session_id` |
| Cross-session memory | Agno `Memory` + `PostgresMemoryDb` — synthesis agent only |
| Frontend | Streamlit |
| Data models | Pydantic v2 |

---

## MCP Servers

### Phase 1 — Required

#### Firecrawl MCP (official)
- Package: `firecrawl-mcp` via npx
- Provides: `scrape`, `search`, `crawl` tools
- Used by: all 6 domain agents
- Transport: `stdio`
- Agno config:
```python
MCPTools(
    command="npx",
    args=["-y", "firecrawl-mcp"],
    env={"FIRECRAWL_API_KEY": os.getenv("FIRECRAWL_API_KEY")},
    transport="stdio",
)
```

#### Meta Ad Library MCP (`@trypeggy/facebook-ads-library-mcp`)
- Package: installed via Smithery: `npx -y @smithery/cli install @trypeggy/facebook-ads-library-mcp --client claude`
- Provides: `get_meta_ads` — searches public competitor ads by brand name
- Used by: `CompetitiveAgent`, `PositioningAgent`
- Transport: `stdio`
- Requires: ScrapeCreators API key (separate from Meta token — register at scrapcreators.com for free credits)
- Add `SCRAPCREATORS_API_KEY` to `.env`
- Agno config:
```python
MCPTools(
    command="npx",
    args=["-y", "@trypeggy/facebook-ads-library-mcp"],
    env={"API_KEY": os.getenv("SCRAPCREATORS_API_KEY")},
    transport="stdio",
)
```

### Phase 2 — Deferred

| Source | Package | Notes |
|---|---|---|
| SerpAPI | `serpapi-mcp` (official) | Remote: `https://mcp.serpapi.com/YOUR_KEY/mcp` |
| Reddit | `reddit-mcp-server` (netixc/PRAW) | Use Python PRAW tool in Phase 1 |
| LinkedIn | `linkedin-mcp-server` (stickerdaniel) | Requires browser auth, use Firecrawl scrape in Phase 1 |

---

## MCP Tool Instantiation Pattern

Each domain agent creates its own `MCPTools` instance. MCP servers are subprocess-based — each `MCPTools` spawns and manages its own server process. Do not share a single instance across threads.

Define factory functions in `core/config.py`:

**`make_firecrawl_mcp() -> MCPTools`**
Returns a new `MCPTools` instance for Firecrawl. Called once per agent at agent construction time.

**`make_meta_ads_mcp() -> MCPTools`**
Returns a new `MCPTools` instance for the Meta Ad Library MCP. Called only for `CompetitiveAgent` and `PositioningAgent`.

Both functions read keys from environment. Both use `transport="stdio"`.

---

## Data Models (`core/models.py`)

Pydantic v2:

- `Confidence` — enum: `high`, `medium`, `low`
- `Finding` — `domain: str`, `fact: str`, `interpretation: str`, `confidence: Confidence`, `source_url: Optional[str]`, `source_label: Optional[str]`
- `IntelReport` — `query: str`, `product: str`, `findings: List[Finding]`, `summary: str`, `recommended_actions: List[str]`

---

## Storage (`storage/postgres.py`)

**`get_agent_storage(table_name: str) -> PostgresStorage`**
`agno.storage.postgres.PostgresStorage` — persists session turns and tool results. Pass distinct `table_name` per agent.

**`get_memory_db(table_name: str) -> PostgresMemoryDb`**
`agno.memory.v2.db.postgres.PostgresMemoryDb` — persists semantic memories extracted across sessions. Used by synthesis agent only.

Both read `POSTGRES_URL` from `core/config.py`.

---

## Tools

Only one plain Python tool remains — Reddit via PRAW. Everything else is via MCP.

### `tools/reddit.py` — `search_reddit(query: str, subreddit: str = "all", limit: int = 10) -> str`
Uses `praw.Reddit` with `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`, `REDDIT_PASSWORD`. Searches posts. Returns title, score, url, and top comment per post as structured text. Clear docstring — Agno uses it as the tool description. Never raises.

---

## Domain Agents (`agents/domain_agents.py`)

6 Agno `Agent` instances. All use `Gemini(id="gemini-2.0-flash")`.

Each agent:
- Gets a fresh `MCPTools` instance via factory functions — never shared across agents
- Gets `storage=get_agent_storage(f"sessions_{slug}")` for session persistence
- Has `add_history_to_messages=True`, `num_history_runs=5`
- Has a tightly scoped system prompt for its domain
- Is instructed to return a **raw JSON array only** — no prose, no markdown fences
- Each finding object: `{ "fact": "...", "interpretation": "...", "confidence": "high|medium|low", "source_url": "..." }`
- Returns 2–3 findings maximum

| Agent name | Domain | MCP tools | Python tools | Signal focus |
|---|---|---|---|---|
| `MarketTrendsAgent` | Market & Trends | Firecrawl | — | Category growth, funding, job posting trends |
| `CompetitiveAgent` | Competitive Intel | Firecrawl, Meta Ad Library | — | Competitor features, ad spend, messaging |
| `WinLossAgent` | Win / Loss | Firecrawl | `search_reddit` | Reviews, switching reasons, buyer complaints |
| `PricingAgent` | Pricing Intel | Firecrawl | — | Pricing pages, packaging changes, WTP signals |
| `PositioningAgent` | Positioning | Firecrawl, Meta Ad Library | — | Taglines, ad copy patterns, messaging gaps |
| `AdjacentMarketsAgent` | Adjacent Markets | Firecrawl | — | Platform expansions, category collision signals |

Export `ALL_AGENTS: list[Agent]` and `AGENT_DOMAIN_MAP: dict[str, str]`.

---

## Orchestrator (`agents/orchestrator.py`)

**`run_agent(agent: Agent, query: str, session_id: str) -> dict`**
- Calls `agent.run(query, session_id=session_id)`
- Extracts content string from response
- Regex-finds and parses the JSON array
- Returns `{ "agent": agent.name, "findings": [...], "error": None | "..." }`
- Never raises — all exceptions caught and returned in `error` field

**`run_all_agents(query: str, session_id: str) -> list[dict]`**
- Dispatches all 6 agents via `ThreadPoolExecutor(max_workers=6)`
- Passes `session_id` to every call — ties storage records to the user's session
- Collects via `as_completed`

---

## Synthesis Agent (`agents/synthesis.py`)

One `Agent` — `SynthesisAgent`:
- Model: `Gemini(id="gemini-2.0-flash")`
- Storage: `get_agent_storage("sessions_synthesis")`
- Memory: `Memory(model=Gemini(...), db=get_memory_db("memories_synthesis"))`
- `enable_agentic_memory=True` — extracts and stores key facts from each run
- `add_history_to_messages=True`, `num_history_runs=10`
- No tools
- System prompt: identify top 5 deduplicated findings, write 3-sentence executive summary, produce 3 specific actionable recommendations. Respond ONLY in JSON: `{ "summary": "...", "top_findings": [...], "recommended_actions": ["...", "...", "..."] }`

**`synthesize(query: str, raw_results: list[dict], session_id: str) -> dict`**
- Flattens all findings, tags each with domain
- Builds prompt: original query + full findings JSON
- Calls `synthesis_agent.run(prompt, session_id=session_id)`
- Parses JSON response — graceful fallback dict on failure

---

## Artifact Renderer (`renderer/artifacts.py`)

**`render_agent_status(agent_results: list[dict])`**
Row of 6 `st.metric` cards — domain name, signal count, error state.

**`render_report(report: dict)`**
- Executive summary: `st.info`
- Recommended actions: numbered `st.success` blocks
- Per-finding `st.expander` cards: fact, interpretation, confidence badge (🟢🟡🔴), source link
- Grouped by domain with emoji header

Domain emoji: Market 📈 · Competitive ⚔️ · Win/Loss 🎯 · Pricing 💰 · Positioning 📣 · Adjacent 🌐

---

## Streamlit App (`app.py`)

- `st.set_page_config`: wide layout, title "CheeseCake", icon 🍰
- Load `.env` via `core/config.py` at startup
- Generate `session_id = str(uuid.uuid4())` once per browser session, store in `st.session_state.session_id`
- Three pre-built query buttons (Vector Agents demo queries) populate `st.session_state.query`
- `st.text_input` for freeform query
- Primary "Run Intelligence 🔍" button triggers the full pipeline
- `st.status` context manager shows live agent progress
- Call `render_agent_status` inside status block once agents complete
- Call `render_report` after synthesis
- Sidebar: collapsed list of prior queries from `st.session_state.history`
- No business logic in `app.py` — only orchestration calls

---

## Code Standards

- Type hints on all function signatures
- Docstrings on all public functions and classes
- `Exception as e` — never bare `except:`
- No `print()` — use `logging` or `st.write`
- All env vars via `os.getenv()` with `ValueError` on missing at startup
- Each file under 120 lines — split if needed
- `__init__.py` exposes only the public interface of each module
- No business logic in `app.py`

---

## Phase 1 Complete When

- [ ] `.venv` created, all packages install cleanly
- [ ] Docker Postgres reachable at port 5532
- [ ] Firecrawl MCP spawns successfully via `MCPTools`
- [ ] Meta Ad Library MCP spawns successfully via `MCPTools`
- [ ] `streamlit run app.py` launches with no import errors
- [ ] All 6 agents run in parallel on a Vector Agents query
- [ ] At least 4/6 agents return findings with source URLs
- [ ] Synthesis agent produces summary + 3 actions
- [ ] Second query in same session shows context carry-over in synthesis output
- [ ] Report renders in Streamlit without errors

---

## Phase 2 — Iterations

**A — Additional MCP servers**
- SerpAPI MCP (remote, no subprocess): `https://mcp.serpapi.com/YOUR_KEY/mcp`
- Reddit MCP: replace PRAW tool with `netixc/reddit-mcp-server`
- LinkedIn MCP: `stickerdaniel/linkedin-mcp-server` — requires one-time `uvx linkedin-scraper-mcp --login`; add `HiringSignalAgent` using job posting patterns as roadmap signals

**B — Agno Team parallelism**
Migrate from `ThreadPoolExecutor` to Agno native `Team(mode="parallel")` for built-in lifecycle visibility and retry.

**C — Richer rendering**
Plotly confidence heat map, signal-count bar chart per domain, full source trail table.

**D — Demo polish**
Stream findings per agent as they arrive. Aggregate confidence meter. "Dig deeper" quick-action buttons per finding.