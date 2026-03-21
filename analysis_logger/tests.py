# -*- coding: utf-8 -*-
"""
Tests for analysis_logger.service.

Uses tmp_path (pytest) so the real project log file is never touched.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

import analysis_logger.service as svc


# ---------------------------------------------------------------------------
# Fixtures: redirect LOG_FILE to a temp directory for every test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_log(tmp_path, monkeypatch):
    """Point the module's LOG_FILE and LOGS_DIR at a temp directory."""
    tmp_logs = tmp_path / "logs"
    tmp_file = tmp_logs / "analysis_logs.json"
    monkeypatch.setattr(svc, "LOGS_DIR", tmp_logs)
    monkeypatch.setattr(svc, "LOG_FILE", tmp_file)
    return tmp_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
_T1 = datetime(2026, 1, 1, 12, 0, 5, tzinfo=timezone.utc)


def _write_entry(project_id=1, **extra):
    svc.log_full_analysis(
        project_id=project_id,
        raster_path="/data/ortho.tif",
        start_time=_T0,
        end_time=_T1,
        ndvi_low=0.3,
        ndvi_high=0.5,
        min_area_ha=0.02,
        grid_size=10.0,
        yield_model_version="v1.0",
        success=True,
        **extra,
    )


# ---------------------------------------------------------------------------
# log_full_analysis
# ---------------------------------------------------------------------------

def test_log_creates_file(isolated_log):
    _write_entry()
    assert isolated_log.exists()


def test_log_creates_logs_dir(tmp_path, monkeypatch):
    new_dir = tmp_path / "new_logs"
    new_file = new_dir / "analysis_logs.json"
    monkeypatch.setattr(svc, "LOGS_DIR", new_dir)
    monkeypatch.setattr(svc, "LOG_FILE", new_file)
    _write_entry()
    assert new_dir.exists()


def test_log_entry_is_valid_json(isolated_log):
    _write_entry()
    line = isolated_log.read_text(encoding="utf-8").strip()
    data = json.loads(line)
    assert data["project_id"] == 1


def test_log_duration_computed_correctly(isolated_log):
    _write_entry()
    entry = json.loads(isolated_log.read_text(encoding="utf-8").strip())
    assert entry["duration_seconds"] == 5.0


def test_log_multiple_entries_appended(isolated_log):
    _write_entry(project_id=1)
    _write_entry(project_id=2)
    lines = [l for l in isolated_log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 2


def test_log_failure_entry_stores_error(isolated_log):
    svc.log_full_analysis(
        project_id=99,
        raster_path="/bad.tif",
        start_time=_T0,
        end_time=_T1,
        ndvi_low=0.3,
        ndvi_high=0.5,
        min_area_ha=0.02,
        grid_size=10.0,
        yield_model_version="v1.0",
        success=False,
        error_message="Something broke",
        stack_trace="Traceback ...",
    )
    entry = json.loads(isolated_log.read_text(encoding="utf-8").strip())
    assert entry["success"] is False
    assert entry["error_message"] == "Something broke"


# ---------------------------------------------------------------------------
# get_latest_analysis_data
# ---------------------------------------------------------------------------

def test_get_latest_returns_empty_when_no_file(isolated_log):
    result = svc.get_latest_analysis_data(project_id=1)
    assert result == {}


def test_get_latest_returns_correct_project(isolated_log):
    _write_entry(project_id=10)
    _write_entry(project_id=20)
    result = svc.get_latest_analysis_data(project_id=20)
    assert result["project_id"] == 20


def test_get_latest_returns_last_entry_for_project(isolated_log):
    svc.log_full_analysis(
        project_id=5,
        raster_path="/first.tif",
        start_time=_T0,
        end_time=_T1,
        ndvi_low=0.3,
        ndvi_high=0.5,
        min_area_ha=0.02,
        grid_size=10.0,
        yield_model_version="v1.0",
        success=True,
    )
    svc.log_full_analysis(
        project_id=5,
        raster_path="/second.tif",
        start_time=_T0,
        end_time=_T1,
        ndvi_low=0.3,
        ndvi_high=0.5,
        min_area_ha=0.02,
        grid_size=10.0,
        yield_model_version="v1.0",
        success=True,
    )
    result = svc.get_latest_analysis_data(project_id=5)
    assert result["raster_path"] == "/second.tif"


def test_get_latest_ignores_unknown_project(isolated_log):
    _write_entry(project_id=1)
    result = svc.get_latest_analysis_data(project_id=999)
    assert result == {}


def test_get_latest_skips_invalid_json_lines(isolated_log):
    # Write one valid and one garbage line
    _write_entry(project_id=7)
    with isolated_log.open("a", encoding="utf-8") as f:
        f.write("NOT JSON\n")
    # Should not raise
    result = svc.get_latest_analysis_data(project_id=7)
    assert result["project_id"] == 7


# ---------------------------------------------------------------------------
# _rotate_if_needed
# ---------------------------------------------------------------------------

def test_rotate_creates_dot1_file(isolated_log, monkeypatch):
    monkeypatch.setattr(svc, "LOG_MAX_BYTES", 5)  # trigger rotation at 5 bytes
    isolated_log.parent.mkdir(parents=True, exist_ok=True)
    isolated_log.write_text("x" * 10, encoding="utf-8")
    svc._rotate_if_needed()
    rotated = isolated_log.with_suffix(".json.1")
    assert rotated.exists()
    assert not isolated_log.exists()


def test_rotate_replaces_existing_dot1(isolated_log, monkeypatch):
    monkeypatch.setattr(svc, "LOG_MAX_BYTES", 5)
    isolated_log.parent.mkdir(parents=True, exist_ok=True)
    rotated = isolated_log.with_suffix(".json.1")
    rotated.write_text("old", encoding="utf-8")
    isolated_log.write_text("x" * 10, encoding="utf-8")
    svc._rotate_if_needed()
    assert rotated.read_text(encoding="utf-8") == "x" * 10


def test_no_rotate_when_file_small(isolated_log, monkeypatch):
    monkeypatch.setattr(svc, "LOG_MAX_BYTES", 1_000_000)
    isolated_log.parent.mkdir(parents=True, exist_ok=True)
    isolated_log.write_text("small", encoding="utf-8")
    svc._rotate_if_needed()
    assert isolated_log.exists()  # not rotated
