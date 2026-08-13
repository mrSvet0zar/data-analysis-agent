"""Concrete implementations of every agent tool.

Each handler receives `file_path` (injected by the agent, never chosen by the
model) plus the model-provided arguments, and returns a JSON-serializable dict.
All handlers are defensive: any exception is returned as ``{"success": False,
"error": ...}`` so a single bad tool call never crashes the agent loop.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.config import settings


def _clean(obj):
    """Recursively convert numpy/pandas scalars to native Python and replace
    NaN/inf with None so the result survives ``json.dumps`` and JS parsing."""
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        obj = float(obj)
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return _clean(obj.tolist())
    return obj


def _load(file_path: str) -> pd.DataFrame:
    return pd.read_csv(file_path)


class DataAnalysisTools:
    @staticmethod
    def read_csv(file_path: str) -> dict:
        try:
            df = _load(file_path)
            return _clean(
                {
                    "success": True,
                    "shape": {"rows": df.shape[0], "columns": df.shape[1]},
                    "columns": df.columns.tolist(),
                    "dtypes": {c: str(t) for c, t in df.dtypes.items()},
                    "numeric_columns": df.select_dtypes(include=[np.number]).columns.tolist(),
                    "missing_values": df.isnull().sum().to_dict(),
                    "head": df.head(5).to_dict(orient="records"),
                }
            )
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def describe_statistics(file_path: str, columns: list | None = None) -> dict:
        try:
            df = _load(file_path)
            numeric = df.select_dtypes(include=[np.number])
            if columns:
                keep = [c for c in columns if c in numeric.columns]
                if not keep:
                    return {
                        "success": False,
                        "error": f"None of {columns} are numeric columns. "
                        f"Numeric columns: {numeric.columns.tolist()}",
                    }
                numeric = numeric[keep]
            if numeric.empty:
                return {"success": False, "error": "No numeric columns to describe."}

            stats = numeric.describe().to_dict()
            for col in numeric.columns:
                stats[col]["skewness"] = float(numeric[col].skew())
                stats[col]["kurtosis"] = float(numeric[col].kurtosis())
            return _clean({"success": True, "statistics": stats})
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def detect_outliers(file_path: str, method: str = "iqr", column: str | None = None) -> dict:
        try:
            df = _load(file_path)
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if not numeric_cols:
                return {"success": False, "error": "No numeric column found."}
            if not column or column not in df.columns:
                column = numeric_cols[0]

            series = df[column].dropna()
            if series.empty:
                return {"success": False, "error": f"Column '{column}' has no numeric data."}

            if method == "zscore":
                std = series.std()
                if std == 0:
                    mask = pd.Series(False, index=df.index)
                else:
                    z = (df[column] - series.mean()) / std
                    mask = z.abs() > 3
            else:  # iqr (default)
                q1, q3 = series.quantile(0.25), series.quantile(0.75)
                iqr = q3 - q1
                lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
                mask = (df[column] < lower) | (df[column] > upper)

            outliers = df[mask.fillna(False)]
            total = len(df)
            return _clean(
                {
                    "success": True,
                    "column": column,
                    "method": method,
                    "outlier_count": int(len(outliers)),
                    "percentage": round(len(outliers) / total * 100, 2) if total else 0,
                    "sample_outlier_values": outliers[column].tolist()[:10],
                }
            )
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def correlation_analysis(file_path: str) -> dict:
        try:
            df = _load(file_path)
            numeric = df.select_dtypes(include=[np.number])
            if numeric.shape[1] < 2:
                return {
                    "success": False,
                    "error": "Need at least two numeric columns for correlation.",
                }
            corr = numeric.corr()
            matrix = corr.to_dict()

            pairs = []
            cols = numeric.columns.tolist()
            for i, c1 in enumerate(cols):
                for c2 in cols[i + 1:]:
                    r = corr.loc[c1, c2]
                    if pd.notna(r) and abs(r) > 0.5:
                        pairs.append({"column1": c1, "column2": c2, "correlation": float(r)})
            pairs.sort(key=lambda p: abs(p["correlation"]), reverse=True)
            return _clean(
                {
                    "success": True,
                    "correlation_matrix": matrix,
                    "strong_correlations": pairs,
                }
            )
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def create_visualization(
        file_path: str,
        chart_type: str,
        x_column: str | None = None,
        y_column: str | None = None,
        title: str = "Chart",
    ) -> dict:
        try:
            df = _load(file_path)

            def require(col: str, label: str):
                if not col or col not in df.columns:
                    raise ValueError(
                        f"{label} '{col}' not found. Available columns: {df.columns.tolist()}"
                    )

            if chart_type == "histogram":
                require(x_column, "x_column")
                fig = px.histogram(df, x=x_column, title=title)
            elif chart_type == "scatter":
                require(x_column, "x_column")
                require(y_column, "y_column")
                fig = px.scatter(df, x=x_column, y=y_column, title=title)
            elif chart_type == "boxplot":
                require(x_column, "x_column")
                fig = px.box(df, y=x_column, title=title)
            elif chart_type == "timeseries":
                require(x_column, "x_column")
                require(y_column, "y_column")
                fig = px.line(df, x=x_column, y=y_column, title=title)
            elif chart_type == "heatmap":
                numeric = df.select_dtypes(include=[np.number])
                if numeric.shape[1] < 2:
                    raise ValueError("Heatmap needs at least two numeric columns.")
                corr = numeric.corr()
                fig = go.Figure(
                    data=go.Heatmap(
                        z=corr.values,
                        x=corr.columns.tolist(),
                        y=corr.columns.tolist(),
                        colorscale="RdBu",
                        zmid=0,
                    )
                )
                fig.update_layout(title=title)
            else:
                return {"success": False, "error": f"Unknown chart_type: {chart_type}"}

            fig.update_layout(template="plotly_white", margin=dict(l=40, r=20, t=50, b=40))

            # Persist an HTML copy for reference and return Plotly JSON for the frontend.
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:60]
            out_path = settings.OUTPUT_DIR / f"{safe or 'chart'}.html"
            fig.write_html(out_path)

            return {
                "success": True,
                "chart_type": chart_type,
                "title": title,
                "chart_path": str(out_path),
                "plotly_json": json.loads(fig.to_json()),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def generate_report(title: str, findings: list) -> dict:
        try:
            lines = [
                f"# {title}",
                "",
                "_Generated automatically by the AI Data-Analysis Agent._",
                "",
                "## Key Findings",
                "",
            ]
            for i, finding in enumerate(findings, 1):
                lines.append(f"### {i}. {finding}")
                lines.append("")
            lines.append("---")
            lines.append("*This report was produced by an autonomous agent using tool calls.*")
            markdown = "\n".join(lines)

            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:60]
            report_path = settings.OUTPUT_DIR / f"{safe or 'report'}_report.md"
            Path(report_path).write_text(markdown, encoding="utf-8")

            return {"success": True, "report_path": str(report_path), "report": markdown}
        except Exception as e:
            return {"success": False, "error": str(e)}
