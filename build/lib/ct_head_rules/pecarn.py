"""PECARN rules for children. Educational implementation, not for clinical use.

Source: Kuppermann N, Holmes JF, Dayan PS, et al. Identification of children at
very low risk of clinically-important brain injuries after head trauma: a
prospective cohort study. Lancet 2009;374:1160-70.
(sources/Kuppermann_2009_The-Lancet_000.pdf)

Two rules, one for children under 2 and one for 2 and older, each with three
outcomes (Figure 3, p1168): CT recommended; observation versus CT on the basis
of other clinical factors; CT not recommended. Loss of consciousness is not
required to be eligible, unlike the Canadian and New Orleans rules.

One study exclusion is deliberately not implemented: "neuroimaging at an
outside hospital before transfer" (p1162). Like Haydel's "declined CT", it
describes the study's process, not whether the rule fits the child.
"""

from ct_head_rules.findings import Finding
from ct_head_rules.patient import Patient
from ct_head_rules.rules import (
    CriterionStatus,
    Outcome,
    RiskLevel,
    RuleResult,
    _any_of,
    _compare,
    _Criterion,
    _either,
    _from_finding,
    _in_field_order,
    _present_implies,
    decide,
    rule_inputs,
    with_notes,
)

# Journal pages 1160-1170 are PDF pages 1-11.
_PAPER = "Kuppermann 2009, Lancet 374:1160-70"
SOURCE_METHODS_P1161 = f"{_PAPER}, Methods: Patients and setting (p1161)"
SOURCE_ELIGIBILITY = f"{_PAPER}, Methods: Inclusion and exclusion criteria (p1162)"
SOURCE_FIGURE_3 = f"{_PAPER}, Figure 3 (p1168)"
# Figure 3 gives the tiers; these give each predictor's definition.
SOURCE_PANEL_1 = f"{_PAPER}, Panel 1 (p1161) and Figure 3 (p1168)"
SOURCE_PREDICTORS = f"{_PAPER}, Selection of predictors (p1163) and Figure 3 (p1168)"


# --- Inclusion criteria -----------------------------------------------------

INCLUSION_CRITERIA = (
    # p1161: "patients younger than 18 years with head trauma".
    _Criterion(
        "pecarn.inclusion.age_under_18",
        "Age under 18",
        "inclusion",
        SOURCE_METHODS_P1161,
        ("age_years",),
        lambda p: _compare(p.age_years, lambda age: age < 18),
    ),
    # p1162: "Children presenting within 24 h of head trauma were eligible."
    _Criterion(
        "pecarn.inclusion.injury_within_24h",
        "Injury within the past 24 h",
        "inclusion",
        SOURCE_ELIGIBILITY,
        ("hours_since_injury",),
        lambda p: _compare(p.hours_since_injury, lambda hours: hours <= 24),
    ),
    # p1162: patients with "GCS scores less than 14 were enrolled but are being
    # analysed separately", so the rules cover GCS 14-15 only.
    _Criterion(
        "pecarn.inclusion.gcs_14_to_15",
        "GCS 14-15",
        "inclusion",
        SOURCE_ELIGIBILITY,
        ("initial_ed_gcs",),
        lambda p: _compare(p.initial_ed_gcs, lambda gcs: 14 <= gcs <= 15),
    ),
)


# --- Exclusion criteria (all p1162) -----------------------------------------


def _exclusion(field: str, label: str) -> _Criterion:
    return _Criterion(
        f"pecarn.exclusion.{field}",
        label,
        "exclusion",
        SOURCE_ELIGIBILITY,
        (field,),
        lambda p: _from_finding(getattr(p, field)),
    )


EXCLUSION_CRITERIA = (
    # p1162: "trivial injury mechanisms defined by ground-level falls or
    # walking or running into stationary objects, and no signs or symptoms of
    # head trauma other than scalp abrasions and lacerations".
    _exclusion(
        "trivial_mechanism_no_symptoms",
        "Trivial mechanism with no signs or symptoms of head trauma",
    ),
    # p1162: "penetrating trauma, known brain tumours, pre-existing
    # neurological disorders complicating assessment".
    _exclusion("penetrating_trauma", "Penetrating trauma"),
    _exclusion("brain_tumour", "Known brain tumour"),
    _exclusion(
        "neuro_disorder_complicating_assessment",
        "Pre-existing neurological disorder complicating assessment",
    ),
    # p1162: "Patients with ventricular shunts, bleeding disorders ... were
    # enrolled but are being analysed separately."
    _exclusion("ventricular_shunt", "Ventricular shunt"),
    _exclusion("bleeding_disorder", "Bleeding disorder"),
)


# --- Predictors shared by both age groups, with age-specific details --------


def _altered_mental_status(branch: str) -> _Criterion:
    # p1163: "altered mental status was defined a priori by GCS score lower
    # than 15, agitation, sleepiness, slow responses, or repetitive
    # questioning". Figure 3: CT recommended in both age groups.
    return _Criterion(
        f"pecarn.{branch}.altered_mental_status",
        "Altered mental status (GCS 14, agitation, somnolence, repetitive "
        "questioning or slow response)",
        "high_risk",
        SOURCE_PREDICTORS,
        ("initial_ed_gcs", "other_altered_mental_status"),
        lambda p: _either(
            _compare(p.initial_ed_gcs, lambda gcs: gcs < 15),
            _from_finding(p.other_altered_mental_status),
        ),
    )


def _severe_mechanism(branch: str, fall_threshold_m: float) -> _Criterion:
    # p1163 and Figure 3 footnote (p1168): "motor vehicle crash with patient
    # ejection, death of another passenger, or rollover; pedestrian or
    # bicyclist without helmet struck by a motorised vehicle; falls of more
    # than 1.5 m (5 feet) for children aged 2 years and older and more than
    # 0.9 m (3 feet) for those younger than 2 years; or head struck by a
    # high-impact object". "Without helmet" is read as applying only to the
    # cyclist. The Canadian rule's ejection and pedestrian fields describe the
    # same events, so they count when PRESENT; never when ABSENT.
    return _Criterion(
        f"pecarn.{branch}.severe_mechanism",
        f"Severe mechanism of injury (fall over {fall_threshold_m} m)",
        "medium_risk",
        SOURCE_PREDICTORS,
        ("fall_height_m", "severe_non_fall_mechanism"),
        lambda p: _either(
            _compare(p.fall_height_m, lambda height: height > fall_threshold_m),
            _present_implies(
                p.severe_non_fall_mechanism,
                p.ejected_from_motor_vehicle,
                p.pedestrian_struck_by_motor_vehicle,
            ),
        ),
        also_reads=("ejected_from_motor_vehicle", "pedestrian_struck_by_motor_vehicle"),
    )


# --- Children younger than 2 (Figure 3A) ------------------------------------

UNDER_2_CT = (
    _altered_mental_status("under_2"),
    # Panel 1: "Palpable skull fracture: on digital inspection, or unclear on
    # the basis of swelling or distortion of the scalp".
    _Criterion(
        "pecarn.under_2.palpable_skull_fracture",
        "Palpable or unclear skull fracture",
        "high_risk",
        SOURCE_PANEL_1,
        ("palpable_or_unclear_skull_fracture",),
        lambda p: _from_finding(p.palpable_or_unclear_skull_fracture),
    ),
)

UNDER_2_OBSERVATION = (
    # Panel 1 records scalp haematoma location; Figure 3A: "Occipital or
    # parietal or temporal scalp haematoma".
    _Criterion(
        "pecarn.under_2.non_frontal_scalp_haematoma",
        "Occipital, parietal or temporal scalp haematoma",
        "medium_risk",
        SOURCE_PANEL_1,
        ("non_frontal_scalp_haematoma",),
        lambda p: _from_finding(p.non_frontal_scalp_haematoma),
    ),
    # Figure 3A: "history of LOC >=5 s".
    _Criterion(
        "pecarn.under_2.loc_5_seconds_or_more",
        "Loss of consciousness for 5 s or more",
        "medium_risk",
        SOURCE_FIGURE_3,
        ("loc_duration_seconds",),
        lambda p: _compare(p.loc_duration_seconds, lambda seconds: seconds >= 5),
    ),
    _severe_mechanism("under_2", fall_threshold_m=0.9),
    # Panel 1: "Parental report of whether the patient is acting normally";
    # Figure 3A: "not acting normally per parent".
    _Criterion(
        "pecarn.under_2.not_acting_normally",
        "Not acting normally, according to a parent",
        "medium_risk",
        SOURCE_PANEL_1,
        ("not_acting_normally_per_parent",),
        lambda p: _from_finding(p.not_acting_normally_per_parent),
    ),
)


# --- Children aged 2 and older (Figure 3B) ----------------------------------

TWO_AND_OVER_CT = (
    _altered_mental_status("2_and_over"),
    # Panel 1: "Signs of basilar skull fracture: such as retro-auricular
    # bruising (Battle's sign), periorbital bruising (raccoon eyes),
    # haemotympanum, cerebral spinal fluid otorrhoea, or cerebral spinal fluid
    # rhinorrhoea". We treat the named signs as the definition.
    _Criterion(
        "pecarn.2_and_over.basilar_skull_fracture_sign",
        "Signs of basilar skull fracture",
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
)

TWO_AND_OVER_OBSERVATION = (
    # Figure 2B (p1167) splits on LOC "Yes or suspected"; Figure 3B: "History
    # of LOC". Witnessed or patient-reported LOC counts when PRESENT.
    _Criterion(
        "pecarn.2_and_over.history_of_loc",
        "History of loss of consciousness (known or suspected)",
        "medium_risk",
        f"{_PAPER}, Figure 2B (p1167) and Figure 3 (p1168)",
        ("history_of_loc",),
        lambda p: _present_implies(
            p.history_of_loc, p.witnessed_loc, p.patient_reported_loc
        ),
        also_reads=("witnessed_loc", "patient_reported_loc"),
    ),
    # p1165: vomiting's "simple presence was identified as the most useful
    # form"; Figure 3B: "history of vomiting".
    _Criterion(
        "pecarn.2_and_over.vomiting",
        "History of vomiting",
        "medium_risk",
        f"{_PAPER}, Results (p1165) and Figure 3 (p1168)",
        ("vomiting_episodes",),
        lambda p: _compare(p.vomiting_episodes, lambda n: n >= 1),
    ),
    _severe_mechanism("2_and_over", fall_threshold_m=1.5),
    # Panel 1: headache severity "severe [intense]"; Figure 3B: "severe
    # headache".
    _Criterion(
        "pecarn.2_and_over.severe_headache",
        "Severe headache",
        "medium_risk",
        SOURCE_PANEL_1,
        ("severe_headache",),
        lambda p: _from_finding(p.severe_headache),
    ),
)

# Oral anticoagulant use is read only for a note, never as a criterion.
PECARN_INPUTS = _in_field_order(
    (
        *rule_inputs(
            *INCLUSION_CRITERIA,
            *EXCLUSION_CRITERIA,
            *UNDER_2_CT,
            *UNDER_2_OBSERVATION,
            *TWO_AND_OVER_CT,
            *TWO_AND_OVER_OBSERVATION,
        ),
        "oral_anticoagulant",
    )
)


# --- Evaluation -------------------------------------------------------------

NOTE_NOT_APPLICABLE = (
    "The PECARN rules were not derived for this patient and give no guidance on "
    "CT. This is not a 'CT not required' result."
)
NOTE_GCS_BELOW_14 = (
    "PECARN enrolled children with GCS below 14 but analysed them separately "
    "(Kuppermann 2009, p1162)."
)
NOTE_AGE_UNKNOWN = "Age is needed to choose between the under-2 and 2-and-over rules."
# Figure 3 (p1168) and Discussion (p1169).
NOTE_OBSERVATION = (
    "The authors suggest choosing observation or CT based on physician "
    "experience, multiple versus isolated findings, worsening symptoms or signs "
    "during ED observation, and parental preference (Kuppermann 2009, Figure 3)."
)
NOTE_UNDER_3_MONTHS = (
    " For infants younger than 3 months, CT should be more strongly considered (p1169)."
)
NOTE_CT_TIER_UNKNOWN = (
    "Some CT recommended predictors are unknown; if any is present, CT is recommended."
)
# p1162 excludes "bleeding disorders"; anticoagulants are not mentioned.
NOTE_ANTICOAGULANT = (
    "Anticoagulant use: Kuppermann 2009 excluded bleeding disorders (p1162) but "
    "does not mention anticoagulants."
)


def evaluate_pecarn(patient: Patient) -> RuleResult:
    """Apply the PECARN rule for the child's age group."""
    age = patient.age_years
    if age is None:
        tiers = ()
    elif age < 2:
        tiers = (
            (RiskLevel.HIGH, Outcome.CT_RECOMMENDED, UNDER_2_CT),
            (RiskLevel.MEDIUM, Outcome.OBSERVATION_OR_CT, UNDER_2_OBSERVATION),
        )
    else:
        tiers = (
            (RiskLevel.HIGH, Outcome.CT_RECOMMENDED, TWO_AND_OVER_CT),
            (RiskLevel.MEDIUM, Outcome.OBSERVATION_OR_CT, TWO_AND_OVER_OBSERVATION),
        )
    result = decide("pecarn", patient, INCLUSION_CRITERIA, EXCLUSION_CRITERIA, tiers)

    notes = []
    if age is None:
        notes.append(NOTE_AGE_UNKNOWN)
    if result.outcome is Outcome.NOT_APPLICABLE:
        notes.append(NOTE_NOT_APPLICABLE)
    if patient.initial_ed_gcs is not None and patient.initial_ed_gcs < 14:
        notes.append(NOTE_GCS_BELOW_14)
    if result.outcome is Outcome.OBSERVATION_OR_CT:
        notes.append(NOTE_OBSERVATION + (NOTE_UNDER_3_MONTHS if age < 2 else ""))
        ct_ids = {c.id for c in tiers[0][2]}
        if any(
            c.id in ct_ids and c.status is CriterionStatus.UNKNOWN
            for c in result.criteria
        ):
            notes.append(NOTE_CT_TIER_UNKNOWN)
    if patient.oral_anticoagulant is Finding.PRESENT:
        notes.append(NOTE_ANTICOAGULANT)
    return with_notes(result, *notes)
