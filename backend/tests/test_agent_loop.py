"""Validate the agentic loop end-to-end WITHOUT a live LLM call.

We stub AsyncAnthropic with a scripted sequence of responses that mimics a real
tool-use conversation, then assert the loop injects file_path, emits steps,
collects charts, captures the report, and terminates cleanly.

Run:  ./venv/Scripts/python.exe -m tests.test_agent_loop
"""
import asyncio
import os
import sys
from types import SimpleNamespace

# The agent checks for a key at construction time; a dummy value is enough here.
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-dummy")

from app.agent import DataAnalysisAgent  # noqa: E402

SAMPLE = "sample_data/sales.csv"


def text_block(t):
    return SimpleNamespace(type="text", text=t)


def tool_block(tool_id, name, tool_input):
    return SimpleNamespace(type="tool_use", id=tool_id, name=name, input=tool_input)


class FakeMessages:
    """Returns pre-scripted responses, one per create() call."""

    def __init__(self, script):
        self._script = script
        self._i = 0

    async def create(self, **kwargs):
        resp = self._script[self._i]
        self._i += 1
        return resp


class FakeClient:
    def __init__(self, script):
        self.messages = FakeMessages(script)


SCRIPT = [
    # Turn 1: read the CSV
    SimpleNamespace(
        stop_reason="tool_use",
        content=[
            text_block("Let me inspect the data."),
            tool_block("t1", "read_csv", {}),
        ],
    ),
    # Turn 2: correlation + a chart
    SimpleNamespace(
        stop_reason="tool_use",
        content=[
            tool_block("t2", "correlation_analysis", {}),
            tool_block(
                "t3",
                "create_visualization",
                {"chart_type": "heatmap", "title": "Correlation Heatmap"},
            ),
        ],
    ),
    # Turn 3: generate the report
    SimpleNamespace(
        stop_reason="tool_use",
        content=[
            tool_block(
                "t4",
                "generate_report",
                {"title": "Sales Analysis", "findings": ["Spend drives revenue."]},
            )
        ],
    ),
    # Turn 4: final answer
    SimpleNamespace(
        stop_reason="end_turn",
        content=[text_block("Done — marketing spend strongly predicts revenue.")],
    ),
]


async def main():
    agent = DataAnalysisAgent()
    agent.client = FakeClient(SCRIPT)  # inject the stub

    emitted = []

    async def on_step(step):
        emitted.append(step)
        tag = step.get("tool", "")
        print(f"  [{step['type']}] {tag} {step.get('summary', step.get('message', ''))[:70]}")

    result = await agent.analyze(SAMPLE, "Analyze sales", on_step=on_step)

    # Assertions
    assert result["status"] == "completed", result
    assert result["result"].startswith("Done"), result["result"]
    assert len(result["charts"]) == 1, "expected one collected chart"
    assert result["charts"][0]["plotly_json"], "chart should carry plotly json"
    assert result["report"] and "Sales Analysis" in result["report"], "report missing"
    tool_calls = [s for s in emitted if s["type"] == "tool_use"]
    assert {s["tool"] for s in tool_calls} == {
        "read_csv",
        "correlation_analysis",
        "create_visualization",
        "generate_report",
    }, tool_calls
    # Every tool_result must be successful (proves file_path injection worked).
    results = [s for s in emitted if s["type"] == "tool_result"]
    assert all(s["success"] for s in results), [s for s in results if not s["success"]]

    print("\nPASS — agentic loop verified:")
    print(f"  steps emitted : {len(emitted)}")
    print(f"  tool calls    : {len(tool_calls)}")
    print(f"  charts        : {len(result['charts'])}")
    print(f"  report chars  : {len(result['report'])}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except AssertionError as e:
        print(f"\nFAIL: {e}")
        sys.exit(1)
