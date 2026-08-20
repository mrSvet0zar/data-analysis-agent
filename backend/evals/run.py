"""Run the agent against the golden cases and print a scorecard.

Usage:
    ./venv/Scripts/python.exe -m evals.run          # all cases
    ./venv/Scripts/python.exe -m evals.run sales    # one case by name

Exits non-zero if any case falls below the pass thresholds, so it can gate a
release (it is intentionally NOT part of the fast CI, since it spends tokens).
"""

import asyncio
import sys

from app.agent import DataAnalysisAgent
from app.tools.handlers import DataAnalysisTools as T
from evals.cases import CASES, EvalCase
from evals.judge import judge_report

# Pass thresholds.
MIN_TOOL_COVERAGE = 1.0
MIN_GROUNDING = 0.8
MIN_QUALITY = 3


def compute_ground_truth(case: EvalCase) -> str:
    """Deterministic facts from our own tools, used to grade the agent's report."""
    facts: list[str] = []
    info = T.read_csv(case.csv_path)
    if info.get("success"):
        s = info["shape"]
        facts.append(f"- shape: {s['rows']} rows x {s['columns']} columns")
        facts.append(f"- numeric columns: {info.get('numeric_columns')}")
    corr = T.correlation_analysis(case.csv_path)
    if corr.get("success"):
        pairs = [
            f"{p['column1']}~{p['column2']} r={p['correlation']:.2f}"
            for p in corr.get("strong_correlations", [])
        ]
        facts.append(f"- strong correlations: {pairs or 'none'}")
    if case.key_outlier_column:
        out = T.detect_outliers(case.csv_path, "iqr", case.key_outlier_column)
        if out.get("success"):
            facts.append(
                f"- outliers in '{case.key_outlier_column}': {out['outlier_count']} "
                f"({out['percentage']}%)"
            )
    return "\n".join(facts)


async def run_case(case: EvalCase) -> dict:
    ground_truth = compute_ground_truth(case)
    agent = DataAnalysisAgent()
    result = await agent.analyze(case.csv_path, case.request)

    tools_called = {s["tool"] for s in result["steps"] if s["type"] == "tool_use"}
    coverage = (
        len(case.expected_tools & tools_called) / len(case.expected_tools)
        if case.expected_tools
        else 1.0
    )
    n_charts = len(result.get("charts", []))
    report = result.get("report") or result.get("result") or ""

    judged = {"grounding": 0.0, "quality": 0, "notes": "no report"}
    if report:
        judged = await judge_report(ground_truth, report)

    passed = (
        result["status"] == "completed"
        and coverage >= MIN_TOOL_COVERAGE
        and n_charts >= case.min_charts
        and judged["grounding"] >= MIN_GROUNDING
        and judged["quality"] >= MIN_QUALITY
    )
    return {
        "name": case.name,
        "status": result["status"],
        "coverage": coverage,
        "missing_tools": sorted(case.expected_tools - tools_called),
        "charts": n_charts,
        "min_charts": case.min_charts,
        "grounding": judged["grounding"],
        "quality": judged["quality"],
        "notes": judged["notes"],
        "cost_usd": result.get("usage", {}).get("cost_usd", 0.0),
        "passed": passed,
    }


async def main() -> int:
    wanted = sys.argv[1:] if len(sys.argv) > 1 else None
    cases = [c for c in CASES if not wanted or c.name in wanted]
    if not cases:
        print(f"No matching cases. Available: {[c.name for c in CASES]}")
        return 2

    print(f"Running {len(cases)} eval case(s) against the live agent...\n")
    rows = []
    for case in cases:
        print(f"  → {case.name} ...", flush=True)
        rows.append(await run_case(case))

    print("\n" + "=" * 96)
    print(
        f"{'case':<22}{'status':<11}{'tools':<8}{'charts':<8}"
        f"{'ground':<8}{'qual':<6}{'cost$':<9}{'result'}"
    )
    print("-" * 96)
    total_cost = 0.0
    for r in rows:
        total_cost += r["cost_usd"]
        verdict = "PASS" if r["passed"] else "FAIL"
        print(
            f"{r['name']:<22}{r['status']:<11}{r['coverage'] * 100:>3.0f}%   "
            f"{r['charts']}/{r['min_charts']:<6}{r['grounding']:<8.2f}"
            f"{r['quality']:<6}{r['cost_usd']:<9.4f}{verdict}"
        )
        if not r["passed"]:
            detail = []
            if r["missing_tools"]:
                detail.append(f"missing tools: {r['missing_tools']}")
            if r["notes"]:
                detail.append(r["notes"])
            if detail:
                print(f"{'':<22}↳ {'; '.join(detail)}")
    print("-" * 96)
    n_pass = sum(r["passed"] for r in rows)
    print(f"{n_pass}/{len(rows)} passed   |   total eval cost: ${total_cost:.4f}")
    print("=" * 96)
    return 0 if n_pass == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
