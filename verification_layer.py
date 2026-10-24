"""Optional LLM-assisted claim audit. No semantic result is fabricated when unconfigured."""
from __future__ import annotations
import json, os, re
from typing import Any
import requests

BASE_URL = os.getenv('YIN_LLM_BASE_URL', '').rstrip('/')
API_KEY = os.getenv('YIN_LLM_API_KEY', '')
MODEL = os.getenv('YIN_LLM_MODEL', '')
TIMEOUT = float(os.getenv('YIN_LLM_TIMEOUT', '60'))

class AuditNotConfigured(RuntimeError): pass

def _call_llm(system_prompt: str, user_content: str) -> dict[str, Any]:
    if not (BASE_URL and API_KEY and MODEL):
        raise AuditNotConfigured('Semantic audit is not configured. Set YIN_LLM_BASE_URL, YIN_LLM_API_KEY, and YIN_LLM_MODEL.')
    url = BASE_URL if BASE_URL.endswith('/chat/completions') else BASE_URL + '/chat/completions'
    response = requests.post(url, headers={'Authorization': f'Bearer {API_KEY}', 'Content-Type':'application/json'},
        json={'model':MODEL,'temperature':0,'response_format':{'type':'json_object'},'messages':[{'role':'system','content':system_prompt},{'role':'user','content':user_content}]}, timeout=TIMEOUT)
    response.raise_for_status(); payload=response.json()
    content=payload['choices'][0]['message']['content']
    if not isinstance(content,str): raise ValueError('LLM returned non-text content')
    result=json.loads(content)
    if not isinstance(result,dict): raise ValueError('LLM JSON root must be an object')
    return result

def extract_atomic_claims_and_unreferenced(draft_text: str) -> dict:
    prompt='''Analyze the academic text. Return JSON with referenced_claims (list of {claim: string, citation_ids: list of strings}) and unreferenced_claims (list of factual claim strings). Preserve all IDs matching [P1] or [P1, P2]. Do not silently omit factual claims. Ignore headings and purely transitional language. If uncertain, include the sentence as unreferenced_claims.'''
    data=_call_llm(prompt, draft_text)
    if not isinstance(data.get('referenced_claims'),list) or not isinstance(data.get('unreferenced_claims'),list): raise ValueError('Invalid extraction schema')
    for item in data['referenced_claims']:
        if not isinstance(item,dict) or not isinstance(item.get('claim'),str) or not isinstance(item.get('citation_ids'),list): raise ValueError('Invalid referenced claim item')
    return data

def verify_single_claim(claim: str, source_abstract: str) -> dict:
    prompt='''Assess whether the source abstract supports the claim. Return JSON {"status":"SUPPORTED|CONTRADICTED|INSUFFICIENT","reason":"brief evidence-based explanation"}. SUPPORTED requires explicit entailment; CONTRADICTED requires explicit contradiction; otherwise INSUFFICIENT. This is LLM-as-a-judge, not a validated NLI classifier.'''
    result=_call_llm(prompt, f'CLAIM:\n{claim}\n\nSOURCE ABSTRACT:\n{source_abstract}')
    status=result.get('status')
    if status not in {'SUPPORTED','CONTRADICTED','INSUFFICIENT'}: raise ValueError('Invalid verification status')
    return {'status':status,'reason':str(result.get('reason',''))[:2000]}

def run_full_audit(draft_text: str, papers: list[dict]) -> dict:
    if not isinstance(draft_text,str) or not draft_text.strip(): return {'status':'not_run','reason':'No draft text supplied.'}
    try: extraction=extract_atomic_claims_and_unreferenced(draft_text)
    except AuditNotConfigured as e: return {'status':'not_configured','reason':str(e),'detailed_audit':[],'unreferenced_claims':[]}
    except Exception as e: return {'status':'error','reason':f'Claim extraction failed: {type(e).__name__}: {e}','detailed_audit':[],'unreferenced_claims':[]}
    paper_map={str(p.get('paper_id') or p.get('openalex_id') or f'P{i}'):p for i,p in enumerate(papers,1)}
    # Map generated positional citation IDs P1...Pn to the current ordered paper list too.
    for i,p in enumerate(papers,1): paper_map.setdefault(f'P{i}',p)
    details=[]
    for item in extraction['referenced_claims']:
        claim=item['claim']
        for raw_id in item['citation_ids']:
            match=re.search(r'P\d+',str(raw_id),re.I); cite_id=match.group(0).upper() if match else str(raw_id)
            paper=paper_map.get(cite_id)
            if paper is None:
                details.append({'claim':claim,'citation_id':cite_id,'status':'INVALID_CITATION','reason':'Citation ID does not match a paper in this run.'}); continue
            abstract=paper.get('abstract') or ''
            if not abstract.strip():
                details.append({'claim':claim,'citation_id':cite_id,'status':'INSUFFICIENT','reason':'Source abstract is unavailable; full text was not checked.'}); continue
            try: result=verify_single_claim(claim,abstract)
            except Exception as e: result={'status':'ERROR','reason':f'{type(e).__name__}: {e}'}
            details.append({'claim':claim,'citation_id':cite_id,**result})
    denominator=len(details)
    contradicted=sum(x['status']=='CONTRADICTED' for x in details)
    insufficient=sum(x['status'] in {'INSUFFICIENT','INVALID_CITATION','ERROR'} for x in details)
    supported=sum(x['status']=='SUPPORTED' for x in details)
    return {'status':'completed','method':'LLM-as-a-judge; not a validated NLI classifier','audit_summary':{
        'total_claim_source_pairs':denominator,'supported_pairs':supported,'contradicted_pairs':contradicted,
        'insufficient_invalid_or_error_pairs':insufficient,
        'unsupported_or_contradicted_claim_rate':round((contradicted+insufficient)/denominator,4) if denominator else None,
        'unreferenced_claims_count':len(extraction['unreferenced_claims'])},
        'detailed_audit':details,'unreferenced_claims':extraction['unreferenced_claims']}
