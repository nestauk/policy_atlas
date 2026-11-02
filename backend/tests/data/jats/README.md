# JATS full-text fixtures

Real open-access articles in JATS XML (the Journal Article Tag Suite, the XML format
publishers deposit papers in), used by `tests/evidence_search/sourcing/test_parse_jats.py`
to check that `parse_jats` finds headings, paragraphs and tables. Real openly licensed
documents are allowed as full-text fixtures (sanitized-fixtures policy).

Each file was fetched once, on 2026-11-02, with `fetch_europe_pmc_xml` from the Europe
PMC REST service (task 056, egress approved for `www.ebi.ac.uk`, sending the PubMed
Central id only). The files are saved byte for byte as served. All three are licensed
CC BY 4.0 (Creative Commons Attribution), as stated in each file's `<license>` element.
The articles came from the fixed-question acquisitions of 2026-11-02 (task 056).

| File | PubMed Central id | Title | Journal, year | Licence | Source URL |
| --- | --- | --- | --- | --- | --- |
| `PMC11210863.xml` | PMC11210863 | Interventions targeting young people not in employment, education or training (NEET) for increased likelihood of return to school or employment — A systematic review (Stea et al.; doi 10.1371/journal.pone.0306285) | PLOS ONE, 2024 | CC BY 4.0 | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11210863/fullTextXML |
| `PMC5264339.xml` | PMC5264339 | Are we failing young people not in employment, education or training (NEETs)? A systematic review and meta-analysis of re-engagement interventions (doi 10.1186/s13643-016-0394-2) | Systematic Reviews, 2017 | CC BY 4.0 | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5264339/fullTextXML |
| `PMC11218303.xml` | PMC11218303 | A school-based food and nutrition education intervention increases nutrition-related knowledge and fruit consumption among primary school children in northern Ghana (doi 10.1186/s12889-024-19200-7) | BMC Public Health, 2024 | CC BY 4.0 | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11218303/fullTextXML |

SHA-256 of the saved files:

```
2a9c1eda50244d2346e988f038ec01474039bf3bd3a0ce229494ce25c2ad552f  PMC11210863.xml
3e2e0e55ffc559ba6c2752749b43cdb540b09d6530130cadc4ba76bda14ddb66  PMC5264339.xml
f3e4b69ba40f3d13adb2c028120b51566f4d6af7c96e4f98b65d969ae1563d12  PMC11218303.xml
```

The test pins a digest of each parsed output. If `parse_jats` changes on purpose,
re-run the test, check the new output by eye, and update the digest in the test.
