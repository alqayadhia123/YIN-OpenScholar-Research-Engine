import os
import storage
import app as app_module
from fastapi.testclient import TestClient

PAPERS = [{"title":"Sample paper", "authors":["Smith, John"], "year":2024, "doi":"10.1234/sample", "openalex_id":"https://openalex.org/W1", "abstract":"Sample abstract", "journal":"Journal", "source":"OpenAlex"}]

def setup_db(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "test.sqlite3")
    storage.init_db()

def test_save_and_retrieve_run(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    run_id=storage.save_run(run_type="search", query="sample query", parameters={"limit":1}, papers=PAPERS)
    result=storage.get_run(run_id)
    assert result is not None
    assert result["query"] == "sample query"
    assert result["papers"][0]["title"] == "Sample paper"
    assert storage.list_runs(10)[0]["run_id"] == run_id

def test_search_api_persists_results(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    monkeypatch.setattr(app_module, "search_literature", lambda *args, **kwargs: PAPERS)
    client=TestClient(app_module.app)
    response=client.post("/search", json={"query":"sample query", "limit":1})
    assert response.status_code == 200, response.text
    body=response.json()
    assert body["count"] == 1
    assert storage.get_run(body["run_id"])["papers"][0]["doi"] == "10.1234/sample"

def test_export_endpoint_rejects_unknown_format():
    client=TestClient(app_module.app)
    response=client.post("/export/unknown", json={"papers":PAPERS})
    assert response.status_code == 400

def test_audit_is_explicitly_not_configured_without_credentials(monkeypatch):
    for key in ("YIN_LLM_BASE_URL","YIN_LLM_API_KEY","YIN_LLM_MODEL"):
        monkeypatch.delenv(key, raising=False)
    import verification_layer
    monkeypatch.setattr(verification_layer, "BASE_URL", "")
    monkeypatch.setattr(verification_layer, "API_KEY", "")
    monkeypatch.setattr(verification_layer, "MODEL", "")
    result=verification_layer.run_full_audit("A factual claim.", PAPERS)
    assert result["status"] == "not_configured"
    assert "detailed_audit" in result

def test_review_endpoint_returns_exports_and_persists_run(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    monkeypatch.setattr(app_module, "search_literature", lambda *args, **kwargs: PAPERS)
    client=TestClient(app_module.app)
    response=client.post("/review", json={"query":"sample query", "limit":1, "export_references":True})
    assert response.status_code == 200, response.text
    body=response.json()
    assert body["reference_exports"]["bibtex"].startswith("@article{")
    saved=storage.get_run(body["run_id"])
    assert saved is not None and saved["run_type"] == "review"
    assert saved["report_markdown"]

def test_export_endpoint_returns_downloadable_content():
    client=TestClient(app_module.app)
    response=client.post("/export/ris", json={"papers":PAPERS})
    assert response.status_code == 200, response.text
    assert "attachment; filename=\"references.ris\"" in response.headers.get("content-disposition", "")
    assert "TY  - JOUR" in response.text
