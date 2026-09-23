"""Who the Canadian CT Head Rule applies to.

Source: Stiell et al. 2001, Lancet 357:1391-96, Methods, "Study setting and
population" (pp1391-92), and the Panel 1 footnote defining minor head injury.
"""

import pytest
from patients import ABSENT, PRESENT, negative_patient

from ct_head_rules.cchr import CriterionStatus, Outcome, evaluate_cchr


def reason_ids(result) -> set[str]:
    return {c.id for c in result.exclusion_reasons}


def assert_not_applicable(result, criterion_id: str) -> None:
    assert result.outcome is Outcome.NOT_APPLICABLE
    assert result.risk_level is None
    assert reason_ids(result) == {criterion_id}


# --- Exclusions ------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value", "criterion_id"),
    [
        pytest.param("age_years", 15, "cchr.exclusion.age_under_16", id="age<16"),
        pytest.param(
            "obvious_penetrating_injury_or_depressed_fracture",
            PRESENT,
            "cchr.exclusion.obvious_penetrating_or_depressed_fracture",
            id="obvious-penetrating-or-depressed-fracture",
        ),
        pytest.param(
            "acute_focal_neuro_deficit",
            PRESENT,
            "cchr.exclusion.acute_focal_neuro_deficit",
            id="focal-neuro-deficit",
        ),
        pytest.param(
            "unstable_vitals_major_trauma",
            PRESENT,
            "cchr.exclusion.unstable_vitals_major_trauma",
            id="unstable-vitals",
        ),
        pytest.param(
            "seizure_before_ed_assessment",
            PRESENT,
            "cchr.exclusion.seizure_before_ed_assessment",
            id="seizure-before-ed",
        ),
        pytest.param(
            "bleeding_disorder",
            PRESENT,
            "cchr.exclusion.bleeding_disorder",
            id="bleeding-disorder",
        ),
        pytest.param(
            "oral_anticoagulant",
            PRESENT,
            "cchr.exclusion.oral_anticoagulant",
            id="oral-anticoagulant",
        ),
        pytest.param(
            "return_visit_same_injury",
            PRESENT,
            "cchr.exclusion.return_visit_same_injury",
            id="return-visit",
        ),
        pytest.param("pregnant", PRESENT, "cchr.exclusion.pregnant", id="pregnant"),
    ],
)
def test_exclusion_makes_rule_not_applicable(field, value, criterion_id):
    result = evaluate_cchr(negative_patient(**{field: value}))
    assert_not_applicable(result, criterion_id)


def test_age_16_is_eligible():
    assert evaluate_cchr(negative_patient(age_years=16)).outcome is (
        Outcome.CT_NOT_REQUIRED
    )


def test_warfarin_patient_with_high_risk_findings_is_not_applicable():
    # Oral anticoagulant use is an exclusion, so risk findings must not turn
    # into a recommendation, and must not become "CT not required" either.
    result = evaluate_cchr(
        negative_patient(oral_anticoagulant=PRESENT, age_years=70, vomiting_episodes=3)
    )

    assert_not_applicable(result, "cchr.exclusion.oral_anticoagulant")
    assert result.triggered == ()
    by_id = {c.id: c for c in result.criteria}
    assert by_id["cchr.high.age_65_or_over"].status is CriterionStatus.MET
    assert by_id["cchr.high.vomiting_2_or_more"].status is CriterionStatus.MET
    assert any("no guidance" in note for note in result.notes)


def test_anticoagulant_and_bleeding_disorder_are_reported_separately():
    result = evaluate_cchr(
        negative_patient(oral_anticoagulant=PRESENT, bleeding_disorder=PRESENT)
    )
    assert reason_ids(result) == {
        "cchr.exclusion.oral_anticoagulant",
        "cchr.exclusion.bleeding_disorder",
    }


# --- Inclusion criteria not met --------------------------------------------


def test_no_clear_blunt_trauma_is_not_applicable():
    result = evaluate_cchr(negative_patient(blunt_head_trauma=ABSENT))
    assert_not_applicable(result, "cchr.inclusion.blunt_head_trauma")


def test_minimal_head_injury_is_not_applicable():
    result = evaluate_cchr(
        negative_patient(
            witnessed_loc=ABSENT,
            definite_amnesia=ABSENT,
            witnessed_disorientation=ABSENT,
        )
    )
    assert_not_applicable(result, "cchr.inclusion.loc_amnesia_or_disorientation")


@pytest.mark.parametrize(
    "field", ["witnessed_loc", "definite_amnesia", "witnessed_disorientation"]
)
def test_any_one_of_loc_amnesia_or_disorientation_qualifies(field):
    none_of_them = dict(
        witnessed_loc=ABSENT, definite_amnesia=ABSENT, witnessed_disorientation=ABSENT
    )
    result = evaluate_cchr(negative_patient(**{**none_of_them, field: PRESENT}))
    assert result.outcome is Outcome.CT_NOT_REQUIRED


def test_initial_gcs_below_13_is_not_applicable():
    result = evaluate_cchr(negative_patient(initial_ed_gcs=12, gcs_2h_post_injury=12))
    assert_not_applicable(result, "cchr.inclusion.initial_gcs_13_to_15")


def test_initial_gcs_13_is_eligible():
    result = evaluate_cchr(negative_patient(initial_ed_gcs=13))
    assert result.outcome is Outcome.CT_NOT_REQUIRED


def test_injury_more_than_24h_ago_is_not_applicable():
    result = evaluate_cchr(negative_patient(hours_since_injury=25))
    assert_not_applicable(result, "cchr.inclusion.injury_within_24h")


def test_injury_exactly_24h_ago_is_eligible():
    result = evaluate_cchr(negative_patient(hours_since_injury=24))
    assert result.outcome is Outcome.CT_NOT_REQUIRED
