"""Every criterion cites the pages of the source paper it comes from.

Expected pages were checked by hand against the PDFs in sources/, using the
journal's page numbers. A new criterion fails here until its pages are added.
"""

import re

import pytest
from patients import negative_patient

from ct_head_rules.cchr import evaluate_cchr
from ct_head_rules.noc import evaluate_noc

STIELL = "Stiell 2001, Lancet 357:1391-96"
HAYDEL = "Haydel 2000, N Engl J Med 343:100-05"

# Stiell 2001 (sources/stiell2001.pdf): the Methods eligibility sentence starts
# at the bottom of p1391 and continues on p1392, where the exclusion list is.
# Panel 1 and its footnote are on p1394.
EXPECTED_CCHR_PAGES = {
    "cchr.inclusion.blunt_head_trauma": {1391, 1392},
    "cchr.inclusion.loc_amnesia_or_disorientation": {1391, 1392, 1394},
    "cchr.inclusion.initial_gcs_13_to_15": {1392, 1394},
    "cchr.inclusion.injury_within_24h": {1392},
    "cchr.exclusion.age_under_16": {1392},
    "cchr.exclusion.obvious_penetrating_or_depressed_fracture": {1392},
    "cchr.exclusion.acute_focal_neuro_deficit": {1392},
    "cchr.exclusion.unstable_vitals_major_trauma": {1392},
    "cchr.exclusion.seizure_before_ed_assessment": {1392},
    "cchr.exclusion.bleeding_disorder": {1392},
    "cchr.exclusion.oral_anticoagulant": {1392},
    "cchr.exclusion.return_visit_same_injury": {1392},
    "cchr.exclusion.pregnant": {1392},
    "cchr.high.gcs_below_15_at_2h": {1394},
    "cchr.high.suspected_open_or_depressed_fracture": {1394},
    "cchr.high.basal_skull_fracture_sign": {1394},
    "cchr.high.vomiting_2_or_more": {1394},
    "cchr.high.age_65_or_over": {1394},
    "cchr.medium.retrograde_amnesia_over_30_min": {1394},
    "cchr.medium.dangerous_mechanism": {1394},
}

# Haydel 2000 (sources/NEJM200007133430204.pdf): age >=3 and within 24 h are in
# Methods, Phase 1, on p100; the minor head injury definition and every
# finding's definition are on p101, as is the Results sentence naming the
# seven findings. Trauma above the clavicles also cites Stiell Panel 1, which
# identifies the skull fracture signs used to infer it.
EXPECTED_NOC_PAGES = {
    "noc.inclusion.gcs_15": {101},
    "noc.inclusion.loc_or_amnesia_for_event": {101},
    "noc.inclusion.normal_brief_neuro_exam": {101},
    "noc.inclusion.age_3_or_over": {100},
    "noc.inclusion.injury_within_24h": {100},
    "noc.finding.headache": {101},
    "noc.finding.vomiting": {101},
    "noc.finding.age_over_60": {101},
    "noc.finding.drug_or_alcohol_intoxication": {101},
    "noc.finding.short_term_memory_deficit": {101},
    "noc.finding.trauma_above_clavicles": {101, 1394},
    "noc.finding.seizure": {101},
}

RULES = [
    pytest.param(evaluate_cchr, STIELL, EXPECTED_CCHR_PAGES, id="cchr"),
    pytest.param(evaluate_noc, HAYDEL, EXPECTED_NOC_PAGES, id="noc"),
]


def cited_pages(source: str) -> set[int]:
    """Pages from "p101", "p1392" or "pp1391-92" style references."""
    pages = set()
    for first, last in re.findall(r"\bpp?(\d{3,4})(?:-(\d{1,4}))?\b", source):
        start = int(first)
        end = int(first[: len(first) - len(last)] + last) if last else start
        pages.update(range(start, end + 1))
    return pages


def test_page_parser_expands_ranges():
    assert cited_pages("Methods (pp1391-92) and Panel 1 (p1394)") == {
        1391,
        1392,
        1394,
    }
    assert cited_pages("Methods (p101); Stiell Panel 1 (p1394)") == {101, 1394}


@pytest.mark.parametrize(("evaluate", "paper", "expected"), RULES)
def test_every_criterion_has_expected_pages_listed(evaluate, paper, expected):
    criteria = evaluate(negative_patient()).criteria
    assert {c.id for c in criteria} == set(expected)


@pytest.mark.parametrize(("evaluate", "paper", "expected"), RULES)
def test_criterion_cites_the_pages_it_comes_from(evaluate, paper, expected):
    for criterion in evaluate(negative_patient()).criteria:
        assert criterion.source.startswith(paper), criterion.id
        assert cited_pages(criterion.source) == expected[criterion.id], criterion.id
