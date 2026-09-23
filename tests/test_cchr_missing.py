"""Missing and unknown inputs must never be treated as negative (CLAUDE.md)."""

import dataclasses

import pytest
from patients import ABSENT, PRESENT, UNKNOWN, negative_patient

from ct_head_rules.cchr import (
    CCHRInput,
    CriterionStatus,
    Outcome,
    RiskLevel,
    evaluate_cchr,
)
from ct_head_rules.findings import Finding

# Definite amnesia and witnessed disorientation are alternatives to witnessed
# LOC, which the negative patient already has, so leaving them unknown cannot
# change the result. They get their own test below.
REDUNDANT_WHEN_LOC_PRESENT = {"definite_amnesia", "witnessed_disorientation"}


def missing_value(field: dataclasses.Field):
    return UNKNOWN if field.type is Finding else None


DECISIVE_FIELDS = [
    f for f in dataclasses.fields(CCHRInput) if f.name not in REDUNDANT_WHEN_LOC_PRESENT
]


@pytest.mark.parametrize("field", DECISIVE_FIELDS, ids=lambda f: f.name)
def test_missing_input_on_negative_patient_is_indeterminate(field):
    result = evaluate_cchr(negative_patient(**{field.name: missing_value(field)}))

    assert result.outcome is Outcome.INDETERMINATE
    assert result.risk_level is None
    assert result.missing_inputs == (field.name,)


@pytest.mark.parametrize("field", sorted(REDUNDANT_WHEN_LOC_PRESENT))
def test_unknown_alternative_to_witnessed_loc_is_reported_but_not_blocking(field):
    result = evaluate_cchr(negative_patient(**{field: UNKNOWN}))

    assert result.outcome is Outcome.CT_NOT_REQUIRED
    assert result.missing_inputs == (field,)


def test_unknown_basal_skull_sign_makes_criterion_unknown():
    result = evaluate_cchr(negative_patient(battle_sign=UNKNOWN))

    by_id = {c.id: c for c in result.criteria}
    criterion = by_id["cchr.high.basal_skull_fracture_sign"]
    assert criterion.status is CriterionStatus.UNKNOWN
    assert criterion.missing_inputs == ("battle_sign",)


def test_one_present_sign_is_enough_even_if_others_are_unknown():
    result = evaluate_cchr(negative_patient(raccoon_eyes=PRESENT, battle_sign=UNKNOWN))

    assert result.outcome is Outcome.CT_RECOMMENDED
    assert result.risk_level is RiskLevel.HIGH
    assert result.missing_inputs == ("battle_sign",)


def test_gcs_at_2h_not_yet_reached_is_indeterminate_with_reevaluation_note():
    result = evaluate_cchr(
        negative_patient(hours_since_injury=1.0, gcs_2h_post_injury=None)
    )

    assert result.outcome is Outcome.INDETERMINATE
    assert "gcs_2h_post_injury" in result.missing_inputs
    assert any("2 h" in note for note in result.notes)


def test_high_risk_met_with_other_inputs_missing_still_recommends_ct():
    result = evaluate_cchr(
        negative_patient(
            vomiting_episodes=2, gcs_2h_post_injury=None, battle_sign=UNKNOWN
        )
    )

    assert result.outcome is Outcome.CT_RECOMMENDED
    assert result.risk_level is RiskLevel.HIGH
    assert result.missing_inputs == ("gcs_2h_post_injury", "battle_sign")


def test_medium_risk_met_with_high_risk_unknown_flags_possible_upgrade():
    result = evaluate_cchr(
        negative_patient(retrograde_amnesia_minutes=45, vomiting_episodes=None)
    )

    assert result.outcome is Outcome.CT_RECOMMENDED
    assert result.risk_level is RiskLevel.MEDIUM
    assert result.missing_inputs == ("vomiting_episodes",)
    assert any("high risk" in note for note in result.notes)


def test_criterion_met_with_applicability_unknown_recommends_ct():
    # Missing applicability data could only move this to NOT_APPLICABLE
    # (no guidance), never to CT_NOT_REQUIRED.
    result = evaluate_cchr(negative_patient(age_years=70, oral_anticoagulant=UNKNOWN))

    assert result.outcome is Outcome.CT_RECOMMENDED
    assert result.risk_level is RiskLevel.HIGH
    assert result.missing_inputs == ("oral_anticoagulant",)


def test_known_exclusion_wins_over_missing_inputs():
    result = evaluate_cchr(
        negative_patient(oral_anticoagulant=PRESENT, vomiting_episodes=None)
    )

    assert result.outcome is Outcome.NOT_APPLICABLE
    assert result.missing_inputs == ("vomiting_episodes",)


def test_everything_unknown_is_indeterminate():
    unknowns = {f.name: missing_value(f) for f in dataclasses.fields(CCHRInput)}
    result = evaluate_cchr(CCHRInput(**unknowns))

    assert result.outcome is Outcome.INDETERMINATE
    assert set(result.missing_inputs) == set(unknowns)


# --- Inputs that could be silently read as negative are rejected -------------


@pytest.mark.parametrize("value", [None, False, True, 0, "absent"])
def test_non_finding_value_for_finding_field_is_rejected(value):
    with pytest.raises(TypeError, match="battle_sign"):
        negative_patient(battle_sign=value)


@pytest.mark.parametrize("value", [False, True, "0"])
def test_non_numeric_value_for_numeric_field_is_rejected(value):
    with pytest.raises(TypeError, match="vomiting_episodes"):
        negative_patient(vomiting_episodes=value)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("initial_ed_gcs", 2),
        ("initial_ed_gcs", 16),
        ("gcs_2h_post_injury", 16),
        ("gcs_2h_post_injury", 14.5),
        ("age_years", -1),
        ("vomiting_episodes", -1),
        ("retrograde_amnesia_minutes", -5),
        ("hours_since_injury", -0.5),
    ],
)
def test_out_of_range_value_is_rejected(field, value):
    with pytest.raises(ValueError, match=field):
        negative_patient(**{field: value})


def test_absent_is_not_confused_with_unknown():
    assert negative_patient(battle_sign=ABSENT).battle_sign is Finding.ABSENT
