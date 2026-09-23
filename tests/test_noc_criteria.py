"""The seven findings of the New Orleans Criteria.

Source: Haydel et al. 2000, N Engl J Med 343:100-05, Methods and Results (p101).
"""

import pytest
from patients import ABSENT, PRESENT, UNKNOWN, negative_patient

from ct_head_rules.noc import evaluate_noc
from ct_head_rules.rules import CriterionStatus, Outcome

# Canadian CT Head Rule fields that are signs of skull fracture (Stiell 2001,
# Panel 1 and Methods). Haydel p101 counts signs of skull fracture as physical
# evidence of trauma above the clavicles.
SKULL_FRACTURE_SIGNS = [
    "suspected_open_or_depressed_fracture",
    "obvious_penetrating_injury_or_depressed_fracture",
    "haemotympanum",
    "raccoon_eyes",
    "csf_otorrhoea_or_rhinorrhoea",
    "battle_sign",
]


def triggered_ids(result) -> set[str]:
    return {c.id for c in result.triggered}


def assert_recommended(result, criterion_id: str) -> None:
    assert result.outcome is Outcome.CT_RECOMMENDED
    assert result.risk_level is None  # the criteria have a single tier
    assert triggered_ids(result) == {criterion_id}


def assert_not_required(result) -> None:
    assert result.outcome is Outcome.CT_NOT_REQUIRED
    assert result.triggered == ()


def status_of(result, criterion_id: str) -> CriterionStatus:
    return {c.id: c for c in result.criteria}[criterion_id].status


def test_clearly_negative_patient_does_not_require_ct():
    result = evaluate_noc(negative_patient())

    assert result.rule == "noc"
    assert result.outcome is Outcome.CT_NOT_REQUIRED
    assert result.risk_level is None
    assert result.triggered == ()
    assert result.exclusion_reasons == ()
    assert result.missing_inputs == ()


@pytest.mark.parametrize(
    ("field", "criterion_id"),
    [
        ("headache", "noc.finding.headache"),
        ("drug_or_alcohol_intoxication", "noc.finding.drug_or_alcohol_intoxication"),
        ("short_term_memory_deficit", "noc.finding.short_term_memory_deficit"),
        ("trauma_above_clavicles", "noc.finding.trauma_above_clavicles"),
        ("post_traumatic_seizure", "noc.finding.seizure"),
    ],
)
def test_finding_present_recommends_ct(field, criterion_id):
    result = evaluate_noc(negative_patient(**{field: PRESENT}))
    assert_recommended(result, criterion_id)
    assert result.missing_inputs == ()


def test_pecarn_severe_headache_implies_headache():
    # Every severe headache (Kuppermann) is "any head pain" (Haydel p101).
    result = evaluate_noc(negative_patient(headache=UNKNOWN, severe_headache=PRESENT))
    assert_recommended(result, "noc.finding.headache")
    assert result.missing_inputs == ("headache",)


def test_any_vomiting_recommends_ct():
    # Vomiting: "any emesis after the traumatic event" (p101). The Canadian
    # rule needs 2 or more episodes.
    assert_recommended(
        evaluate_noc(negative_patient(vomiting_episodes=1)), "noc.finding.vomiting"
    )


def test_no_vomiting_does_not_trigger():
    assert_not_required(evaluate_noc(negative_patient(vomiting_episodes=0)))


def test_age_61_recommends_ct():
    result = evaluate_noc(negative_patient(age_years=61))
    assert_recommended(result, "noc.finding.age_over_60")


def test_age_60_does_not_trigger():
    # "Age over 60 years" (p101); the Canadian rule's threshold is 65 or over.
    assert_not_required(evaluate_noc(negative_patient(age_years=60)))


def test_findings_are_risk_factors_citing_haydel():
    result = evaluate_noc(negative_patient(headache=PRESENT))
    (criterion,) = result.triggered
    assert criterion.kind == "risk_factor"
    assert criterion.source.startswith("Haydel 2000")


def test_several_findings_are_all_reported():
    result = evaluate_noc(
        negative_patient(headache=PRESENT, drug_or_alcohol_intoxication=PRESENT)
    )
    assert triggered_ids(result) == {
        "noc.finding.headache",
        "noc.finding.drug_or_alcohol_intoxication",
    }


# --- Trauma above the clavicles: inferred from skull fracture signs ---------


@pytest.mark.parametrize("sign", SKULL_FRACTURE_SIGNS)
def test_skull_fracture_sign_implies_trauma_above_clavicles(sign):
    result = evaluate_noc(
        negative_patient(trauma_above_clavicles=UNKNOWN, **{sign: PRESENT})
    )

    assert_recommended(result, "noc.finding.trauma_above_clavicles")
    # Still unknown, so still reported, even though the finding is met.
    assert result.missing_inputs == ("trauma_above_clavicles",)


def test_present_sign_wins_over_absent_trauma_above_clavicles():
    result = evaluate_noc(
        negative_patient(trauma_above_clavicles=ABSENT, battle_sign=PRESENT)
    )
    assert_recommended(result, "noc.finding.trauma_above_clavicles")


def test_absent_skull_fracture_signs_do_not_imply_absent_trauma():
    # Only PRESENT carries over from the Canadian fields, never ABSENT.
    result = evaluate_noc(negative_patient(trauma_above_clavicles=UNKNOWN))

    assert status_of(result, "noc.finding.trauma_above_clavicles") is (
        CriterionStatus.UNKNOWN
    )
    assert result.outcome is Outcome.INDETERMINATE


def test_unknown_skull_fracture_signs_do_not_block_a_negative():
    unknown_signs = {sign: UNKNOWN for sign in SKULL_FRACTURE_SIGNS}
    result = evaluate_noc(negative_patient(**unknown_signs))

    assert status_of(result, "noc.finding.trauma_above_clavicles") is (
        CriterionStatus.NOT_MET
    )
    assert result.outcome is Outcome.CT_NOT_REQUIRED
    assert result.missing_inputs == ()


def test_inferred_criterion_lists_the_canadian_fields_it_read():
    result = evaluate_noc(negative_patient())
    criterion = {c.id: c for c in result.criteria}["noc.finding.trauma_above_clavicles"]
    assert criterion.inputs_used == ("trauma_above_clavicles", *SKULL_FRACTURE_SIGNS)
