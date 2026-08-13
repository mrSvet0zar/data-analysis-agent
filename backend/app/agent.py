"""Autonomous data-analysis agent.

Runs a tool-use loop against Claude: the model decides which tools to call, we
execute them, feed results back, and repeat until the model ends its turn (or we
hit the iteration cap). A ``on_step`` callback is invoked after every step so the
caller (the WebSocket layer) can stream progress in real time.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

import anthropic

from app.config import settings
from app.tools.definitions import get_tools_for_claude
from app.tools.handlers import DataAnalysisTools

# Handlers that operate on the CSV — the agent injects `file_path` into these.
_FILE_HANDLERS = {
    "read_csv": DataAnalysisTools.read_csv,
    "describe_statistics": DataAnalysisTools.describe_statistics,
    "detect_outliers": DataAnalysisTools.detect_outliers,
    "correlation_analysis": DataAnalysisTools.correlation_analysis,
    "create_visualization": DataAnalysisTools.create_visualization,
}
# Handlers that don't touch the file.
_PLAIN_HANDLERS = {
    "generate_report": DataAnalysisTools.generate_report,
}

StepCallback = Callable[[dict], Awaitable[None]]

SYSTEM_PROMPT = """You are an autonomous data-analysis agent.

A CSV file has already been loaded for you — you do NOT pass a file path to any
tool; just call tools with their analytical arguments. Work methodically:

1. Call read_csv first to understand the structure (columns, dtypes, missing values).
2. Compute descriptive statistics on the numeric columns.
3. Detect outliers on the most relevant numeric columns.
4. Run correlation analysis when there are multiple numeric columns.
5. Create 2-4 visualizations that best illustrate what you found (a histogram of a
   key variable, a correlation heatmap, a scatter of a strong correlation, etc.).
6. Finally call generate_report with a clear title and a list of concrete findings,
   then end your turn with a 2-3 sentence spoken summary for the user.

Be decisive and avoid redundant calls. Base every claim on tool output, not
assumptions. Prefer insight over exhaustiveness."""


class DataAnalysisAgent:
    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not set (see backend/.env).")
        self.client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.ANTHROPIC_MODEL
        self.tools = get_tools_for_claude()

    async def _run_tool(self, name: str, tool_input: dict, file_path: str) -> dict:
        """Execute a tool off the event loop so large CSVs don't block it."""
        if name in _FILE_HANDLERS:
            handler = _FILE_HANDLERS[name]
            return await asyncio.to_thread(handler, file_path, **tool_input)
        if name in _PLAIN_HANDLERS:
            handler = _PLAIN_HANDLERS[name]
            return await asyncio.to_thread(handler, **tool_input)
        return {"success": False, "error": f"Unknown tool: {name}"}

    async def analyze(
        self,
        file_path: str,
        user_request: str,
        on_step: Optional[StepCallback] = None,
    ) -> dict:
        steps: list[dict] = []
        charts: list[dict] = []
        report: Optional[str] = None

        async def emit(step: dict) -> None:
            step["timestamp"] = datetime.now(timezone.utc).isoformat()
            steps.append(step)
            if on_step:
                await on_step(step)

        messages = [
            {
                "role": "user",
                "content": (
                    f"Analyze the uploaded dataset.\n\nUser request: {user_request}\n\n"
                    "Start by reading the CSV."
                ),
            }
        ]

        for iteration in range(settings.MAX_ITERATIONS):
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=self.tools,
                messages=messages,
            )

            # Surface any narrative text the model produced this turn.
            assistant_text = "".join(
                b.text for b in response.content if getattr(b, "type", None) == "text"
            ).strip()
            if assistant_text:
                await emit({"type": "thinking", "iteration": iteration, "message": assistant_text})

            if response.stop_reason != "tool_use":
                # Model is done — final answer.
                await emit(
                    {"type": "completion", "iteration": iteration, "message": assistant_text}
                )
                return {
                    "status": "completed",
                    "result": assistant_text,
                    "steps": steps,
                    "charts": charts,
                    "report": report,
                }

            # Persist the assistant turn (with tool_use blocks) before answering it.
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if getattr(block, "type", None) != "tool_use":
                    continue

                await emit(
                    {
                        "type": "tool_use",
                        "iteration": iteration,
                        "tool": block.name,
                        "input": block.input,
                    }
                )

                result = await self._run_tool(block.name, block.input, file_path)

                # Collect artifacts for the frontend and slim down what goes to the model.
                model_result = result
                if block.name == "create_visualization" and result.get("success"):
                    charts.append(
                        {
                            "title": result.get("title"),
                            "chart_type": result.get("chart_type"),
                            "plotly_json": result.get("plotly_json"),
                        }
                    )
                    # Don't feed the huge Plotly payload back to the model.
                    model_result = {
                        k: v for k, v in result.items() if k != "plotly_json"
                    }
                if block.name == "generate_report" and result.get("success"):
                    report = result.get("report")

                await emit(
                    {
                        "type": "tool_result",
                        "iteration": iteration,
                        "tool": block.name,
                        "success": bool(result.get("success", False)),
                        "summary": _summarize_result(block.name, result),
                    }
                )

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(model_result),
                        "is_error": not result.get("success", False),
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        # Ran out of iterations.
        await emit({"type": "error", "message": "Max iterations reached."})
        return {
            "status": "error",
            "error": "Max iterations reached before the agent finished.",
            "steps": steps,
            "charts": charts,
            "report": report,
        }


def _summarize_result(tool: str, result: dict) -> str:
    """A short human-readable line describing a tool result, for the UI."""
    if not result.get("success", False):
        return f"error: {result.get('error', 'unknown error')}"
    if tool == "read_csv":
        s = result.get("shape", {})
        return f"{s.get('rows', '?')} rows × {s.get('columns', '?')} columns"
    if tool == "describe_statistics":
        return f"stats for {len(result.get('statistics', {}))} numeric column(s)"
    if tool == "detect_outliers":
        return (
            f"{result.get('outlier_count', 0)} outliers "
            f"({result.get('percentage', 0)}%) in '{result.get('column')}'"
        )
    if tool == "correlation_analysis":
        return f"{len(result.get('strong_correlations', []))} strong correlation(s)"
    if tool == "create_visualization":
        return f"{result.get('chart_type')} — {result.get('title')}"
    if tool == "generate_report":
        return "report generated"
    return "ok"
