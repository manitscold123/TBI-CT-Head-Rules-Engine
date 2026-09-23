"""The PECARN predictors, by age group and tier.

Source: Kuppermann et al. 2009, Lancet 374:1160-70, Figure 3 (p1168), with
definitions from Panel 1 (p1161) and Selection of predictors (p1163).
"""

import pytest
from patients import ABSENT, PRESENT, UNKNOWN, negative_child

from ct_head_rules.pecarn import evaluate_pecarn
from ct_head_rules.rules import CriterionStatus, Outcome, RiskLevel


def triggered_ids(result) -> set[str]:
    return {c.id for c in result.triggered}


def criterion_ids(result) -> set[str]:
    return {c.id for c in result.criteria}


@pytest.mark.parametrize("age", [1, 5])
def test_child_with_no_predictors_does_not_require_ct(age):
    result = evaluate_pecarn(negative_child(age))

    assert result.rule == "pecarn"
    assert result.outcome is Outcome.CT_NOT_REQUIRED
    assert result.risk_level is None
    assert result.missing_inputs == ()


# --- CT recommended tier ------------------------------------------------------


@pytest.mark.parametrize(
    ("age", "overrides", "criterion_id"),
    [
        (1, {"initial_ed_gcs": 14}, "pecarn.under_2.altered_mental_status"),
        (
            1,
            {"other_altered_mental_status": PRESENT},
            "pecarn.under_2.altered_mental_status",
        ),
        (
            1,
            {"palpable_or_unclear_skull_fracture": PRESENT},
            "pecarn.under_2.palpable_skull_fracture",
        ),
        (5, {"initial_ed_gcs": 14}, "pecarn.2_and_over.altered_mental_status"),
        (
            5,
            {"other_altered_mental_status": PRESENT},
            "pecarn.2_and_over.altered_mental_status",
        ),
        (
            5,
            {"haemotympanum": PRESENT},
            "pecarn.2_and_over.basilar_skull_fracture_sign",
        ),
        (5, {"raccoon_eyes": PRESENT}, "pecarn.2_and_over.basilar_skull_fracture_sign"),
        (
            5,
            {"csf_otorrhoea_or_rhinorrhoea": PRESENT},
            "pecarn.2_and_over.basilar_skull_fracture_sign",
        ),
        (5, {"battle_sign": PRESENT}, "pecarn.2_and_over.basilar_skull_fracture_sign"),
    ],
)
def test_ct_recommended_predictors(age, overrides, criterion_id):
    result = evaluate_pecarn(negative_child(age, **overrides))

    assert result.outcome is Outcome.CT_RECOMMENDED
    assert result.risk_level is RiskLevel.HIGH
    assert triggered_ids(result) == {criterion_id}


# --- Observation or CT tier ---------------------------------------------------


@pytest.mark.parametrize(
    ("age", "overrides", "criterion_id"),
    [
        (
            1,
            {"non_frontal_scalp_haematoma": PRESENT},
            "pecarn.under_2.non_frontal_scalp_haematoma",
        ),
        (1, {"loc_duration_seconds": 5}, "pecarn.under_2.loc_5_seconds_or_more"),
        (1, {"severe_non_fall_mechanism": PRESENT}, "pecarn.under_2.severe_mechanism"),
        (
            1,
            {"not_acting_normally_per_parent": PRESENT},
            "pecarn.under_2.not_acting_normally",
        ),
        (5, {"history_of_loc": PRESENT}, "pecarn.2_and_over.history_of_loc"),
        (5, {"vomiting_episodes": 1}, "pecarn.2_and_over.vomiting"),
        (
            5,
            {"severe_non_fall_mechanism": PRESENT},
            "pecarn.2_and_over.severe_mechanism",
        ),
        (5, {"severe_headache": PRESENT}, "pecarn.2_and_over.severe_headache"),
    ],
)
def test_observation_or_ct_predictors(age, overrides, criterion_id):
    result = evaluate_pecarn(negative_child(age, **overrides))

    assert result.outcome is Outcome.OBSERVATION_OR_CT
    assert result.risk_level is RiskLevel.MEDIUM
    assert triggered_ids(result) == {criterion_id}
    assert any("parental preference" in note for note in result.notes)


def test_under_2_observation_note_mentions_infants_under_3_months():
    result = evaluate_pecarn(negative_child(1, not_acting_normally_per_parent=PRESENT))
    assert any("3 months" in note for note in result.notes)


def test_ct_recommended_tier_wins_and_both_tiers_are_reported():
    result = evaluate_pecarn(negative_child(5, initial_ed_gcs=14, vomiting_episodes=2))

    assert result.outcome is Outcome.CT_RECOMMENDED
    assert triggered_ids(result) == {
        "pecarn.2_and_over.altered_mental_status",
        "pecarn.2_and_over.vomiting",
    }


def test_unknown_ct_recommended_predictor_is_flagged_on_observation_result():
    result = evaluate_pecarn(
        negative_child(5, vomiting_episodes=1, other_altered_mental_status=UNKNOWN)
    )

    assert result.outcome is Outcome.OBSERVATION_OR_CT
    assert any("CT recommended" in note for note in result.notes)


# --- Edge values ----------------------------------------------------------------


def test_loc_under_5_seconds_does_not_trigger_under_2():
    result = evaluate_pecarn(negative_child(1, loc_duration_seconds=4))
    assert result.outcome is Outcome.CT_NOT_REQUIRED


@pytest.mark.parametrize(
    ("age", "height", "severe"),
    [
        (1, 0.9, False),  # "more than 0.9 m" for under 2
        (1, 1.0, True),
        (5, 1.5, False),  # "more than 1.5 m" for 2 and older
        (5, 1.6, True),
        (1, 1.2, True),  # the same fall is severe at 1 ...
        (5, 1.2, False),  # ... but not at 5
    ],
)
def test_fall_height_threshold_depends_on_age(age, height, severe):
    result = evaluate_pecarn(negative_child(age, fall_height_m=height))
    expected = Outcome.OBSERVATION_OR_CT if severe else Outcome.CT_NOT_REQUIRED
    assert result.outcome is expected


def test_age_2_uses_the_2_and_over_rule():
    result = evaluate_pecarn(negative_child(2))
    assert "pecarn.2_and_over.vomiting" in criterion_ids(result)
    assert "pecarn.under_2.palpable_skull_fracture" not in criterion_ids(result)


# --- Only the child's own age group counts --------------------------------------


def test_under_2_predictor_is_ignored_for_older_child():
    result = evaluate_pecarn(
        negative_child(5, palpable_or_unclear_skull_fracture=PRESENT)
    )
    assert result.outcome is Outcome.CT_NOT_REQUIRED


def test_other_age_groups_inputs_are_never_reported_missing():
    older = evaluate_pecarn(
        negative_child(5, palpable_or_unclear_skull_fracture=UNKNOWN)
    )
    younger = evaluate_pecarn(negative_child(1, severe_headache=UNKNOWN))

    assert older.missing_inputs == ()
    assert younger.missing_inputs == ()


def test_vomiting_is_not_a_predictor_under_2():
    result = evaluate_pecarn(negative_child(1, vomiting_episodes=3))
    assert result.outcome is Outcome.CT_NOT_REQUIRED


# --- One-way inferences from shared fields -----------------------------------


@pytest.mark.parametrize(
    "field", ["ejected_from_motor_vehicle", "pedestrian_struck_by_motor_vehicle"]
)
def test_canadian_vehicle_mechanism_implies_severe_mechanism(field):
    result = evaluate_pecarn(
        negative_child(5, severe_non_fall_mechanism=UNKNOWN, **{field: PRESENT})
    )
    assert triggered_ids(result) == {"pecarn.2_and_over.severe_mechanism"}


@pytest.mark.parametrize("field", ["witnessed_loc", "patient_reported_loc"])
def test_reported_loc_implies_history_of_loc(field):
    result = evaluate_pecarn(
        negative_child(5, history_of_loc=UNKNOWN, **{field: PRESENT})
    )
    assert triggered_ids(result) == {"pecarn.2_and_over.history_of_loc"}


def test_absent_vehicle_mechanisms_do_not_imply_no_severe_mechanism():
    result = evaluate_pecarn(negative_child(5, severe_non_fall_mechanism=UNKNOWN))

    by_id = {c.id: c for c in result.criteria}
    assert by_id["pecarn.2_and_over.severe_mechanism"].status is (
        CriterionStatus.UNKNOWN
    )
    assert result.outcome is Outcome.INDETERMINATE


def test_predictors_cite_kuppermann():
    for age in (1, 5):
        for criterion in evaluate_pecarn(negative_child(age)).criteria:
            assert criterion.source.startswith("Kuppermann 2009"), criterion.id


def test_absent_is_absent():
    assert negative_child(5, severe_headache=ABSENT).severe_headache is ABSENT
