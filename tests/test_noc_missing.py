"""Missing inputs in the New Orleans Criteria are never treated as negative."""

import dataclasses

import pytest
from patients import PRESENT, UNKNOWN, negative_patient

from ct_head_rules.findings import Finding
from ct_head_rules.noc import NOC_INPUTS, evaluate_noc
from ct_head_rules.patient import Patient
from ct_head_rules.rules import Outcome

FIELDS = {f.name: f for f in dataclasses.fields(Patient)}

# Only used for a note, never as a criterion (p103).
NOTE_ONLY = {"bleeding_disorder", "oral_anticoagulant"}
# Alternatives to witnessed LOC, which the negative patient already has.
REDUNDANT_WHEN_LOC_PRESENT = {"patient_reported_loc", "amnesia_for_event"}

CRITERION_INPUTS = tuple(name for name in NOC_INPUTS if name not in NOTE_ONLY)
DECISIVE = [n for n in CRITERION_INPUTS if n not in REDUNDANT_WHEN_LOC_PRESENT]


def missing_value(name: str):
    return UNKNOWN if FIELDS[name].type is Finding else None


def test_inputs_are_shared_fields_plus_new_orleans_fields():
    assert NOC_INPUTS == (
        "age_years",
        "witnessed_loc",
        "initial_ed_gcs",
        "hours_since_injury",
        "bleeding_disorder",
        "oral_anticoagulant",
        "vomiting_episodes",
        "patient_reported_loc",
        "amnesia_for_event",
        "abnormal_brief_neuro_exam",
        "headache",
        "drug_or_alcohol_intoxication",
        "short_term_memory_deficit",
        "trauma_above_clavicles",
        "post_traumatic_seizure",
    )


@pytest.mark.parametrize("name", DECISIVE)
def test_missing_input_on_negative_patient_is_indeterminate(name):
    result = evaluate_noc(negative_patient(**{name: missing_value(name)}))

    assert result.outcome is Outcome.INDETERMINATE
    assert result.missing_inputs == (name,)


@pytest.mark.parametrize("name", sorted(REDUNDANT_WHEN_LOC_PRESENT))
def test_unknown_alternative_to_witnessed_loc_is_reported_but_not_blocking(name):
    result = evaluate_noc(negative_patient(**{name: UNKNOWN}))

    assert result.outcome is Outcome.CT_NOT_REQUIRED
    assert result.missing_inputs == (name,)


@pytest.mark.parametrize("name", sorted(NOTE_ONLY))
def test_unknown_coagulopathy_is_not_a_missing_input(name):
    result = evaluate_noc(negative_patient(**{name: UNKNOWN}))

    assert result.outcome is Outcome.CT_NOT_REQUIRED
    assert result.missing_inputs == ()


def test_unknown_gcs_is_indeterminate_never_not_required():
    result = evaluate_noc(negative_patient(initial_ed_gcs=None))

    assert result.outcome is Outcome.INDETERMINATE
    assert result.missing_inputs == ("initial_ed_gcs",)


def test_finding_met_with_unknown_gcs_still_recommends_ct():
    # Same policy as the Canadian rule: the missing GCS could only make the
    # rule not apply, never make CT unnecessary.
    result = evaluate_noc(negative_patient(initial_ed_gcs=None, headache=PRESENT))

    assert result.outcome is Outcome.CT_RECOMMENDED
    assert result.missing_inputs == ("initial_ed_gcs",)


def test_everything_unknown_is_indeterminate():
    result = evaluate_noc(Patient())

    assert result.outcome is Outcome.INDETERMINATE
    assert result.missing_inputs == CRITERION_INPUTS
