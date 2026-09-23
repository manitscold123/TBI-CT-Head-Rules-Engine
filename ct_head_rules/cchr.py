"""Canadian CT Head Rule. Educational implementation, not for clinical use.

Source: Stiell IG, Wells GA, Vandemheen K, et al. The Canadian CT Head Rule for
patients with minor head injury. Lancet 2001;357:1391-96. (sources/stiell2001.pdf)

Where the paper is inconsistent, Panel 1 (the rule as published) wins over the
derivation tables. Each such choice is noted next to the criterion it affects.
"""

import dataclasses
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from ct_head_rules.findings import Finding

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


@dataclass(frozen=True)
class CCHRInput:
    """Everything the rule needs. Use Finding.UNKNOWN or None when not known."""

    # --- Applicability ---
    age_years: int | None
    blunt_head_trauma: Finding  # trauma was the primary event, not seizure/syncope
    witnessed_loc: Finding
    definite_amnesia: Finding
    witnessed_disorientation: Finding
    initial_ed_gcs: int | None
    hours_since_injury: float | None
    obvious_penetrating_injury_or_depressed_fracture: Finding
    acute_focal_neuro_deficit: Finding
    unstable_vitals_major_trauma: Finding
    seizure_before_ed_assessment: Finding
    bleeding_disorder: Finding
    # The paper says "used oral anticoagulants (ie, coumadin)". Treating DOACs
    # as included and antiplatelets as excluded is our interpretation, not the
    # paper's; the caller decides what counts as PRESENT.
    oral_anticoagulant: Finding
    return_visit_same_injury: Finding
    pregnant: Finding

    # --- High risk ---
    gcs_2h_post_injury: int | None  # None until 2 h have passed, or if not recorded
    suspected_open_or_depressed_fracture: Finding
    haemotympanum: Finding
    raccoon_eyes: Finding
    csf_otorrhoea_or_rhinorrhoea: Finding
    battle_sign: Finding
    vomiting_episodes: int | None

    # --- Medium risk ---
    retrograde_amnesia_minutes: float | None  # amnesia before impact
    pedestrian_struck_by_motor_vehicle: Finding
    ejected_from_motor_vehicle: Finding
    fall_from_height_gt_3ft_or_5_stairs: Finding

    def __post_init__(self) -> None:
        for field in dataclasses.fields(self):
            value = getattr(self, field.name)
            if field.type is Finding:
                if not isinstance(value, Finding):
                    raise TypeError(
                        f"{field.name} must be a Finding (use Finding.UNKNOWN "
                        f"when not known), got {value!r}"
                    )
            elif value is not None:
                if isinstance(value, bool) or not isinstance(value, int | float):
                    raise TypeError(
                        f"{field.name} must be a number or None, got {value!r}"
                    )
                if value < 0:
                    raise ValueError(f"{field.name} must not be negative, got {value}")

        for name in ("age_years", "vomiting_episodes"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, int):
                raise ValueError(f"{name} must be a whole number, got {value!r}")

        # The Glasgow Coma Scale runs from 3 to 15 in whole points.
        for name in ("initial_ed_gcs", "gcs_2h_post_injury"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, int) or not 3 <= value <= 15
            ):
                raise ValueError(
                    f"{name} must be a whole GCS score 3-15, got {value!r}"
                )


class CriterionStatus(Enum):
    MET = "met"
    NOT_MET = "not_met"
    UNKNOWN = "unknown"


class RiskLevel(Enum):
    HIGH = "high"  # for neurological intervention
    MEDIUM = "medium"  # for brain injury on CT


class Outcome(Enum):
    CT_RECOMMENDED = "ct_recommended"
    CT_NOT_REQUIRED = "ct_not_required"  # only when every relevant input is known
    NOT_APPLICABLE = "not_applicable"  # excluded, or outside the rule's population
    INDETERMINATE = "indeterminate"  # missing inputs prevent a conclusion


CriterionKind = Literal["inclusion", "exclusion", "high_risk", "medium_risk"]


@dataclass(frozen=True)
class CriterionResult:
    """One criterion checked against one patient.

    For inclusions, MET means the requirement is satisfied. For exclusions,
    MET means the patient is excluded.
    """

    id: str
    label: str
    kind: CriterionKind
    status: CriterionStatus
    source: str
    inputs_used: tuple[str, ...]
    missing_inputs: tuple[str, ...]


@dataclass(frozen=True)
class CCHRResult:
    outcome: Outcome
    risk_level: RiskLevel | None  # set only when outcome is CT_RECOMMENDED
    triggered: tuple[CriterionResult, ...]  # met risk criteria, if CT_RECOMMENDED
    exclusion_reasons: tuple[CriterionResult, ...]  # why the rule does not apply
    criteria: tuple[CriterionResult, ...]  # every criterion checked, for audit
    missing_inputs: tuple[str, ...]  # in CCHRInput field order
    notes: tuple[str, ...]


# --- Status helpers ---------------------------------------------------------


def _is_missing(value: object) -> bool:
    return value is None or value is Finding.UNKNOWN


def _from_finding(value: Finding) -> CriterionStatus:
    if value is Finding.PRESENT:
        return CriterionStatus.MET
    if value is Finding.ABSENT:
        return CriterionStatus.NOT_MET
    return CriterionStatus.UNKNOWN


def _any_of(*values: Finding) -> CriterionStatus:
    """MET if any is present; NOT_MET only if every one is known absent."""
    statuses = [_from_finding(v) for v in values]
    if CriterionStatus.MET in statuses:
        return CriterionStatus.MET
    if all(s is CriterionStatus.NOT_MET for s in statuses):
        return CriterionStatus.NOT_MET
    return CriterionStatus.UNKNOWN


def _compare(
    value: float | None, predicate: Callable[[float], bool]
) -> CriterionStatus:
    if value is None:
        return CriterionStatus.UNKNOWN
    return CriterionStatus.MET if predicate(value) else CriterionStatus.NOT_MET


@dataclass(frozen=True)
class _Criterion:
    id: str
    label: str
    kind: CriterionKind
    source: str
    inputs: tuple[str, ...]
    evaluate: Callable[[CCHRInput], CriterionStatus]

    def apply(self, patient: CCHRInput) -> CriterionResult:
        return CriterionResult(
            id=self.id,
            label=self.label,
            kind=self.kind,
            status=self.evaluate(patient),
            source=self.source,
            inputs_used=self.inputs,
            missing_inputs=tuple(
                name for name in self.inputs if _is_missing(getattr(patient, name))
            ),
        )


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


def _missing_inputs(
    patient: CCHRInput, criteria: Iterable[CriterionResult]
) -> tuple[str, ...]:
    missing = {name for c in criteria for name in c.missing_inputs}
    return tuple(f.name for f in dataclasses.fields(patient) if f.name in missing)


def _any_status(criteria: Iterable[CriterionResult], status: CriterionStatus) -> bool:
    return any(c.status is status for c in criteria)


def evaluate_cchr(patient: CCHRInput) -> CCHRResult:
    """Apply the Canadian CT Head Rule to one patient."""
    inclusions = tuple(c.apply(patient) for c in INCLUSION_CRITERIA)
    exclusions = tuple(c.apply(patient) for c in EXCLUSION_CRITERIA)
    high = tuple(c.apply(patient) for c in HIGH_RISK_CRITERIA)
    medium = tuple(c.apply(patient) for c in MEDIUM_RISK_CRITERIA)
    criteria = (*inclusions, *exclusions, *high, *medium)
    missing = _missing_inputs(patient, criteria)

    notes: list[str] = []
    if (
        patient.gcs_2h_post_injury is None
        and patient.hours_since_injury is not None
        and patient.hours_since_injury < 2
    ):
        notes.append(NOTE_GCS_2H_PENDING)

    def result(
        outcome: Outcome,
        risk_level: RiskLevel | None = None,
        triggered: tuple[CriterionResult, ...] = (),
        exclusion_reasons: tuple[CriterionResult, ...] = (),
    ) -> CCHRResult:
        return CCHRResult(
            outcome=outcome,
            risk_level=risk_level,
            triggered=triggered,
            exclusion_reasons=exclusion_reasons,
            criteria=criteria,
            missing_inputs=missing,
            notes=tuple(notes),
        )

    # 1. A known exclusion or failed inclusion means the rule does not apply,
    #    whatever else is known or missing.
    reasons = tuple(
        c for c in inclusions if c.status is CriterionStatus.NOT_MET
    ) + tuple(c for c in exclusions if c.status is CriterionStatus.MET)
    if reasons:
        notes.append(NOTE_NOT_APPLICABLE)
        return result(Outcome.NOT_APPLICABLE, exclusion_reasons=reasons)

    # 2-3. A met risk criterion recommends CT even if applicability is not
    #      fully known: missing data could only make the rule not apply (no
    #      guidance), never make CT unnecessary.
    triggered = tuple(c for c in (*high, *medium) if c.status is CriterionStatus.MET)
    if _any_status(high, CriterionStatus.MET):
        return result(Outcome.CT_RECOMMENDED, RiskLevel.HIGH, triggered)
    if triggered:
        notes.append(NOTE_MEDIUM_RISK)
        if _any_status(high, CriterionStatus.UNKNOWN):
            notes.append(NOTE_HIGH_RISK_UNKNOWN)
        return result(Outcome.CT_RECOMMENDED, RiskLevel.MEDIUM, triggered)

    # 4. Nothing met, but something unknown: unknown is never negative.
    if _any_status(criteria, CriterionStatus.UNKNOWN):
        return result(Outcome.INDETERMINATE)

    # 5. Eligible, every criterion known, none met.
    return result(Outcome.CT_NOT_REQUIRED)
