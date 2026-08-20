"""LLM-as-judge: score a generated report for grounding and quality.

The judge receives ground-truth facts (computed by our deterministic tools) and
the agent's report, and returns a structured score. Using an independent model
call to grade avoids marking our own homework by string-matching.
"""

import json
import re

import anthropic

from app.config import settings

_JUDGE_PROMPT = """You are a strict evaluator of data-analysis reports.

You are given VERIFIED ground-truth facts about a dataset (computed by trusted
code) and a REPORT written by an AI agent. Judge the report.

VERIFIED GROUND TRUTH:
{ground_truth}

REPORT:
{report}

Score on two axes and respond with ONLY a JSON object, no prose:
{{
  "grounding": <float 0..1>,   // Are the report's quantitative claims CONSISTENT
                               // with the ground truth? 1.0 = fully consistent,
                               // 0.0 = contradicts the facts or invents numbers.
  "quality":   <int 1..5>,     // Clarity, insight, and actionability of the report.
  "notes":     "<one sentence>"
}}"""


def _parse_json(text: str) -> dict:
    # Tolerate code fences or surrounding prose.
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"Judge returned no JSON: {text[:200]}")
    return json.loads(m.group(0))


async def judge_report(ground_truth: str, report: str) -> dict:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    resp = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=400,
        messages=[
            {
                "role": "user",
                "content": _JUDGE_PROMPT.format(ground_truth=ground_truth, report=report),
            }
        ],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    data = _parse_json(text)
    return {
        "grounding": float(data.get("grounding", 0.0)),
        "quality": int(data.get("quality", 0)),
        "notes": str(data.get("notes", "")),
    }
