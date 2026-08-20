"""Live end-to-end run of the agent against a real Claude API call.

Usage:  ./venv/Scripts/python.exe -m tests.live_test [sample_data/sales.csv]
"""

import asyncio
import sys

from app.agent import DataAnalysisAgent


async def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "sample_data/sales.csv"
    agent = DataAnalysisAgent()
    print(f"Model: {agent.model}")
    print(f"Analyzing: {path}\n" + "-" * 60)

    async def on_step(step):
        t = step["type"]
        if t == "tool_use":
            print(f"🔧 {step['tool']}({step.get('input', {})})")
        elif t == "tool_result":
            flag = "✅" if step["success"] else "❌"
            print(f"   {flag} {step.get('summary', '')}")
        elif t == "thinking":
            print(f"💭 {step['message'][:120]}")
        elif t == "completion":
            print(f"\n🏁 FINAL:\n{step['message']}")
        elif t == "error":
            print(f"⚠️  {step['message']}")

    result = await agent.analyze(
        path, "Analyze this data and surface the key insights.", on_step=on_step
    )

    print("-" * 60)
    print(f"status : {result['status']}")
    print(
        f"charts : {len(result['charts'])}  ->  "
        f"{[c['chart_type'] + ':' + str(c['title']) for c in result['charts']]}"
    )
    report_info = f"yes ({len(result['report'])} chars)" if result["report"] else "none"
    print(f"report : {report_info}")


if __name__ == "__main__":
    asyncio.run(main())
