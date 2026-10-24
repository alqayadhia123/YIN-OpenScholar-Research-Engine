"""SQLite persistence for reproducible YIN search and audit runs."""
from __future__ import annotations
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("YIN_DB_PATH", str(Path(__file__).resolve().parent / "yin.sqlite3")))

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db() -> None:
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS search_runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_type TEXT NOT NULL,
            query TEXT NOT NULL,
            parameters_json TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            status TEXT NOT NULL,
            result_count INTEGER NOT NULL DEFAULT 0,
            report_markdown TEXT,
            synthesis_json TEXT,
            audit_json TEXT,
            error_type TEXT,
            error_message TEXT
        );
        CREATE TABLE IF NOT EXISTS papers (
            paper_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES search_runs(run_id) ON DELETE CASCADE,
            paper_id TEXT NOT NULL,
            doi TEXT,
            title TEXT,
            year INTEGER,
            source TEXT,
            metadata_json TEXT NOT NULL,
            UNIQUE(run_id, paper_id)
        );
        CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
        CREATE INDEX IF NOT EXISTS idx_runs_started ON search_runs(started_at DESC);
        CREATE TABLE IF NOT EXISTS audit_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER REFERENCES search_runs(run_id) ON DELETE SET NULL,
            event_time TEXT NOT NULL,
            level TEXT NOT NULL,
            event_type TEXT NOT NULL,
            message TEXT NOT NULL,
            details_json TEXT NOT NULL DEFAULT '{}'
        );
        """)

def _paper_id(paper: dict[str, Any], index: int) -> str:
    return str(paper.get("openalex_id") or paper.get("doi") or paper.get("paper_id") or f"record-{index}")

def save_run(*, run_type: str, query: str, parameters: dict[str, Any], papers: list[dict], status: str = "completed", report_markdown: str | None = None, synthesis: dict | None = None, audit: dict | None = None, error: Exception | None = None, started_at: str | None = None) -> int:
    started = started_at or utc_now()
    completed = utc_now()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO search_runs (run_type, query, parameters_json, started_at, completed_at, status, result_count, report_markdown, synthesis_json, audit_json, error_type, error_message) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run_type, query, json.dumps(parameters, ensure_ascii=False, sort_keys=True), started, completed, status, len(papers), report_markdown,
             json.dumps(synthesis, ensure_ascii=False) if synthesis is not None else None,
             json.dumps(audit, ensure_ascii=False) if audit is not None else None,
             type(error).__name__ if error else None, str(error)[:2000] if error else None))
        run_id = int(cur.lastrowid)
        for i, paper in enumerate(papers, 1):
            conn.execute(
                "INSERT OR IGNORE INTO papers (run_id, paper_id, doi, title, year, source, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (run_id, _paper_id(paper, i), paper.get("doi"), paper.get("title"), paper.get("year"), paper.get("source"), json.dumps(paper, ensure_ascii=False, sort_keys=True)))
        conn.execute("INSERT INTO audit_events (run_id, event_time, level, event_type, message, details_json) VALUES (?, ?, ?, ?, ?, ?)",
                     (run_id, completed, "ERROR" if error else "INFO", "run_completed" if not error else "run_failed", "Search/review run stored", json.dumps({"status": status, "result_count": len(papers)}, ensure_ascii=False)))
        return run_id

def log_event(level: str, event_type: str, message: str, details: dict | None = None, run_id: int | None = None) -> None:
    with connect() as conn:
        conn.execute("INSERT INTO audit_events (run_id, event_time, level, event_type, message, details_json) VALUES (?, ?, ?, ?, ?, ?)",
                     (run_id, utc_now(), level.upper(), event_type, message[:2000], json.dumps(details or {}, ensure_ascii=False, sort_keys=True)))

def list_runs(limit: int = 50) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT run_id, run_type, query, started_at, completed_at, status, result_count, error_type FROM search_runs ORDER BY run_id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

def get_run(run_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM search_runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["parameters"] = json.loads(result.pop("parameters_json"))
        result["synthesis"] = json.loads(result.pop("synthesis_json")) if result.get("synthesis_json") else None
        result["semantic_audit"] = json.loads(result.pop("audit_json")) if result.get("audit_json") else None
        result.pop("synthesis_json", None); result.pop("audit_json", None)
        result["papers"] = [json.loads(p[0]) for p in conn.execute("SELECT metadata_json FROM papers WHERE run_id = ? ORDER BY paper_row_id", (run_id,)).fetchall()]
        result["events"] = [dict(e) for e in conn.execute("SELECT event_time, level, event_type, message, details_json FROM audit_events WHERE run_id = ? ORDER BY event_id", (run_id,)).fetchall()]
        for event in result["events"]:
            event["details"] = json.loads(event.pop("details_json"))
        return result
