"""Deliberately broken LangGraph agent — loops on retrieval failure.

The agent retries `retrieve_context` up to 3 times before giving up.
The funnel shows retrieve_context firing multiple times — the loop signature.

Run:
    python examples/langgraph_broken_agent.py
    stepscope funnel ./stepscope.db --since all
"""
import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, StateGraph

import stepscope
from stepscope.langchain import StepScopeCallback

stepscope.init(local=True, db_path="./stepscope.db")
cb = StepScopeCallback()
CALLBACKS = {"callbacks": [cb]}

_attempt = 0


class AgentState(TypedDict):
    query: str
    context: str
    attempts: Annotated[int, operator.add]
    done: bool


def parse_input(state: AgentState) -> dict:
    return {}


def retrieve_context(state: AgentState) -> dict:
    global _attempt
    _attempt += 1
    if _attempt < 3:
        return {"attempts": 1}  # failure: no context set, triggers retry
    return {"context": "Paris is the capital of France.", "attempts": 1}


def respond(state: AgentState) -> dict:
    print(f"Answer: {state['context']}")
    return {"done": True}


def route(state: AgentState) -> str:
    if state.get("context"):
        return "respond"
    if state.get("attempts", 0) >= 5:
        return END
    return "retrieve_context"


builder = StateGraph(AgentState)
builder.add_node("parse_input", parse_input)
builder.add_node("retrieve_context", retrieve_context)
builder.add_node("respond", respond)

builder.set_entry_point("parse_input")
builder.add_edge("parse_input", "retrieve_context")
builder.add_conditional_edges("retrieve_context", route)
builder.add_edge("respond", END)

graph = builder.compile()

graph.invoke(
    {"query": "What is the capital of France?", "context": "", "attempts": 0, "done": False},
    config=CALLBACKS,
)

print("\nRun: stepscope funnel ./stepscope.db --since all")
print("retrieve_context should appear with count=3 (loop detected)")
