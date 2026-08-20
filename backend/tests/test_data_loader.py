"""Tests for robust, cached CSV loading."""

import pytest

from app import data_loader
from app.config import settings


def test_loads_and_reports_meta(sales_csv):
    df, meta = data_loader.load_df(sales_csv)
    assert df.shape[0] == 300
    assert meta["delimiter"] == ","
    assert meta["encoding"] in ("utf-8", "utf-8-sig")
    assert meta["sampled"] is False
    assert meta["original_rows"] == 300


def test_cache_returns_same_object(sales_csv):
    df1, _ = data_loader.load_df(sales_csv)
    df2, _ = data_loader.load_df(sales_csv)
    assert df1 is df2  # served from cache, not re-read


def test_sniffs_semicolon_delimiter(semicolon_csv):
    df, meta = data_loader.load_df(semicolon_csv)
    assert meta["delimiter"] == ";"
    assert list(df.columns) == ["a", "b", "c"]


def test_row_cap_raises(tmp_csv, monkeypatch):
    data_loader.evict(tmp_csv)
    monkeypatch.setattr(settings, "max_rows", 1)
    with pytest.raises(ValueError, match="above the limit"):
        data_loader.load_df(tmp_csv)


def test_samples_large_files(tmp_csv, monkeypatch):
    data_loader.evict(tmp_csv)
    monkeypatch.setattr(settings, "sample_over_rows", 2)
    df, meta = data_loader.load_df(tmp_csv)
    assert meta["sampled"] is True
    assert meta["analyzed_rows"] == 2
    assert meta["original_rows"] == 3
