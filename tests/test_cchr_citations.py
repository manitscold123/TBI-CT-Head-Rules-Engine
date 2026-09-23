"""Every criterion cites the pages of sources/stiell2001.pdf it comes from.

Expected pages were checked by hand against the PDF (journal pages 1391-96 are
PDF pages 1-6). A new criterion fails here until its pages are added below.
"""

import re

import pytest
from patients import negative_patient

from ct_head_rules.cchr import evaluate_cchr

# Methods, "Study setting and population": eligibility sentence starts at the
# bottom of p1391 (right column) and continues at the top of p1392; the
# exclusion list is on p1392 (left column). Panel 1 and its footnote are on p1394.
EXPECTED_PAGES = {
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

CRITERIA = evaluate_cchr(negative_patient()).criteria


def cited_pages(source: str) -> set[int]:
    """Pages from "p1392" or "pp1391-92" style references."""
    pages = set()
    for first, last in re.findall(r"\bpp?(\d{4})(?:-(\d{2,4}))?\b", source):
        start = int(first)
        end = int(first[: 4 - len(last)] + last) if last else start
        pages.update(range(start, end + 1))
    return pages


def test_page_parser_expands_ranges():
    assert cited_pages("Methods (pp1391-92) and Panel 1 (p1394)") == {
        1391,
        1392,
        1394,
    }


def test_every_criterion_has_expected_pages_listed():
    assert {c.id for c in CRITERIA} == set(EXPECTED_PAGES)


@pytest.mark.parametrize("criterion", CRITERIA, ids=lambda c: c.id)
def test_criterion_cites_the_pages_it_comes_from(criterion):
    assert criterion.source.startswith("Stiell 2001, Lancet 357:1391-96")
    assert cited_pages(criterion.source) == EXPECTED_PAGES[criterion.id]
