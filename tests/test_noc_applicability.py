"""Who the New Orleans Criteria apply to.

Source: Haydel et al. 2000, N Engl J Med 343:100-05, Methods, Phase 1 (pp100-01).
The key difference from the Canadian CT Head Rule: GCS must be exactly 15.
"""

import pytest
from patients import ABSENT, PRESENT, negative_patient

from ct_head_rules.cchr import evaluate_cchr
from ct_head_rules.noc import evaluate_noc
from ct_head_rules.rules import Outcome


def reason_ids(result) -> set[str]:
    return {c.id for c in result.exclusion_reasons}


def assert_not_applicable(result, criterion_id: str) -> None:
    assert result.outcome is Outcome.NOT_APPLICABLE
    assert result.risk_level is None
    assert reason_ids(result) == {criterion_id}
    assert any("no guidance" in note for note in result.notes)


# --- GCS 15 only ---------------------------------------------------------------


@pytest.mark.parametrize("gcs", [13, 14])
def test_gcs_13_or_14_is_not_applicable_but_points_to_canadian_rule(gcs):
    result = evaluate_noc(negative_patient(initial_ed_gcs=gcs))

    assert_not_applicable(result, "noc.inclusion.gcs_15")
    assert any("GCS 15" in note and "13-15" in note for note in result.notes)


def test_gcs_below_13_is_not_applicable_without_canadian_pointer():
    result = evaluate_noc(negative_patient(initial_ed_gcs=12))

    assert_not_applicable(result, "noc.inclusion.gcs_15")
    assert not any("13-15" in note for note in result.notes)


def test_gcs_15_is_eligible():
    assert evaluate_noc(negative_patient(initial_ed_gcs=15)).outcome is (
        Outcome.CT_NOT_REQUIRED
    )


def test_gcs_14_patient_is_covered_by_canadian_rule_but_not_new_orleans():
    # GCS 14 on arrival, back to 15 at 2 h, with a headache.
    patient = negative_patient(
        initial_ed_gcs=14, gcs_2h_post_injury=15, headache=PRESENT
    )

    assert evaluate_cchr(patient).outcome is Outcome.CT_NOT_REQUIRED
    assert evaluate_noc(patient).outcome is Outcome.NOT_APPLICABLE


def test_same_patient_with_gcs_15_gets_ct_from_new_orleans_only():
    patient = negative_patient(initial_ed_gcs=15, headache=PRESENT)

    assert evaluate_cchr(patient).outcome is Outcome.CT_NOT_REQUIRED
    assert evaluate_noc(patient).outcome is Outcome.CT_RECOMMENDED


def test_gcs_14_with_memory_deficit_suggests_rescoring():
    # Haydel scored an isolated short-term memory deficit as GCS 15 (p101).
    result = evaluate_noc(
        negative_patient(initial_ed_gcs=14, short_term_memory_deficit=PRESENT)
    )

    assert_not_applicable(result, "noc.inclusion.gcs_15")
    assert any("re-score" in note for note in result.notes)


def test_new_orleans_ignores_gcs_at_2h():
    result = evaluate_noc(negative_patient(gcs_2h_post_injury=13))
    assert result.outcome is Outcome.CT_NOT_REQUIRED


# --- Loss of consciousness or amnesia for the event -------------------------


NO_LOC = dict(
    witnessed_loc=ABSENT, patient_reported_loc=ABSENT, amnesia_for_event=ABSENT
)


@pytest.mark.parametrize(
    "field", ["witnessed_loc", "patient_reported_loc", "amnesia_for_event"]
)
def test_any_one_of_the_three_qualifies(field):
    result = evaluate_noc(negative_patient(**{**NO_LOC, field: PRESENT}))
    assert result.outcome is Outcome.CT_NOT_REQUIRED


def test_no_loc_or_amnesia_is_not_applicable():
    result = evaluate_noc(negative_patient(**NO_LOC))
    assert_not_applicable(result, "noc.inclusion.loc_or_amnesia_for_event")


def test_disorientation_alone_qualifies_for_canadian_rule_only():
    patient = negative_patient(**NO_LOC, witnessed_disorientation=PRESENT)

    assert evaluate_cchr(patient).outcome is Outcome.CT_NOT_REQUIRED
    assert evaluate_noc(patient).outcome is Outcome.NOT_APPLICABLE


# --- Other inclusions -----------------------------------------------------------


def test_abnormal_brief_neuro_exam_is_not_applicable():
    result = evaluate_noc(negative_patient(abnormal_brief_neuro_exam=PRESENT))
    assert_not_applicable(result, "noc.inclusion.normal_brief_neuro_exam")


def test_age_under_3_is_not_applicable():
    result = evaluate_noc(negative_patient(age_years=2))
    assert_not_applicable(result, "noc.inclusion.age_3_or_over")


def test_age_3_is_eligible_for_new_orleans_but_not_canadian_rule():
    patient = negative_patient(age_years=3)

    assert evaluate_noc(patient).outcome is Outcome.CT_NOT_REQUIRED
    assert evaluate_cchr(patient).outcome is Outcome.NOT_APPLICABLE


def test_injury_more_than_24h_ago_is_not_applicable():
    result = evaluate_noc(negative_patient(hours_since_injury=25))
    assert_not_applicable(result, "noc.inclusion.injury_within_24h")


def test_injury_exactly_24h_ago_is_eligible():
    result = evaluate_noc(negative_patient(hours_since_injury=24))
    assert result.outcome is Outcome.CT_NOT_REQUIRED


# --- Not exclusions for New Orleans ----------------------------------------------


@pytest.mark.parametrize("field", ["oral_anticoagulant", "bleeding_disorder"])
def test_coagulopathy_is_not_an_exclusion_but_is_flagged(field):
    # Haydel could not evaluate coagulopathy (1 patient in phase 1, p103).
    patient = negative_patient(**{field: PRESENT})
    result = evaluate_noc(patient)

    assert result.outcome is Outcome.CT_NOT_REQUIRED
    assert any("could not evaluate" in note for note in result.notes)
    assert evaluate_cchr(patient).outcome is Outcome.NOT_APPLICABLE


@pytest.mark.parametrize(
    "field",
    [
        "blunt_head_trauma",
        "pregnant",
        "return_visit_same_injury",
        "unstable_vitals_major_trauma",
    ],
)
def test_canadian_only_eligibility_fields_do_not_affect_new_orleans(field):
    value = ABSENT if field == "blunt_head_trauma" else PRESENT
    result = evaluate_noc(negative_patient(**{field: value}))
    assert result.outcome is Outcome.CT_NOT_REQUIRED
