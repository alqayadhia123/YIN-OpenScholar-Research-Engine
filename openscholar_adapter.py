"""
Optional bridge to a separately deployed OpenScholar-compatible HTTP wrapper.

This deliberately does not pretend the upstream OpenScholar repository exposes a
stable public HTTP API. Set YIN_OPENSCHOLAR_BRIDGE_URL only after deploying a
wrapper around the official OpenScholar inference code and matching this contract.

POST JSON:
{
  "query": "...",
  "papers": [{"title": "...", "year": 2024, "doi": "...", "abstract": "..."}]
}
Expected response JSON:
{"answer": "...", "citations": [{"doi": "...", "claim": "..."}]}

The bridge is optional. Search and evidence-report generation work without it.
"""
import os
import requests

def synthesize_with_openscholar(query, papers):
    url = os.getenv("YIN_OPENSCHOLAR_BRIDGE_URL")
    if not url:
        raise RuntimeError(
            "OpenScholar bridge is not configured. Set YIN_OPENSCHOLAR_BRIDGE_URL to a deployed "
            "wrapper around the official OpenScholar inference pipeline. See README.md; no synthesis was generated."
        )
    payload = {"query": query, "papers": [
        {k: p.get(k) for k in ("title", "year", "doi", "abstract", "journal", "landing_page")}
        for p in papers
    ]}
    try:
        response = requests.post(url, json=payload, timeout=180)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        raise RuntimeError(f"OpenScholar bridge request failed: {type(e).__name__}: {e}") from e
    if not isinstance(data, dict) or not isinstance(data.get("answer"), str):
        raise RuntimeError("Bridge response did not match the required schema: expected a JSON object with string field 'answer'.")
    return {"status": "completed", "answer": data["answer"],
            "citations": data.get("citations", []),
            "warning": "Treat model output as a draft. Verify every citation and claim against the original paper."}
