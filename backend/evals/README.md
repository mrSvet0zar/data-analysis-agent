# Agent evaluations

Unit tests prove the *plumbing* works. These evals prove the *agent* works —
that it reliably selects the right tools and produces grounded, useful reports.
They run the real agent against Claude, so they cost tokens and are **not** part
of the fast CI; run them before a release or when changing the prompt/model.

## Run

```bash
cd backend
venv/Scripts/python -m evals.run            # all cases
venv/Scripts/python -m evals.run sales      # a single case
```

Exit code is non-zero if any case fails its thresholds, so it can gate a release.

## What each case measures

| Metric | How | Pass threshold |
|--------|-----|----------------|
| **Completion** | agent reaches `completed` | required |
| **Tool coverage** | expected tools ⊆ tools actually called | 100% |
| **Charts** | number of visualizations produced | ≥ case minimum |
| **Grounding** | LLM-as-judge checks the report's numbers against ground truth **computed by our own deterministic tools** | ≥ 0.80 |
| **Quality** | LLM-as-judge rates clarity/insight/actionability 1–5 | ≥ 3 |

Ground truth is not hard-coded — `run.py` recomputes correlations and outliers
with the trusted handlers and hands those facts to the judge, so we never grade
the agent by string-matching its own output.

## Cases (`cases.py`)

- **strong_corr_outlier** — synthetic golden set (`golden/`) with a designed
  strong x–y correlation and one blatant outlier in `z`.
- **sales** / **employees** — the shipped sample datasets.

Add a case by appending an `EvalCase` to `CASES`.
