"""Missing inputs in PECARN are never treated as negative."""

import dataclasses

import pytest
from patients import UNKNOWN, negative_child

from ct_head_rules.findings import Finding
from ct_head_rules.patient import Patient
from ct_head_rules.pecarn import PECARN_INPUTS, evaluate_pecarn
from ct_head_rules.rules import Outcome

FIELDS = {f.name: f for f in dataclasses.fields(Patient)}

ELIGIBILITY = [
    "initial_ed_gcs",
    "hours_since_injury",
    "bleeding_disorder",
    "trivial_mechanism_no_symptoms",
    "penetrating_trauma",
    "brain_tumour",
    "neuro_disorder_complicating_assessment",
    "ventricular_shunt",
]
UNDER_2 = [
    "other_altered_mental_status",
    "palpable_or_unclear_skull_fracture",
    "non_frontal_scalp_haematoma",
    "loc_duration_seconds",
    "not_acting_normally_per_parent",
    "fall_height_m",
    "severe_non_fall_mechanism",
]
TWO_AND_OVER = [
    "haemotympanum",
    "raccoon_eyes",
    "csf_otorrhoea_or_rhinorrhoea",
    "battle_sign",
    "vomiting_episodes",
    "other_altered_mental_status",
    "history_of_loc",
    "severe_headache",
    "fall_height_m",
    "severe_non_fall_mechanism",
]


def missing_value(name: str):
    return UNKNOWN if FIELDS[name].type is Finding else None


@pytest.mark.parametrize(
    ("age", "name"),
    [(1, name) for name in ELIGIBILITY + UNDER_2]
    + [(5, name) for name in ELIGIBILITY + TWO_AND_OVER],
)
def test_missing_input_is_indeterminate(age, name):
    result = evaluate_pecarn(negative_child(age, **{name: missing_value(name)}))

    assert result.outcome is Outcome.INDETERMINATE
    assert result.missing_inputs == (name,)


def test_inputs_cover_both_age_groups_and_the_anticoagulant_note():
    expected = {"age_years", "oral_anticoagulant", *ELIGIBILITY, *UNDER_2}
    assert set(PECARN_INPUTS) == expected | set(TWO_AND_OVER)


def test_unknown_anticoagulant_is_not_a_missing_input():
    result = evaluate_pecarn(negative_child(5, oral_anticoagulant=UNKNOWN))
    assert result.missing_inputs == ()


def test_predictor_met_with_eligibility_unknown_still_gives_its_tier():
    result = evaluate_pecarn(
        negative_child(5, hours_since_injury=None, severe_headache=Finding.PRESENT)
    )

    assert result.outcome is Outcome.OBSERVATION_OR_CT
    assert result.missing_inputs == ("hours_since_injury",)


def test_everything_unknown_is_indeterminate_and_asks_for_age_first():
    result = evaluate_pecarn(Patient())

    assert result.outcome is Outcome.INDETERMINATE
    assert "age_years" in result.missing_inputs
