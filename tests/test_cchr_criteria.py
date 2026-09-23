"""High- and medium-risk criteria of the Canadian CT Head Rule.

Source: Stiell et al. 2001, Lancet 357:1391-96, Panel 1.
"""

import pytest
from patients import PRESENT, negative_patient

from ct_head_rules.cchr import evaluate_cchr
from ct_head_rules.rules import CriterionStatus, Outcome, RiskLevel


def triggered_ids(result) -> set[str]:
    return {c.id for c in result.triggered}


def assert_recommended(result, level: RiskLevel, criterion_id: str) -> None:
    assert result.outcome is Outcome.CT_RECOMMENDED
    assert result.risk_level is level
    assert triggered_ids(result) == {criterion_id}
    assert result.missing_inputs == ()


def assert_not_required(result) -> None:
    assert result.outcome is Outcome.CT_NOT_REQUIRED
    assert result.triggered == ()


def test_clearly_negative_patient_does_not_require_ct():
    result = evaluate_cchr(negative_patient())

    assert result.outcome is Outcome.CT_NOT_REQUIRED
    assert result.risk_level is None
    assert result.triggered == ()
    assert result.exclusion_reasons == ()
    assert result.missing_inputs == ()
    assert all(c.status is not CriterionStatus.UNKNOWN for c in result.criteria)


# --- High risk (Panel 1) ---------------------------------------------------


def test_gcs_below_15_at_2h_is_high_risk():
    result = evaluate_cchr(negative_patient(initial_ed_gcs=14, gcs_2h_post_injury=14))
    assert_recommended(result, RiskLevel.HIGH, "cchr.high.gcs_below_15_at_2h")


def test_initial_gcs_below_15_that_recovers_by_2h_does_not_trigger():
    result = evaluate_cchr(negative_patient(initial_ed_gcs=13, gcs_2h_post_injury=15))
    assert_not_required(result)


def test_suspected_open_or_depressed_fracture_is_high_risk():
    result = evaluate_cchr(
        negative_patient(suspected_open_or_depressed_fracture=PRESENT)
    )
    assert_recommended(
        result, RiskLevel.HIGH, "cchr.high.suspected_open_or_depressed_fracture"
    )


@pytest.mark.parametrize(
    "sign",
    [
        "haemotympanum",
        "raccoon_eyes",
        "csf_otorrhoea_or_rhinorrhoea",
        "battle_sign",
    ],
)
def test_any_sign_of_basal_skull_fracture_is_high_risk(sign):
    result = evaluate_cchr(negative_patient(**{sign: PRESENT}))
    assert_recommended(result, RiskLevel.HIGH, "cchr.high.basal_skull_fracture_sign")


def test_vomiting_two_episodes_is_high_risk():
    result = evaluate_cchr(negative_patient(vomiting_episodes=2))
    assert_recommended(result, RiskLevel.HIGH, "cchr.high.vomiting_2_or_more")


def test_single_vomiting_episode_does_not_trigger():
    assert_not_required(evaluate_cchr(negative_patient(vomiting_episodes=1)))


def test_age_65_is_high_risk():
    result = evaluate_cchr(negative_patient(age_years=65))
    assert_recommended(result, RiskLevel.HIGH, "cchr.high.age_65_or_over")


def test_age_64_does_not_trigger():
    assert_not_required(evaluate_cchr(negative_patient(age_years=64)))


# --- Medium risk (Panel 1) -------------------------------------------------


def test_retrograde_amnesia_over_30_min_is_medium_risk():
    result = evaluate_cchr(negative_patient(retrograde_amnesia_minutes=31))
    assert_recommended(
        result, RiskLevel.MEDIUM, "cchr.medium.retrograde_amnesia_over_30_min"
    )


def test_retrograde_amnesia_of_exactly_30_min_does_not_trigger():
    # Panel 1 says ">30 min"; Tables 3 and 6 say ">=30". Panel 1 is the rule.
    assert_not_required(evaluate_cchr(negative_patient(retrograde_amnesia_minutes=30)))


@pytest.mark.parametrize(
    "mechanism",
    [
        "pedestrian_struck_by_motor_vehicle",
        "ejected_from_motor_vehicle",
        "fall_from_height_gt_3ft_or_5_stairs",
    ],
)
def test_dangerous_mechanism_is_medium_risk(mechanism):
    result = evaluate_cchr(negative_patient(**{mechanism: PRESENT}))
    assert_recommended(result, RiskLevel.MEDIUM, "cchr.medium.dangerous_mechanism")


# --- Combinations and reporting --------------------------------------------


def test_high_risk_takes_precedence_over_medium_risk_and_both_are_reported():
    result = evaluate_cchr(
        negative_patient(vomiting_episodes=3, ejected_from_motor_vehicle=PRESENT)
    )

    assert result.outcome is Outcome.CT_RECOMMENDED
    assert result.risk_level is RiskLevel.HIGH
    assert triggered_ids(result) == {
        "cchr.high.vomiting_2_or_more",
        "cchr.medium.dangerous_mechanism",
    }


def test_medium_risk_recommendation_notes_observation_alternative():
    result = evaluate_cchr(negative_patient(retrograde_amnesia_minutes=60))
    assert any("observation" in note for note in result.notes)


def test_every_criterion_cites_its_source():
    result = evaluate_cchr(negative_patient())
    for criterion in result.criteria:
        assert criterion.source.startswith("Stiell 2001"), criterion.id


def test_triggered_criterion_reports_inputs_used():
    result = evaluate_cchr(negative_patient(battle_sign=PRESENT))
    (criterion,) = result.triggered
    assert "battle_sign" in criterion.inputs_used
