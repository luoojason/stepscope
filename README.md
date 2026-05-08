# stepscope

> Funnel analytics for AI agents — see where conversations drop off across all your sessions.

**Alpha — v0.1 OSS launch coming in ~4 weeks.**

## Quick Start

```bash
pip install stepscope
```

```python
import stepscope

stepscope.init(local=True)

with stepscope.step("parse_input"):
    pass

with stepscope.step("retrieve_context"):
    pass

with stepscope.step("respond"):
    pass
```

```bash
stepscope funnel ./stepscope.db
```

```
Step funnel (last 24h, 1 sessions)
────────────────────────────────────────────────────
parse_input            ████████████████  1 (100%)
retrieve_context       ████████████████  1 (100%)
respond                ████████████████  1 (100%)
```

## What is this?

Most LLM observability tools (Langfuse, Phoenix, Helicone) show you individual traces.
stepscope shows you **aggregate funnels** — where conversations drop off across *all* your sessions.

Think Mixpanel for agent conversations, not a trace viewer.

## LangGraph (1 config line)

```python
from stepscope.langchain import StepScopeCallback
import stepscope

stepscope.init(local=True)
graph.invoke(inputs, config={"callbacks": [StepScopeCallback()]})
```

```bash
stepscope funnel ./stepscope.db --since all   # where do sessions drop off?
stepscope loops  ./stepscope.db --since all   # which sessions are stuck in a loop?
```

## Status

- [x] `stepscope.init(local=True)` + SQLite local mode
- [x] `with stepscope.step("name"):` context manager
- [x] `stepscope funnel <db>` ASCII funnel CLI
- [x] `stepscope loops <db>` loop detector
- [x] `StepScopeCallback` for LangChain / LangGraph (1 config line)
- [ ] Hosted dashboard — W8 beta
- [ ] Public hosted launch — W12

## License

MIT
