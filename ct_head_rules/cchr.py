"""Canadian CT Head Rule. Educational implementation, not for clinical use.

Source: Stiell IG, Wells GA, Vandemheen K, et al. The Canadian CT Head Rule for
patients with minor head injury. Lancet 2001;357:1391-96. (sources/stiell2001.pdf)

Where the paper is inconsistent, Panel 1 (the rule as published) wins over the
derivation tables. Each such choice is noted next to the criterion it affects.
"""

from ct_head_rules.patient import Patient
from ct_head_rules.rules import (
    CriterionStatus,
    Outcome,
    RiskLevel,
    RuleResult,
    _any_of,
    _compare,
    _Criterion,
    _from_finding,
    decide,
    rule_inputs,
    with_notes,
)

# Journal pages 1391-96 are PDF pages 1-6. The eligibility sentence in Methods
# starts at the bottom of p1391 and runs onto p1392, where the exclusion list is.
_PAPER = "Stiell 2001, Lancet 357:1391-96"
SOURCE_PANEL_1 = f"{_PAPER}, Panel 1 (p1394)"
SOURCE_METHODS_PP1391_92 = (
    f"{_PAPER}, Methods: Study setting and population (pp1391-92)"
)
SOURCE_METHODS_P1392 = f"{_PAPER}, Methods: Study setting and population (p1392)"
SOURCE_MINOR_HEAD_INJURY = f"{_PAPER}, Methods (pp1391-92) and Panel 1 footnote (p1394)"
SOURCE_INITIAL_GCS = f"{_PAPER}, Methods (p1392) and Panel 1 footnote (p1394)"


# --- Inclusion criteria -----------------------------------------------------

INCLUSION_CRITERIA = (
    # Methods p1391: "blunt trauma to the head"; excluded (p1392) if "no clear
    # history of trauma as the primary event (eg, primary seizure or syncope)".
    _Criterion(
        "cchr.inclusion.blunt_head_trauma",
        "Blunt head trauma as the primary event",
        "inclusion",
        SOURCE_METHODS_PP1391_92,
        ("blunt_head_trauma",),
        lambda p: _from_finding(p.blunt_head_trauma),
    ),
    # Methods p1391 and Panel 1 footnote (p1394): "witnessed loss of
    # consciousness, definite amnesia, or witnessed disorientation". Patients
    # with none of these ("minimal head injury") are excluded (Methods p1392).
    _Criterion(
        "cchr.inclusion.loc_amnesia_or_disorientation",
        "Witnessed LOC, definite amnesia, or witnessed disorientation",
        "inclusion",
        SOURCE_MINOR_HEAD_INJURY,
        ("witnessed_loc", "definite_amnesia", "witnessed_disorientation"),
        lambda p: _any_of(
            p.witnessed_loc, p.definite_amnesia, p.witnessed_disorientation
        ),
    ),
    # Methods p1392 (first line): "GCS score of 13 or greater"; Panel 1
    # footnote (p1394): "GCS score of 13-15".
    _Criterion(
        "cchr.inclusion.initial_gcs_13_to_15",
        "Initial ED GCS 13-15",
        "inclusion",
        SOURCE_INITIAL_GCS,
        ("initial_ed_gcs",),
        lambda p: _compare(p.initial_ed_gcs, lambda gcs: 13 <= gcs <= 15),
    ),
    # Methods p1392: "injury within the past 24 h".
    _Criterion(
        "cchr.inclusion.injury_within_24h",
        "Injury within the past 24 h",
        "inclusion",
        SOURCE_METHODS_P1392,
        ("hours_since_injury",),
        lambda p: _compare(p.hours_since_injury, lambda hours: hours <= 24),
    ),
)


# --- Exclusion criteria (all Methods p1392) ---------------------------------


def _exclusion(id_suffix: str, label: str, field: str) -> _Criterion:
    return _Criterion(
        f"cchr.exclusion.{id_suffix}",
        label,
        "exclusion",
        SOURCE_METHODS_P1392,
        (field,),
        lambda p: _from_finding(getattr(p, field)),
    )


EXCLUSION_CRITERIA = (
    # Methods p1392: "were less than 16 years old".
    _Criterion(
        "cchr.exclusion.age_under_16",
        "Age under 16",
        "exclusion",
        SOURCE_METHODS_P1392,
        ("age_years",),
        lambda p: _compare(p.age_years, lambda age: age < 16),
    ),
    # Methods p1392: "had an obvious penetrating skull injury or obvious
    # depressed fracture". Distinct from the high-risk *suspected* fracture.
    _exclusion(
        "obvious_penetrating_or_depressed_fracture",
        "Obvious penetrating skull injury or obvious depressed fracture",
        "obvious_penetrating_injury_or_depressed_fracture",
    ),
    # Methods p1392: "had acute focal neurological deficit".
    _exclusion(
        "acute_focal_neuro_deficit",
        "Acute focal neurological deficit",
        "acute_focal_neuro_deficit",
    ),
    # Methods p1392: "had unstable vital signs associated with major trauma".
    _exclusion(
        "unstable_vitals_major_trauma",
        "Unstable vital signs associated with major trauma",
        "unstable_vitals_major_trauma",
    ),
    # Methods p1392: "had had a seizure before assessment in the emergency
    # department".
    _exclusion(
        "seizure_before_ed_assessment",
        "Seizure before ED assessment",
        "seizure_before_ed_assessment",
    ),
    # Methods p1392: "had a bleeding disorder or used oral anticoagulants (ie,
    # coumadin)". Split into two exclusions so the result names which applies.
    _exclusion("bleeding_disorder", "Bleeding disorder", "bleeding_disorder"),
    _exclusion("oral_anticoagulant", "Oral anticoagulant use", "oral_anticoagulant"),
    # Methods p1392: "had returned for reassessment of the same head injury".
    _exclusion(
        "return_visit_same_injury",
        "Returned for reassessment of the same injury",
        "return_visit_same_injury",
    ),
    # Methods p1392: "or were pregnant".
    _exclusion("pregnant", "Pregnant", "pregnant"),
)


# --- High-risk criteria (Panel 1: "High risk (for neurological intervention)")

HIGH_RISK_CRITERIA = (
    # Panel 1: "GCS score <15 at 2 h after injury".
    _Criterion(
        "cchr.high.gcs_below_15_at_2h",
        "GCS <15 at 2 h after injury",
        "high_risk",
        SOURCE_PANEL_1,
        ("gcs_2h_post_injury",),
        lambda p: _compare(p.gcs_2h_post_injury, lambda gcs: gcs < 15),
    ),
    # Panel 1: "Suspected open or depressed skull fracture".
    _Criterion(
        "cchr.high.suspected_open_or_depressed_fracture",
        "Suspected open or depressed skull fracture",
        "high_risk",
        SOURCE_PANEL_1,
        ("suspected_open_or_depressed_fracture",),
        lambda p: _from_finding(p.suspected_open_or_depressed_fracture),
    ),
    # Panel 1: "Any sign of basal skull fracture (haemotympanum, 'racoon' eyes,
    # cerebrospinal fluid otorrhoea/rhinorrhoea, Battle's sign)".
    _Criterion(
        "cchr.high.basal_skull_fracture_sign",
        "Any sign of basal skull fracture",
        "high_risk",
        SOURCE_PANEL_1,
        (
            "haemotympanum",
            "raccoon_eyes",
            "csf_otorrhoea_or_rhinorrhoea",
            "battle_sign",
        ),
        lambda p: _any_of(
            p.haemotympanum,
            p.raccoon_eyes,
            p.csf_otorrhoea_or_rhinorrhoea,
            p.battle_sign,
        ),
    ),
    # Panel 1: "Vomiting >=2 episodes".
    _Criterion(
        "cchr.high.vomiting_2_or_more",
        "Vomiting 2 or more episodes",
        "high_risk",
        SOURCE_PANEL_1,
        ("vomiting_episodes",),
        lambda p: _compare(p.vomiting_episodes, lambda n: n >= 2),
    ),
    # Panel 1: "Age >=65 years".
    _Criterion(
        "cchr.high.age_65_or_over",
        "Age 65 or over",
        "high_risk",
        SOURCE_PANEL_1,
        ("age_years",),
        lambda p: _compare(p.age_years, lambda age: age >= 65),
    ),
)


# --- Medium-risk criteria (Panel 1: "Medium risk (for brain injury on CT)") --

MEDIUM_RISK_CRITERIA = (
    # Panel 1: "Amnesia before impact >30 min". Tables 3 and 6 use ">=30 min";
    # we follow Panel 1.
    _Criterion(
        "cchr.medium.retrograde_amnesia_over_30_min",
        "Amnesia before impact over 30 min",
        "medium_risk",
        SOURCE_PANEL_1,
        ("retrograde_amnesia_minutes",),
        lambda p: _compare(p.retrograde_amnesia_minutes, lambda minutes: minutes > 30),
    ),
    # Panel 1: "Dangerous mechanism (pedestrian struck by motor vehicle,
    # occupant ejected from motor vehicle, fall from height >3 feet or five
    # stairs)". The Table 4 footnote's wider definition (adds assault with a
    # blunt object and heavy object falling on the head) is not used.
    _Criterion(
        "cchr.medium.dangerous_mechanism",
        "Dangerous mechanism",
        "medium_risk",
        SOURCE_PANEL_1,
        (
            "pedestrian_struck_by_motor_vehicle",
            "ejected_from_motor_vehicle",
            "fall_from_height_gt_3ft_or_5_stairs",
        ),
        lambda p: _any_of(
            p.pedestrian_struck_by_motor_vehicle,
            p.ejected_from_motor_vehicle,
            p.fall_from_height_gt_3ft_or_5_stairs,
        ),
    ),
)


CCHR_INPUTS = rule_inputs(
    *INCLUSION_CRITERIA, *EXCLUSION_CRITERIA, *HIGH_RISK_CRITERIA, *MEDIUM_RISK_CRITERIA
)


# --- Evaluation -------------------------------------------------------------

NOTE_NOT_APPLICABLE = (
    "The Canadian CT Head Rule was not derived for this patient and gives no "
    "guidance on CT. This is not a 'CT not required' result."
)
# Discussion pp1394 and 1396: CT is "mandatory" for high-risk patients; for
# medium-risk, management "might reasonably include either careful observation
# ... or urgent CT".
NOTE_MEDIUM_RISK = (
    "Medium risk only: the authors suggest CT or careful observation, depending "
    "on local resources (Stiell 2001, Discussion p1396)."
)
NOTE_HIGH_RISK_UNKNOWN = (
    "Some high risk criteria are unknown; if any is met, the risk level is high."
)
NOTE_GCS_2H_PENDING = (
    "Fewer than 2 h since injury, so GCS at 2 h is not yet known: "
    "re-evaluate at 2 h post-injury."
)


def evaluate_cchr(patient: Patient) -> RuleResult:
    """Apply the Canadian CT Head Rule to one patient."""
    result = decide(
        "cchr",
        patient,
        INCLUSION_CRITERIA,
        EXCLUSION_CRITERIA,
        (
            (RiskLevel.HIGH, Outcome.CT_RECOMMENDED, HIGH_RISK_CRITERIA),
            (RiskLevel.MEDIUM, Outcome.CT_RECOMMENDED, MEDIUM_RISK_CRITERIA),
        ),
    )

    notes = []
    if (
        patient.gcs_2h_post_injury is None
        and patient.hours_since_injury is not None
        and patient.hours_since_injury < 2
    ):
        notes.append(NOTE_GCS_2H_PENDING)
    if result.outcome is Outcome.NOT_APPLICABLE:
        notes.append(NOTE_NOT_APPLICABLE)
    if result.risk_level is RiskLevel.MEDIUM:
        notes.append(NOTE_MEDIUM_RISK)
        high_ids = {c.id for c in HIGH_RISK_CRITERIA}
        if any(
            c.id in high_ids and c.status is CriterionStatus.UNKNOWN
            for c in result.criteria
        ):
            notes.append(NOTE_HIGH_RISK_UNKNOWN)
    return with_notes(result, *notes)
