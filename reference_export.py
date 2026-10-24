"""Conservative reference exporters. APA output is an approximation, not a substitute for manual style review."""
from __future__ import annotations
import re
from typing import Any

def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()

def get_doi(paper: dict) -> str:
    doi = clean(paper.get("doi"))
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.I)
    return doi.rstrip(" .")

def normalize_paper(paper: dict) -> dict:
    authors = paper.get("authors") or []
    if isinstance(authors, str): authors = [authors]
    return {"title": clean(paper.get("title")), "authors": [clean(a) for a in authors if clean(a)],
            "year": clean(paper.get("year")), "journal": clean(paper.get("journal") or paper.get("container_title")),
            "volume": clean(paper.get("volume")), "issue": clean(paper.get("issue")), "pages": clean(paper.get("pages")),
            "doi": get_doi(paper), "url": clean(paper.get("landing_page") or paper.get("url")),
            "publisher": clean(paper.get("publisher")), "type": clean(paper.get("type") or paper.get("work_type"))}

def bib_escape(value: Any) -> str:
    value = clean(value)
    replacements = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    return ''.join(replacements.get(ch, ch) for ch in value)

def citation_key(paper: dict, index: int, used: set[str]) -> str:
    p = normalize_paper(paper)
    author = p['authors'][0] if p['authors'] else 'Unknown'
    surname = author.split(',')[0] if ',' in author else author.split()[-1] if author.split() else 'Unknown'
    base = re.sub(r'[^A-Za-z0-9]+', '', surname) or 'Unknown'
    year = re.sub(r'[^0-9]', '', p['year']) or 'nd'
    proposed = f"{base}{year}_P{index}"
    key = proposed; suffix = 2
    while key in used:
        key = f"{proposed}_{suffix}"; suffix += 1
    used.add(key)
    return key

def export_bibtex(papers: list[dict]) -> str:
    entries=[]; used=set()
    for i, raw in enumerate(papers, 1):
        p=normalize_paper(raw); key=citation_key(raw, i, used)
        entry_type = 'article' if p['journal'] else 'misc'
        fields = [('title', p['title']), ('author', ' and '.join(p['authors']) if p['authors'] else 'Unknown Author'), ('year', p['year']), ('journal', p['journal']), ('volume', p['volume']), ('number', p['issue']), ('pages', p['pages']), ('doi', p['doi']), ('url', p['url'])]
        lines=[f'@{entry_type}{{{key},']
        for name,value in fields:
            if value: lines.append(f'  {name} = {{{bib_escape(value)}}},')
        if len(lines)>1 and lines[-1].endswith(','): lines[-1]=lines[-1][:-1]
        lines.append('}')
        entries.append('\n'.join(lines))
    return '\n\n'.join(entries)

def ris_escape(value: Any) -> str:
    return clean(value).replace('\r',' ').replace('\n',' ')

def export_ris(papers: list[dict]) -> str:
    records=[]
    for raw in papers:
        p=normalize_paper(raw); lines=[f"TY  - {'JOUR' if p['journal'] else 'GEN'}"]
        if p['title']: lines.append('TI  - '+ris_escape(p['title']))
        for author in p['authors']: lines.append('AU  - '+ris_escape(author))
        if p['year']: lines.append('PY  - '+p['year'])
        if p['journal']: lines.append('JO  - '+ris_escape(p['journal']))
        if p['volume']: lines.append('VL  - '+p['volume'])
        if p['issue']: lines.append('IS  - '+p['issue'])
        if p['pages']: lines.append('SP  - '+p['pages'].split('-')[0].strip()); lines.append('EP  - '+p['pages'].split('-')[-1].strip()) if '-' in p['pages'] else None
        if p['doi']: lines.append('DO  - '+p['doi']); lines.append('UR  - https://doi.org/'+p['doi'])
        elif p['url']: lines.append('UR  - '+p['url'])
        lines.append('ER  - '); records.append('\n'.join(lines))
    return '\n\n'.join(records)

def _apa_author(author: str) -> str:
    author=clean(author)
    if ',' in author:
        surname, given = [x.strip() for x in author.split(',',1)]
    else:
        bits=author.split(); surname=bits[-1] if bits else author; given=' '.join(bits[:-1])
    initials=' '.join((part[0].upper()+'.') for part in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", given))
    return f"{surname}, {initials}" if initials else surname

def export_apa7(papers: list[dict]) -> str:
    refs=[]
    for raw in papers:
        p=normalize_paper(raw); authors=p['authors']
        if not authors: author_text='Unknown Author'
        elif len(authors)<=20: author_text=', '.join(_apa_author(a) for a in authors[:-1]) + (', & ' if len(authors)>1 else '') + _apa_author(authors[-1])
        else: author_text=', '.join(_apa_author(a) for a in authors[:19]) + ', ... ' + _apa_author(authors[-1])
        year=p['year'] or 'n.d.'; title=p['title'] or '[Title unavailable]'
        ref=f"{author_text} ({year}). {title}."
        if p['journal']:
            ref += f" *{p['journal']}*"
            if p['volume']: ref += f", *{p['volume']}*"
            if p['issue']: ref += f"({p['issue']})"
            if p['pages']: ref += f", {p['pages']}"
            ref += '.'
        elif p['publisher']:
            ref += f" {p['publisher']}."
        if p['doi']: ref += f" https://doi.org/{p['doi']}"
        elif p['url']: ref += f" {p['url']}"
        refs.append(ref)
    return '\n\n'.join(refs)
