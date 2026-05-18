# agents/ — LangGraph Council Graph + Agent Nodes

## OVERVIEW

The council's decision engine. LangGraph `StateGraph` that runs 2 agents in parallel, detects
their disagreements, and optionally loops for multi-round debate. Agent behavior is controlled
by markdown cognitive manuals in `../skills/`.

## STRUCTURE

```
agents/
├── state.py              # CouncilState TypedDict + Annotated reducers
├── council_graph.py      # LangGraph builder: START → run_agents → debate → (loop|END)
├── prompts.py            # SKILLS file loader (runtime .md → system prompt)
├── market_analyst.py     # LangGraph node — TAM/SAM/SOM, growth, pricing, demand
├── devils_advocate.py    # LangGraph node — kill shots, anti-sycophancy enforcement
└── AGENTS.md
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add a new council agent | Create `your_agent.py` + `../skills/your_agent.md` | Wire into `council_graph.py:_run_agent_pair` |
| Change agent behavior | `../skills/market_analyst.md` or `../skills/devils_advocate.md` | No code changes needed |
| Add forbidden phrases | `devils_advocate.py:_FORBIDDEN_EXACT` | Also add to `../skills/devils_advocate.md` |
| Change agent models | Configure via `Settings` env vars or `/api/settings` endpoint |
| Debug agent prompt | `prompts.py:build_system_prompt()` | Combines SKILLS .md + collected data |
| Understand state | `state.py:CouncilState` | `agent_outputs` uses `Annotated[..., operator.add]` for parallel writes |

## CONVENTIONS

- **Agent node signature**: `async def agent_node(state: dict) -> dict` returning `{"agent_outputs": [...]}`
- **State key**: `agent_outputs` merges via `operator.add` — parallel agents append, never overwrite
- **Output format**: `{"role": "agent_name", "content": "...", "confidence": 0.0, ...}`
- **LLM errors**: Return `{"agent_outputs": []}` on failure — never raise, never return `None`
- **Debate context**: Passed via `state["debate_context"]` (string, built by `council_graph._build_debate_context`)
- **Model key constants**: `MODEL_KEY = "..."` at module level in each agent file

## ANTI-PATTERNS

- **Never hardcode system prompts in agent nodes** — load from `../skills/*.md` via `load_skill_file()`
- **Never return raw LLM output without forbidden phrase check** (Devil's Advocate)
- **Never increment `round` in agent nodes** — only the debate node does this
- **Never import from `langgraph.graph` in agent files** — agents are pure async functions
- **Devil's Advocate MUST produce kill shots**: minimum 3, each with data-backed reasoning
