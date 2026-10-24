import re
import requests
from urllib.parse import quote

OPENALEX = "https://api.openalex.org/works"
CROSSREF = "https://api.crossref.org/works/"
TIMEOUT = 25
HEADERS = {"User-Agent": "YIN-Research-Engine/0.1 (academic literature discovery)"}

def _abstract_from_inverted_index(inv):
    if not isinstance(inv, dict):
        return None
    positions = []
    for word, offsets in inv.items():
        for offset in offsets:
            positions.append((offset, word))
    if not positions:
        return None
    return " ".join(word for _, word in sorted(positions))

def search_literature(query, limit=10, year_from=None, year_to=None, open_access_only=False):
    params = {"search": query, "per-page": limit, "sort": "relevance_score:desc"}
    filters = []
    if year_from:
        filters.append(f"from_publication_date:{year_from}-01-01")
    if year_to:
        filters.append(f"to_publication_date:{year_to}-12-31")
    if open_access_only:
        filters.append("is_oa:true")
    if filters:
        params["filter"] = ",".join(filters)
    response = requests.get(OPENALEX, params=params, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    papers = []
    for item in payload.get("results", []):
        authorships = item.get("authorships") or []
        authors = []
        for a in authorships[:12]:
            author = (a.get("author") or {}).get("display_name")
            if author:
                authors.append(author)
        doi = item.get("doi")
        doi = doi.replace("https://doi.org/", "") if doi else None
        oa = item.get("open_access") or {}
        loc = item.get("primary_location") or {}
        source = loc.get("source") or {}
        papers.append({
            "title": item.get("title"),
            "year": item.get("publication_year"),
            "authors": authors,
            "doi": doi,
            "doi_url": f"https://doi.org/{doi}" if doi else None,
            "openalex_id": item.get("id"),
            "abstract": _abstract_from_inverted_index(item.get("abstract_inverted_index")),
            "journal": source.get("display_name"),
            "landing_page": loc.get("landing_page_url"),
            "open_access": bool(oa.get("is_oa")),
            "oa_url": oa.get("oa_url"),
            "cited_by_count": item.get("cited_by_count"),
            "source": "OpenAlex"
        })
    return papers

def verify_doi(doi):
    cleaned = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip(), flags=re.I)
    if not re.match(r"^10\.\d{4,9}/\S+$", cleaned):
        return {"input": doi, "verified": False, "reason": "Input does not match a basic DOI pattern."}
    r = requests.get(CROSSREF + quote(cleaned, safe="/"), headers=HEADERS, timeout=TIMEOUT)
    if r.status_code == 404:
        return {"input": doi, "doi": cleaned, "verified": False, "reason": "DOI not found in Crossref. It may exist in another registration agency."}
    r.raise_for_status()
    msg = r.json().get("message", {})
    return {"input": doi, "doi": cleaned, "verified": True,
            "title": (msg.get("title") or [None])[0],
            "authors": [a.get("family", "") + (", " + a.get("given", "") if a.get("given") else "") for a in msg.get("author", [])[:12]],
            "published": msg.get("published-print") or msg.get("published-online") or msg.get("created"),
            "container_title": (msg.get("container-title") or [None])[0],
            "publisher": msg.get("publisher"), "url": msg.get("URL"),
            "note": "Crossref metadata resolution confirms a Crossref record, not the validity of claims in the paper."}

def build_evidence_report(query, papers):
    lines = [f"# YIN literature discovery report", "", f"**Query:** {query}", "",
             f"**Records retrieved:** {len(papers)}", "",
             "> Discovery report only. This is not a completed systematic review, quality appraisal, or verified synthesis of full-text findings.", "",
             "## Retrieved records", ""]
    for i, p in enumerate(papers, 1):
        authors = ", ".join(p.get("authors") or []) or "Author metadata unavailable"
        lines += [f"### [{i}] {p.get('title') or 'Title unavailable'}",
                  f"- **Authors:** {authors}",
                  f"- **Year:** {p.get('year') or 'Not supplied'}",
                  f"- **Journal/source:** {p.get('journal') or 'Not supplied'}",
                  f"- **DOI:** {('https://doi.org/' + p['doi']) if p.get('doi') else 'No DOI supplied by provider'}",
                  f"- **Open access:** {'Yes' if p.get('open_access') else 'Not marked open access'}",
                  f"- **Landing page:** {p.get('landing_page') or 'Not supplied'}",
                  f"- **Abstract:** {p.get('abstract') or 'Abstract not available in provider metadata'}", ""]
    lines += ["## Required human checks", "",
              "1. Open the original publication and confirm the title, authors, year, and DOI.",
              "2. Read the full text where available; do not infer results from title or abstract alone.",
              "3. Screen records against pre-specified inclusion/exclusion criteria.",
              "4. Extract methods, sample, measures, findings, limitations, and risk of bias into a separate evidence table.",
              "5. Verify every claim-citation link before using this report in academic writing.", ""]
    return "\n".join(lines)
