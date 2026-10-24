from reference_export import export_bibtex, export_ris, export_apa7, citation_key

SAMPLE = [{
    "title": "Digital transformation & governance",
    "authors": ["Smith, John", "Jones, Mary"],
    "year": 2024, "journal": "Journal of Educational Research", "volume": "12",
    "issue": "2", "pages": "10-25", "doi": "https://doi.org/10.1234/example.2024"
}]

def test_bibtex_contains_title_doi_and_escapes_ampersand():
    result = export_bibtex(SAMPLE)
    assert "@article{" in result
    assert r"Digital transformation \& governance" in result
    assert "10.1234/example.2024" in result

def test_ris_has_record_markers_and_doi():
    result = export_ris(SAMPLE)
    assert "TY  - JOUR" in result
    assert "TI  - Digital transformation & governance" in result
    assert "DO  - 10.1234/example.2024" in result
    assert "ER  - " in result

def test_apa7_author_year_and_doi():
    result = export_apa7(SAMPLE)
    assert "Smith, J." in result
    assert "Jones, M." in result
    assert "(2024)." in result
    assert "https://doi.org/10.1234/example.2024" in result

def test_missing_doi_does_not_create_fake_url():
    result = export_apa7([{"title":"A study without a DOI", "authors":["Ali, Ahmed"], "year":2023}])
    assert "A study without a DOI" in result
    assert "https://doi.org/" not in result

def test_more_than_20_authors_uses_apa_ellipsis_rule():
    authors = [f"Surname{i}, Author{i}" for i in range(1, 22)]
    result = export_apa7([{"title":"Many authors", "authors":authors, "year":2024, "journal":"Journal"}])
    assert "... Surname21, A." in result
    assert "Surname20, A." not in result

def test_bibtex_keys_are_unique_and_whitespace_free():
    used=set()
    p={"authors":["Smith, John"],"year":2023}
    k1=citation_key(p,1,used); k2=citation_key(p,1,used)
    assert k1 != k2
    assert not any(ch.isspace() for ch in k1+k2)
