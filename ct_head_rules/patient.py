"""The patient record shared by all rules. Educational use only.

Every field defaults to unknown, so a caller gives only what is known and each
rule reports the inputs it still needs. Where the two papers describe similar
findings differently, each gets its own field rather than one field meaning
two things; the help text gives each paper's definition.

Sources:
- Stiell IG, et al. The Canadian CT Head Rule. Lancet 2001;357:1391-96.
- Haydel MJ, et al. Indications for CT in minor head injury. N Engl J Med
  2000;343:100-05 (the New Orleans Criteria).
"""

import dataclasses
from dataclasses import dataclass

from ct_head_rules.findings import Finding

STIELL = "Stiell 2001"
HAYDEL = "Haydel 2000"


def _finding(help_text: str) -> Finding:
    return dataclasses.field(default=Finding.UNKNOWN, metadata={"help": help_text})


def _number(help_text: str):
    return dataclasses.field(default=None, metadata={"help": help_text})


@dataclass(frozen=True, kw_only=True)
class Patient:
    # --- Canadian CT Head Rule; the help text notes which New Orleans shares ---
    age_years: int | None = _number(
        f"Age in years. {STIELL}: 16+ eligible, 65+ high risk. "
        f"{HAYDEL}: 3+ eligible, over 60 is a finding."
    )
    blunt_head_trauma: Finding = _finding(
        f"Blunt head trauma was the primary event, not e.g. seizure or syncope "
        f"({STIELL}, pp1391-92)."
    )
    witnessed_loc: Finding = _finding(
        f"Loss of consciousness seen by a witness ({STIELL} p1391; {HAYDEL} p101)."
    )
    definite_amnesia: Finding = _finding(
        f"Definite amnesia; the paper does not define its type ({STIELL}, p1391)."
    )
    witnessed_disorientation: Finding = _finding(
        f"Disorientation seen by a witness ({STIELL}, p1391)."
    )
    initial_ed_gcs: int | None = _number(
        f"GCS on arrival in the ED. {STIELL}: 13-15 eligible. "
        f"{HAYDEL}: must be 15 (p101)."
    )
    hours_since_injury: float | None = _number(
        f"Hours since injury; both rules need 24 or less ({STIELL} p1392; "
        f"{HAYDEL} p100)."
    )
    obvious_penetrating_injury_or_depressed_fracture: Finding = _finding(
        f"Obvious penetrating skull injury or obvious depressed fracture "
        f"({STIELL} exclusion, p1392)."
    )
    acute_focal_neuro_deficit: Finding = _finding(
        f"Acute focal neurological deficit ({STIELL} exclusion, p1392)."
    )
    unstable_vitals_major_trauma: Finding = _finding(
        f"Unstable vital signs with major trauma ({STIELL} exclusion, p1392)."
    )
    seizure_before_ed_assessment: Finding = _finding(
        f"Seizure before ED assessment ({STIELL} exclusion, p1392)."
    )
    # The paper says "used oral anticoagulants (ie, coumadin)". Treating DOACs
    # as included and antiplatelets as excluded is our interpretation, not the
    # paper's; the caller decides what counts as PRESENT.
    bleeding_disorder: Finding = _finding(
        f"Bleeding or clotting disorder. {STIELL}: exclusion (p1392). "
        f"{HAYDEL}: could not be evaluated (p103)."
    )
    oral_anticoagulant: Finding = _finding(
        f"Oral anticoagulant use; the papers name coumadin/warfarin. {STIELL}: "
        f"exclusion (p1392). {HAYDEL}: could not be evaluated (p103)."
    )
    return_visit_same_injury: Finding = _finding(
        f"Returned for reassessment of the same injury ({STIELL} exclusion, p1392)."
    )
    pregnant: Finding = _finding(f"Pregnant ({STIELL} exclusion, p1392).")
    gcs_2h_post_injury: int | None = _number(
        f"GCS 2 h after injury; leave empty until 2 h have passed ({STIELL}, Panel 1)."
    )
    suspected_open_or_depressed_fracture: Finding = _finding(
        f"Suspected open or depressed skull fracture ({STIELL}, Panel 1)."
    )
    haemotympanum: Finding = _finding(
        f"Haemotympanum, a sign of basal skull fracture ({STIELL}, Panel 1)."
    )
    raccoon_eyes: Finding = _finding(
        f"'Raccoon' eyes, a sign of basal skull fracture ({STIELL}, Panel 1)."
    )
    csf_otorrhoea_or_rhinorrhoea: Finding = _finding(
        f"CSF otorrhoea or rhinorrhoea, a sign of basal skull fracture "
        f"({STIELL}, Panel 1)."
    )
    battle_sign: Finding = _finding(
        f"Battle's sign, a sign of basal skull fracture ({STIELL}, Panel 1)."
    )
    vomiting_episodes: int | None = _number(
        f"Episodes of vomiting after the injury. {STIELL}: 2+ is high risk. "
        f"{HAYDEL}: any is a finding (p101)."
    )
    retrograde_amnesia_minutes: float | None = _number(
        f"Minutes of amnesia for events BEFORE impact; over 30 is medium risk "
        f"({STIELL}, Panel 1)."
    )
    pedestrian_struck_by_motor_vehicle: Finding = _finding(
        f"Pedestrian struck by a motor vehicle ({STIELL}, Panel 1)."
    )
    ejected_from_motor_vehicle: Finding = _finding(
        f"Occupant ejected from a motor vehicle ({STIELL}, Panel 1)."
    )
    fall_from_height_gt_3ft_or_5_stairs: Finding = _finding(
        f"Fall from over 3 feet or 5 stairs ({STIELL}, Panel 1)."
    )

    # --- New Orleans Criteria only (Haydel 2000, p101) ---
    patient_reported_loc: Finding = _finding(
        f"The patient reports losing consciousness ({HAYDEL}, p101)."
    )
    amnesia_for_event: Finding = _finding(
        f"The patient cannot remember the traumatic event; counts as loss of "
        f"consciousness ({HAYDEL}, p101)."
    )
    abnormal_brief_neuro_exam: Finding = _finding(
        f"Abnormal cranial nerves, or abnormal strength or sensation in arms or "
        f"legs ({HAYDEL}, p101)."
    )
    headache: Finding = _finding(f"Any head pain, diffuse or local ({HAYDEL}, p101).")
    drug_or_alcohol_intoxication: Finding = _finding(
        f"Intoxication from history plus exam findings such as slurred speech or "
        f"alcohol on the breath ({HAYDEL}, p101)."
    )
    short_term_memory_deficit: Finding = _finding(
        f"Persistent anterograde amnesia (cannot form new memories) with an "
        f"otherwise normal GCS ({HAYDEL}, p101)."
    )
    trauma_above_clavicles: Finding = _finding(
        f"Any external injury above the clavicles: contusion, abrasion, "
        f"laceration, deformity, or signs of facial or skull fracture "
        f"({HAYDEL}, p101)."
    )
    post_traumatic_seizure: Finding = _finding(
        f"Suspected or witnessed seizure after the injury ({HAYDEL}, p101)."
    )

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
