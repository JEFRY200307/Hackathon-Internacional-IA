from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from app.charts import hydrate_risa_ui
from app.config import settings
from app.llm.guards import (
    ScopeViolation,
    apply_tool_scope,
    grounded_summary,
    guard_citations,
    guard_risa_ui,
    text_is_scoped,
)
from app.llm.planning import (
    DashboardQueryPlan,
    ResolvedScope,
    compile_dashboard,
    create_query_plan,
)
from app.llm.prompts import SYSTEM_PROMPT
from app.llm.tools import TOOLS, run_tool

if TYPE_CHECKING:
    from app.state import AppState

def _collect(result: Any, bag: dict[str, Any]) -> None:
    if isinstance(result, list):
        if result and isinstance(result[0], dict) and "source_id" in result[0]:
            bag["citations"].extend(result)
        return
    if not isinstance(result, dict):
        return
    if "risa_ui" in result:
        bag["risa_ui"] = result["risa_ui"]
    if "chart" in result:
        bag["charts"].append(result["chart"])
    if isinstance(result, dict) and result.get("kind") in {"alert", "rule", "variable", "patient"}:
        bag["citations"].append(result)


async def handle_chat(messages: list[dict[str, str]], app: AppState) -> dict[str, Any]:
    last = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    plan, query_service = await create_query_plan(last, app)
    scope = query_service.resolve(plan)
    bag: dict[str, Any] = {
        "risa_ui": None,
        "charts": [],
        "citations": [],
        "tool_trace": [],
        "degraded": False,
        "model": None,
        "query_plan": plan.model_dump(),
        "resolved_scope": scope.model_dump(),
        "warnings": list(scope.warnings),
    }

    if settings.openai_api_key:
        try:
            text = await _openai_loop(messages, app, bag, plan, scope)
            bag["model"] = settings.llm_model
            return _finalize(text, last, app, bag, plan, scope)
        except Exception as exc:  # noqa: BLE001
            bag["tool_trace"].append({"tool": "llm", "ok": False, "detail": str(exc)})

    bag["degraded"] = True
    bag["model"] = "mock"
    text = await _mock_loop(last, app, bag, plan, scope)
    return _finalize(text, last, app, bag, plan, scope)


def _finalize(
    text: str,
    query: str,
    app: AppState,
    bag: dict[str, Any],
    plan: DashboardQueryPlan,
    scope: ResolvedScope,
) -> dict[str, Any]:
    if not bag["citations"]:
        bag["citations"] = app.rag.search(
            query or "alertas prioridad",
            k=4,
            patient_ids=scope.cohort_ids(),
        )
    bag["citations"], citation_warnings = guard_citations(bag["citations"], scope)
    bag["risa_ui"], widget_warnings = guard_risa_ui(bag["risa_ui"], scope)
    bag["warnings"].extend(citation_warnings + widget_warnings)
    if plan.wants_dashboard and (not bag["risa_ui"] or not bag["risa_ui"].get("widgets")):
        bag["risa_ui"] = hydrate_risa_ui(compile_dashboard(plan, scope, app), app, scope)
        bag["warnings"].append("Se aplicó composición determinista porque la salida generada no superó la verificación.")
    if not text_is_scoped(text, scope):
        bag["warnings"].append("El texto generado mencionó entidades fuera del alcance y fue sustituido.")
        text = grounded_summary(plan, scope, app)
    bag["warnings"] = list(dict.fromkeys(bag["warnings"]))
    return {"content": text, **bag}


async def _openai_loop(
    messages: list[dict[str, str]],
    app: AppState,
    bag: dict[str, Any],
    plan: DashboardQueryPlan,
    scope: ResolvedScope,
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    oai_messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "system",
            "content": (
                "Plan y alcance autorizados (no los amplíes): "
                + json.dumps(
                    {"query_plan": plan.model_dump(), "resolved_scope": scope.model_dump()},
                    ensure_ascii=False,
                )[:12000]
            ),
        },
    ]
    for m in messages[-12:]:
        oai_messages.append({"role": m["role"], "content": m["content"]})

    last_text = ""
    for _ in range(4):
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=oai_messages,
            tools=TOOLS,
            temperature=0.2,
        )
        choice = response.choices[0].message
        last_text = choice.content or last_text
        if not choice.tool_calls:
            return last_text or "No pude completar la respuesta."
        oai_messages.append(
            {
                "role": "assistant",
                "content": choice.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in choice.tool_calls
                ],
            }
        )
        for tc in choice.tool_calls:
            raw_args = json.loads(tc.function.arguments or "{}")
            try:
                args = apply_tool_scope(tc.function.name, raw_args, scope)
                result = await run_tool(tc.function.name, args, app, scope=scope, plan=plan)
                ok = not (isinstance(result, dict) and "error" in result)
            except (ScopeViolation, ValueError) as exc:
                args = raw_args
                result = {"error": str(exc)}
                ok = False
            _collect(result, bag)
            bag["tool_trace"].append({"tool": tc.function.name, "ok": ok, "args": args})
            oai_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str)[:8000],
                }
            )
    return last_text or "Listo. Revisá el panel: usé las herramientas sobre el dataset."


async def _mock_loop(
    text: str,
    app: AppState,
    bag: dict[str, Any],
    plan: DashboardQueryPlan,
    scope: ResolvedScope,
) -> str:
    planned: list[tuple[str, dict[str, Any]]] = [
        ("get_dashboard_context", {}),
        ("summarize_scope", {}),
        (
            "retrieve_evidence",
            {"query": text or "alertas prioridad", "k": 6, "patient_ids": sorted(scope.cohort_ids())},
        ),
    ]
    for name, raw_args in planned:
        try:
            args = apply_tool_scope(name, raw_args, scope)
            result = await run_tool(name, args, app, scope=scope, plan=plan)
            ok = not (isinstance(result, dict) and "error" in result)
        except (ScopeViolation, ValueError) as exc:
            args, result, ok = raw_args, {"error": str(exc)}, False
        _collect(result, bag)
        bag["tool_trace"].append({"tool": name, "ok": ok, "args": args})
    if plan.wants_dashboard:
        bag["risa_ui"] = hydrate_risa_ui(compile_dashboard(plan, scope, app), app, scope)
        bag["tool_trace"].append(
            {"tool": "emit_risa_ui", "ok": True, "args": {"scope_id": scope.scope_id, "strategy": plan.intent}}
        )
    return grounded_summary(plan, scope, app)
