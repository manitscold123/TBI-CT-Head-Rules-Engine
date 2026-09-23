"""Who PECARN applies to.

Source: Kuppermann et al. 2009, Lancet 374:1160-70, Methods (pp1161-62).
Children under 18, within 24 h, GCS 14-15. No loss of consciousness required.
"""

import pytest
from patients import PRESENT, negative_child

from ct_head_rules.cchr import evaluate_cchr
from ct_head_rules.noc import evaluate_noc
from ct_head_rules.pecarn import evaluate_pecarn
from ct_head_rules.rules import Outcome


def assert_not_applicable(result, criterion_id: str) -> None:
    assert result.outcome is Outcome.NOT_APPLICABLE
    assert {c.id for c in result.exclusion_reasons} == {criterion_id}
    assert any("no guidance" in note for note in result.notes)


def test_age_18_is_not_applicable():
    result = evaluate_pecarn(negative_child(18))
    assert_not_applicable(result, "pecarn.inclusion.age_under_18")


def test_age_17_is_eligible():
    assert evaluate_pecarn(negative_child(17)).outcome is Outcome.CT_NOT_REQUIRED


def test_gcs_13_is_not_applicable_and_notes_separate_analysis():
    result = evaluate_pecarn(negative_child(5, initial_ed_gcs=13))

    assert_not_applicable(result, "pecarn.inclusion.gcs_14_to_15")
    assert any("separately" in note for note in result.notes)


def test_injury_more_than_24h_ago_is_not_applicable():
    result = evaluate_pecarn(negative_child(5, hours_since_injury=25))
    assert_not_applicable(result, "pecarn.inclusion.injury_within_24h")


def test_injury_exactly_24h_ago_is_eligible():
    result = evaluate_pecarn(negative_child(5, hours_since_injury=24))
    assert result.outcome is Outcome.CT_NOT_REQUIRED


@pytest.mark.parametrize(
    "field",
    [
        "trivial_mechanism_no_symptoms",
        "penetrating_trauma",
        "brain_tumour",
        "neuro_disorder_complicating_assessment",
        "ventricular_shunt",
        "bleeding_disorder",
    ],
)
def test_exclusion_makes_rule_not_applicable(field):
    result = evaluate_pecarn(negative_child(5, **{field: PRESENT}))
    assert_not_applicable(result, f"pecarn.exclusion.{field}")


def test_anticoagulant_is_not_an_exclusion_but_is_noted():
    # The paper excludes bleeding disorders and never mentions anticoagulants.
    result = evaluate_pecarn(negative_child(5, oral_anticoagulant=PRESENT))

    assert result.outcome is Outcome.CT_NOT_REQUIRED
    assert any("anticoagulant" in note for note in result.notes)


def test_age_unknown_is_indeterminate_and_asks_for_age():
    result = evaluate_pecarn(negative_child(None))

    assert result.outcome is Outcome.INDETERMINATE
    assert result.missing_inputs == ("age_years",)
    assert any("under-2" in note for note in result.notes)


# --- Across rules ------------------------------------------------------------------


def test_no_loc_is_eligible_for_pecarn_only():
    # A 16-year-old is old enough for all three rules, but the Canadian and
    # New Orleans rules require loss of consciousness (or amnesia).
    patient = negative_child(16)

    assert evaluate_pecarn(patient).outcome is Outcome.CT_NOT_REQUIRED
    assert evaluate_cchr(patient).outcome is Outcome.NOT_APPLICABLE
    assert evaluate_noc(patient).outcome is Outcome.NOT_APPLICABLE


def test_witnessed_loc_at_16_is_observation_for_pecarn_only():
    patient = negative_child(16, witnessed_loc=PRESENT)

    assert evaluate_cchr(patient).outcome is Outcome.CT_NOT_REQUIRED
    assert evaluate_noc(patient).outcome is Outcome.CT_NOT_REQUIRED
    assert evaluate_pecarn(patient).outcome is Outcome.OBSERVATION_OR_CT


def test_adult_rules_never_return_observation_or_ct():
    patient = negative_child(16, witnessed_loc=PRESENT, vomiting_episodes=1)

    assert evaluate_cchr(patient).outcome is Outcome.CT_NOT_REQUIRED
    assert evaluate_noc(patient).outcome is Outcome.CT_RECOMMENDED
