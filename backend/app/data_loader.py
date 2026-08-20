"""Robust, cached CSV loading.

The agent calls several tools per analysis, each of which needs the DataFrame.
Re-reading the file every time is wasteful, so we load once and cache (bounded
LRU). Loading is defensive: it sniffs encoding and delimiter, enforces a hard
row cap, and randomly samples very large files to bound memory and latency.
"""

from __future__ import annotations

import csv
from collections import OrderedDict
from typing import Any

import pandas as pd

from app.config import settings

# Bounded LRU cache: file_path -> (DataFrame, meta). One entry per job file.
_CACHE: OrderedDict[str, tuple[pd.DataFrame, dict[str, Any]]] = OrderedDict()
_CACHE_MAX = 8

_SAMPLE_SEED = 42


def _detect_encoding_and_sample(path: str) -> tuple[str, str]:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            with open(path, encoding=enc, newline="") as f:
                return enc, f.read(65536)
        except UnicodeDecodeError:
            continue
    return "latin-1", ""


def _sniff_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def load_df(path: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Return (DataFrame, meta) for a CSV, loading and caching on first use.

    Raises ValueError with an actionable message on unreadable/oversized files.
    """
    if path in _CACHE:
        _CACHE.move_to_end(path)
        return _CACHE[path]

    encoding, sample = _detect_encoding_and_sample(path)
    delimiter = _sniff_delimiter(sample)

    try:
        df = pd.read_csv(path, sep=delimiter, encoding=encoding)
    except pd.errors.EmptyDataError as e:
        raise ValueError("The CSV file is empty or has no parseable columns.") from e
    except Exception as e:  # noqa: BLE001 — surface a clean message to the agent
        raise ValueError(f"Could not parse CSV: {e}") from e

    if df.shape[1] == 0 or df.empty:
        raise ValueError("The CSV file has no rows or columns to analyze.")

    original_rows = int(len(df))
    if original_rows > settings.max_rows:
        raise ValueError(
            f"CSV has {original_rows:,} rows, above the limit of "
            f"{settings.max_rows:,}. Reduce the file and retry."
        )

    sampled = False
    if original_rows > settings.sample_over_rows:
        df = df.sample(settings.sample_over_rows, random_state=_SAMPLE_SEED).reset_index(drop=True)
        sampled = True

    meta = {
        "encoding": encoding,
        "delimiter": delimiter,
        "original_rows": original_rows,
        "analyzed_rows": int(len(df)),
        "sampled": sampled,
    }

    _CACHE[path] = (df, meta)
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)
    return df, meta


def evict(path: str) -> None:
    """Drop a file from the cache (e.g. after the upload is deleted)."""
    _CACHE.pop(path, None)
