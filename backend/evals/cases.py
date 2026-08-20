"""Golden evaluation cases for the agent.

Each case is a dataset + request with expectations about the agent's behavior.
Ground truth for factual grounding is NOT hard-coded here — it is computed at
run time by our own deterministic tools (see run.py), so the judge checks the
agent's narrative against real numbers.
"""

from dataclasses import dataclass, field
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent


@dataclass
class EvalCase:
    name: str
    csv_path: str
    request: str
    # Tools we expect a competent agent to use on this dataset.
    expected_tools: set[str] = field(default_factory=set)
    min_charts: int = 1
    # A numeric column with a known, blatant outlier (for grounding checks).
    key_outlier_column: str | None = None


CASES: list[EvalCase] = [
    EvalCase(
        name="strong_corr_outlier",
        csv_path=str(BACKEND / "evals/golden/strong_corr_outlier.csv"),
        request="Analyze this dataset: find correlations and anomalies.",
        expected_tools={
            "read_csv",
            "correlation_analysis",
            "detect_outliers",
            "create_visualization",
            "generate_report",
        },
        min_charts=1,
        key_outlier_column="z",
    ),
    EvalCase(
        name="sales",
        csv_path=str(BACKEND / "sample_data/sales.csv"),
        request="Analyze this data and surface the key insights.",
        expected_tools={
            "read_csv",
            "correlation_analysis",
            "create_visualization",
            "generate_report",
        },
        min_charts=2,
        key_outlier_column="revenue",
    ),
    EvalCase(
        name="employees",
        csv_path=str(BACKEND / "sample_data/employees.csv"),
        request="Summarize data quality and relationships between columns.",
        expected_tools={"read_csv", "describe_statistics", "generate_report"},
        min_charts=1,
        key_outlier_column=None,
    ),
]
