"""LangChain / LangGraph callback integration for stepscope."""
from __future__ import annotations

import time
from typing import Any, Optional
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from stepscope._config import _CONFIG
from stepscope._ids import new_step_id
from stepscope.step import Step, _current_step


def _node_name(serialized: Optional[dict[str, Any]]) -> str:
    """Extract a human-readable name from LangChain's serialized dict."""
    if not serialized:
        return "unknown"
    if serialized.get("name"):
        return serialized["name"]
    ids = serialized.get("id", [])
    return ids[-1] if ids else "unknown"


class StepScopeCallback(BaseCallbackHandler):
    """One-line LangChain/LangGraph instrumentation.

    Usage:
        graph.invoke(inputs, config={"callbacks": [StepScopeCallback()]})
    """

    def __init__(self) -> None:
        super().__init__()
        self._run_to_step: dict[UUID, str] = {}   # run_id → step_id
        self._llm_starts: dict[UUID, float] = {}  # run_id → started_at
        self._tool_starts: dict[UUID, float] = {}  # run_id → started_at

    def _parent_step_id(self, parent_run_id: Optional[UUID]) -> Optional[str]:
        """Resolve parent step: run_id lookup > contextvar fallback."""
        if parent_run_id and parent_run_id in self._run_to_step:
            return self._run_to_step[parent_run_id]
        cur = _current_step.get()
        return cur.step_id if cur else None

    # ── Chain / LangGraph node ──────────────────────────────────────────────

    def on_chain_start(
        self,
        serialized: Optional[dict[str, Any]],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        cfg = _CONFIG._instance
        if cfg is None:
            return
        # Skip LangGraph hidden inner calls
        if tags and "langsmith:hidden" in tags:
            return
        tags_list = tags or []
        lg_node: Optional[str] = (metadata or {}).get("langgraph_node")
        if lg_node:
            # In LangGraph each node fires both graph:step:N (boundary) and
            # seq:step:M (inner callable). Only count the boundary event.
            if not any(t.startswith("graph:step:") for t in tags_list):
                return
            if lg_node.startswith("__"):
                return
            name = lg_node
        elif metadata is not None:
            # LangGraph context but no named node — outer shell, skip
            return
        else:
            # Plain LangChain chain — use serialized/kwargs name
            name = kwargs.get("name") or _node_name(serialized)
            if not name or name.startswith("__"):
                return
        s = Step(
            step_id=new_step_id(),
            session_id=cfg.session_id,
            parent_step_id=self._parent_step_id(parent_run_id),
            name=name,
        )
        cfg.buffer.write_step_start(s)
        self._run_to_step[run_id] = s.step_id

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        cfg = _CONFIG._instance
        if cfg is None:
            return
        step_id = self._run_to_step.pop(run_id, None)
        if step_id:
            cfg.buffer.write_step_end_by_id(step_id, status="success")

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        cfg = _CONFIG._instance
        if cfg is None:
            return
        step_id = self._run_to_step.pop(run_id, None)
        if step_id:
            cfg.buffer.write_step_end_by_id(step_id, status="error", error=str(error))

    # ── LLM calls ──────────────────────────────────────────────────────────

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        self._llm_starts[run_id] = time.time()

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        self._llm_starts[run_id] = time.time()

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        cfg = _CONFIG._instance
        if cfg is None:
            return
        started_at = self._llm_starts.pop(run_id, time.time())
        step_id = self._run_to_step.get(parent_run_id) if parent_run_id else None

        llm_output = getattr(response, "llm_output", None) or {}
        usage = llm_output.get("token_usage", {})
        model = llm_output.get("model_name")

        resp_text: Optional[str] = None
        if cfg.store_responses and response.generations:
            gen = response.generations[0][0] if response.generations[0] else None
            if gen is not None:
                if hasattr(gen, "text"):
                    resp_text = gen.text
                elif hasattr(gen, "message"):
                    resp_text = str(getattr(gen.message, "content", ""))

        cfg.buffer.write_llm_call(
            span_id=str(run_id),
            step_id=step_id or "",
            gen_ai_system=None,
            gen_ai_model=model,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            started_at=started_at,
            response_text=resp_text,
        )

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._llm_starts.pop(run_id, None)

    # ── Tool calls ─────────────────────────────────────────────────────────

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        cfg = _CONFIG._instance
        if cfg is None:
            return
        started_at = time.time()
        self._tool_starts[run_id] = started_at
        step_id = self._run_to_step.get(parent_run_id) if parent_run_id else None
        cfg.buffer.write_tool_call_start(
            span_id=str(run_id),
            step_id=step_id or "",
            tool_name=_node_name(serialized),
            args_preview=input_str[:200] if input_str else None,
            args_length=len(input_str) if input_str else 0,
            started_at=started_at,
        )

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        cfg = _CONFIG._instance
        if cfg is None:
            return
        self._tool_starts.pop(run_id, None)
        result = str(output) if output is not None else ""
        cfg.buffer.write_tool_call_end(
            span_id=str(run_id),
            success=True,
            result_preview=result[:200],
            result_length=len(result),
        )

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        cfg = _CONFIG._instance
        if cfg is None:
            return
        self._tool_starts.pop(run_id, None)
        cfg.buffer.write_tool_call_end(
            span_id=str(run_id),
            success=False,
            error=str(error),
        )
