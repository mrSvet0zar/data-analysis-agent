"""Tool definitions exposed to Claude for the data-analysis agent.

Each Tool describes its JSON schema in Claude's `tools` format. Only the fields
listed in `required` are mandatory; optional parameters (e.g. a column filter)
are omitted so the model isn't forced to invent values.
"""
from typing import Callable, Optional


class Tool:
    def __init__(
        self,
        name: str,
        description: str,
        properties: dict,
        required: Optional[list[str]] = None,
    ):
        self.name = name
        self.description = description
        self.properties = properties
        self.required = required if required is not None else list(properties.keys())

    def to_dict(self) -> dict:
        """Convert to the schema Claude's Messages API expects."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": self.properties,
                "required": self.required,
            },
        }


TOOLS: list[Tool] = [
    Tool(
        name="read_csv",
        description=(
            "Load the uploaded CSV and return its structure: shape, column names, "
            "dtypes, missing-value counts, and a small preview. Always call this "
            "first to understand the dataset before any other analysis."
        ),
        properties={},  # file_path is injected by the agent, not chosen by the model
        required=[],
    ),
    Tool(
        name="describe_statistics",
        description=(
            "Compute descriptive statistics (count, mean, std, min, quartiles, max, "
            "plus skewness and kurtosis) for numeric columns. Leave `columns` empty "
            "to analyze every numeric column."
        ),
        properties={
            "columns": {
                "type": "array",
                "description": "Specific column names to analyze. Empty = all numeric columns.",
                "items": {"type": "string"},
            }
        },
        required=[],
    ),
    Tool(
        name="detect_outliers",
        description=(
            "Detect outliers in a single numeric column using the IQR (1.5×IQR "
            "fences) or Z-score (|z|>3) method. If `column` is omitted, the first "
            "numeric column is used."
        ),
        properties={
            "method": {
                "type": "string",
                "enum": ["iqr", "zscore"],
                "description": "Outlier detection method.",
            },
            "column": {
                "type": "string",
                "description": "Numeric column to inspect.",
            },
        },
        required=["method"],
    ),
    Tool(
        name="correlation_analysis",
        description=(
            "Compute the Pearson correlation matrix across numeric columns and "
            "surface the strongest pairwise correlations (|r| > 0.5)."
        ),
        properties={},
        required=[],
    ),
    Tool(
        name="create_visualization",
        description=(
            "Generate an interactive Plotly chart and return it as JSON the frontend "
            "can render. Supported: histogram, scatter, heatmap (correlation), "
            "boxplot, timeseries. Provide the relevant columns for the chart type."
        ),
        properties={
            "chart_type": {
                "type": "string",
                "enum": ["histogram", "scatter", "heatmap", "timeseries", "boxplot"],
                "description": "Type of chart to build.",
            },
            "x_column": {
                "type": "string",
                "description": "Column for the X axis (or the value column for histogram/boxplot). Not needed for heatmap.",
            },
            "y_column": {
                "type": "string",
                "description": "Column for the Y axis. Required for scatter and timeseries.",
            },
            "title": {
                "type": "string",
                "description": "Human-readable chart title.",
            },
        },
        required=["chart_type", "title"],
    ),
    Tool(
        name="generate_report",
        description=(
            "Compile the analysis into a final markdown report. Call this LAST, once "
            "you have gathered enough findings, then end your turn with a short summary."
        ),
        properties={
            "title": {
                "type": "string",
                "description": "Report title.",
            },
            "findings": {
                "type": "array",
                "description": "Ordered list of key findings, each a concise paragraph.",
                "items": {"type": "string"},
            },
        },
        required=["title", "findings"],
    ),
]


def get_tools_for_claude() -> list[dict]:
    """Format all tools for the Claude Messages API `tools` parameter."""
    return [tool.to_dict() for tool in TOOLS]
