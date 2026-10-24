"""YIN Research Engine API — local MVP with reproducible SQLite run storage."""
import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, model_validator
from engine import search_literature, build_evidence_report, verify_doi
from openscholar_adapter import synthesize_with_openscholar
from reference_export import export_bibtex, export_ris, export_apa7
from storage import init_db, save_run, list_runs, get_run, log_event
from verification_layer import run_full_audit

APP_VERSION = "0.4.0"
app = FastAPI(title="YIN Research Engine", version=APP_VERSION,
              description="Evidence-first literature discovery, optional synthesis, claim-audit plumbing, reference export, and SQLite run history.")
init_db()

class SearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    limit: int = Field(default=10, ge=1, le=25)
    year_from: Optional[int] = Field(default=None, ge=1900, le=2100)
    year_to: Optional[int] = Field(default=None, ge=1900, le=2100)
    open_access_only: bool = False

    @model_validator(mode="after")
    def validate_year_range(self):
        if self.year_from is not None and self.year_to is not None and self.year_from > self.year_to:
            raise ValueError("year_from must be less than or equal to year_to")
        return self

class SynthesisRequest(SearchRequest):
    include_synthesis: bool = False
    run_semantic_audit: bool = False
    export_references: bool = False

class ExportRequest(BaseModel):
    papers: list[dict] = Field(min_length=1, max_length=500)

@app.get("/health")
def health():
    return {"status": "ok", "version": APP_VERSION,
            "openscholar_bridge_configured": bool(os.getenv("YIN_OPENSCHOLAR_BRIDGE_URL")),
            "semantic_audit_configured": all(os.getenv(k) for k in ("YIN_LLM_BASE_URL", "YIN_LLM_API_KEY", "YIN_LLM_MODEL")),
            "storage": "sqlite", "database_path": os.getenv("YIN_DB_PATH", "./yin.sqlite3")}

@app.post("/search")
def search(req: SearchRequest):
    try:
        papers = search_literature(req.query, req.limit, req.year_from, req.year_to, req.open_access_only)
        params = req.model_dump()
        run_id = save_run(run_type="search", query=req.query, parameters=params, papers=papers)
        return {"run_id": run_id, "query": req.query, "count": len(papers), "papers": papers,
                "notice": "Metadata retrieval is not a systematic-review search and does not establish study quality."}
    except Exception as e:
        try:
            log_event("ERROR", "search_failed", f"Search failed: {type(e).__name__}: {e}", {"query": req.query})
        except Exception:
            pass
        if isinstance(e, HTTPException): raise
        raise HTTPException(status_code=502, detail=f"Literature provider or persistence error: {type(e).__name__}: {e}")

@app.post("/verify-doi")
def verify(doi: str = Query(min_length=5, max_length=300)):
    try:
        result = verify_doi(doi)
        log_event("INFO", "doi_check", "Crossref DOI metadata check completed", {"doi": doi, "verified": result.get("verified")})
        return result
    except Exception as e:
        log_event("ERROR", "doi_check_failed", f"DOI check failed: {type(e).__name__}: {e}", {"doi": doi})
        raise HTTPException(status_code=502, detail=f"DOI provider error: {type(e).__name__}: {e}")

@app.post("/review")
def review(req: SynthesisRequest):
    try:
        papers = search_literature(req.query, req.limit, req.year_from, req.year_to, req.open_access_only)
    except Exception as e:
        log_event("ERROR", "review_search_failed", f"Review search failed: {type(e).__name__}: {e}", {"query": req.query})
        raise HTTPException(status_code=502, detail=f"Literature provider error: {type(e).__name__}: {e}")
    report = build_evidence_report(req.query, papers) if papers else "# No records retrieved\n\nBroaden or revise the query. No literature synthesis was generated."
    synthesis = None
    if req.include_synthesis and papers:
        try:
            synthesis = synthesize_with_openscholar(req.query, papers)
        except RuntimeError as e:
            synthesis = {"status": "not_run", "reason": str(e)}
    semantic_audit = None
    if req.run_semantic_audit:
        if synthesis and synthesis.get("status") == "completed" and synthesis.get("answer"):
            semantic_audit = run_full_audit(synthesis["answer"], papers)
        else:
            semantic_audit = {"status": "not_run", "reason": "No completed synthesis draft is available to audit. Enable synthesis and configure its bridge first."}
    exports = {}
    if req.export_references and papers:
        exports = {"bibtex": export_bibtex(papers), "ris": export_ris(papers), "apa7": export_apa7(papers)}
    try:
        run_id = save_run(run_type="review", query=req.query, parameters=req.model_dump(), papers=papers,
                          report_markdown=report, synthesis=synthesis, audit=semantic_audit,
                          status="completed" if papers else "no_records")
    except Exception as e:
        log_event("ERROR", "review_persist_failed", f"Review persistence failed: {type(e).__name__}: {e}", {"query": req.query})
        raise HTTPException(status_code=500, detail="Review completed but could not be persisted to SQLite.")
    return {"run_id": run_id, "query": req.query, "count": len(papers), "papers": papers,
            "report_markdown": report, "synthesis": synthesis, "semantic_audit": semantic_audit,
            "reference_exports": exports,
            "limitations": ["Search coverage depends on provider indexing and query wording.",
                            "Metadata and DOI checks do not verify the truth of a paper's findings.",
                            "Semantic audit uses LLM-as-a-judge when configured; it is not a validated NLI classifier.",
                            "Human screening and source-level checking are required before academic citation."]}

@app.post("/export/{format_name}")
def export_references(format_name: str, request: ExportRequest):
    exporters = {
        "bibtex": (export_bibtex, "application/x-bibtex; charset=utf-8", "references.bib"),
        "ris": (export_ris, "application/x-research-info-systems; charset=utf-8", "references.ris"),
        "apa7": (export_apa7, "text/plain; charset=utf-8", "references_apa7.txt"),
    }
    if format_name not in exporters:
        raise HTTPException(status_code=400, detail="Supported formats: bibtex, ris, apa7")
    try:
        content = exporters[format_name][0](request.papers)
    except (ValueError, TypeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"Invalid bibliographic input: {type(e).__name__}")
    if not content.strip(): raise HTTPException(status_code=422, detail="No exportable references found")
    return PlainTextResponse(content=content, media_type=exporters[format_name][1],
        headers={"Content-Disposition": f'attachment; filename="{exporters[format_name][2]}"'})

@app.get("/runs")
def runs(limit: int = Query(default=50, ge=1, le=200)):
    return {"count": len(list_runs(limit)), "runs": list_runs(limit)}

@app.get("/runs/{run_id}")
def run_detail(run_id: int):
    result = get_run(run_id)
    if result is None: raise HTTPException(status_code=404, detail="Run not found")
    return result
