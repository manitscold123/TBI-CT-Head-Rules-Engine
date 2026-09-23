"""New Orleans Criteria. Educational implementation, not for clinical use.

Source: Haydel MJ, Preston CA, Mills TJ, et al. Indications for computed
tomography in patients with minor head injury. N Engl J Med 2000;343:100-05.
(sources/NEJM200007133430204.pdf). The paper calls them "seven findings"; the
name "New Orleans Criteria" is not used in it.

Unlike the Canadian CT Head Rule, the criteria apply only to patients with a
GCS of 15, and have a single tier: any one finding means CT.

Two study exclusions are deliberately not implemented: patients who "declined
CT" or "had concurrent injuries that precluded the use of CT" (p101). They
describe whether the study could scan the patient, not who the criteria fit.
"""

from ct_head_rules.findings import Finding
from ct_head_rules.patient import Patient
from ct_head_rules.rules import (
    CriterionStatus,
    Outcome,
    RuleResult,
    _any_of,
    _compare,
    _Criterion,
    _from_finding,
    _in_field_order,
    _present_implies,
    decide,
    rule_inputs,
    with_notes,
)

# Journal pages 100-105 are PDF pages 1-6.
_PAPER = "Haydel 2000, N Engl J Med 343:100-05"
SOURCE_METHODS_P100 = f"{_PAPER}, Methods: Phase 1 (p100)"
SOURCE_METHODS_P101 = f"{_PAPER}, Methods: Phase 1 (p101)"
# Each finding is defined in Methods (p101); Results (p101) names the seven.
SOURCE_FINDINGS = f"{_PAPER}, Methods and Results (p101)"


# --- Inclusion criteria -----------------------------------------------------


def _met_if_absent(value: Finding) -> CriterionStatus:
    """For inclusions that require something to be absent."""
    return {
        CriterionStatus.MET: CriterionStatus.NOT_MET,
        CriterionStatus.NOT_MET: CriterionStatus.MET,
        CriterionStatus.UNKNOWN: CriterionStatus.UNKNOWN,
    }[_from_finding(value)]


INCLUSION_CRITERIA = (
    # p101: minor head injury is loss of consciousness with "a score of 15 on
    # the Glasgow Coma Scale, as determined by a physician on the patient's
    # arrival at the emergency department". The key difference from the
    # Canadian rule, which accepts 13-15.
    _Criterion(
        "noc.inclusion.gcs_15",
        "GCS 15 on arrival in the ED",
        "inclusion",
        SOURCE_METHODS_P101,
        ("initial_ed_gcs",),
        lambda p: _compare(p.initial_ed_gcs, lambda gcs: gcs == 15),
    ),
    # p101: loss of consciousness counts "if a witness or the patient reported
    # loss of consciousness by the patient or if the patient could not
    # remember the traumatic event". Patients with neither LOC nor amnesia for
    # the event were excluded.
    _Criterion(
        "noc.inclusion.loc_or_amnesia_for_event",
        "Loss of consciousness (witnessed or reported) or amnesia for the event",
        "inclusion",
        SOURCE_METHODS_P101,
        ("witnessed_loc", "patient_reported_loc", "amnesia_for_event"),
        lambda p: _any_of(p.witnessed_loc, p.patient_reported_loc, p.amnesia_for_event),
    ),
    # p101: "normal findings on a brief neurologic examination (normal cranial
    # nerves and normal strength and sensation in the arms and legs)".
    _Criterion(
        "noc.inclusion.normal_brief_neuro_exam",
        "Normal brief neurologic examination",
        "inclusion",
        SOURCE_METHODS_P101,
        ("abnormal_brief_neuro_exam",),
        lambda p: _met_if_absent(p.abnormal_brief_neuro_exam),
    ),
    # p100: patients "who were at least three years old".
    _Criterion(
        "noc.inclusion.age_3_or_over",
        "Age 3 or over",
        "inclusion",
        SOURCE_METHODS_P100,
        ("age_years",),
        lambda p: _compare(p.age_years, lambda age: age >= 3),
    ),
    # p100: patients "who presented within 24 hours after the injury".
    _Criterion(
        "noc.inclusion.injury_within_24h",
        "Injury within the past 24 h",
        "inclusion",
        SOURCE_METHODS_P100,
        ("hours_since_injury",),
        lambda p: _compare(p.hours_since_injury, lambda hours: hours <= 24),
    ),
)


# --- The seven findings (p101) ----------------------------------------------

FINDINGS = (
    # p101: "Headache was defined as any head pain, whether diffuse or local."
    # A severe headache recorded for PECARN is head pain, so it meets this
    # finding too; its absence never implies no headache.
    _Criterion(
        "noc.finding.headache",
        "Headache",
        "risk_factor",
        SOURCE_FINDINGS,
        ("headache",),
        lambda p: _present_implies(p.headache, p.severe_headache),
        also_reads=("severe_headache",),
    ),
    # p101: "Vomiting was defined as any emesis after the traumatic event."
    _Criterion(
        "noc.finding.vomiting",
        "Vomiting",
        "risk_factor",
        SOURCE_FINDINGS,
        ("vomiting_episodes",),
        lambda p: _compare(p.vomiting_episodes, lambda n: n >= 1),
    ),
    # p101: "an age over 60 years".
    _Criterion(
        "noc.finding.age_over_60",
        "Age over 60",
        "risk_factor",
        SOURCE_FINDINGS,
        ("age_years",),
        lambda p: _compare(p.age_years, lambda age: age > 60),
    ),
    # p101: intoxication "determined on the basis of the history ... and
    # suggestive findings on physical examination".
    _Criterion(
        "noc.finding.drug_or_alcohol_intoxication",
        "Drug or alcohol intoxication",
        "risk_factor",
        SOURCE_FINDINGS,
        ("drug_or_alcohol_intoxication",),
        lambda p: _from_finding(p.drug_or_alcohol_intoxication),
    ),
    # p101: "persistent anterograde amnesia in a patient with an otherwise
    # normal score on the Glasgow Coma Scale".
    _Criterion(
        "noc.finding.short_term_memory_deficit",
        "Deficit in short-term memory",
        "risk_factor",
        SOURCE_FINDINGS,
        ("short_term_memory_deficit",),
        lambda p: _from_finding(p.short_term_memory_deficit),
    ),
    # p101: "any external evidence of injury, including ... signs of facial or
    # skull fracture". Stiell 2001 Panel 1 (p1394) identifies haemotympanum,
    # raccoon eyes, CSF otorrhoea/rhinorrhoea and Battle's sign as signs of
    # basal skull fracture, so a Canadian skull fracture sign that is PRESENT
    # meets this finding. An ABSENT one never implies no trauma here.
    _Criterion(
        "noc.finding.trauma_above_clavicles",
        "Physical evidence of trauma above the clavicles",
        "risk_factor",
        f"{SOURCE_FINDINGS}; Stiell 2001, Lancet 357:1391-96, Panel 1 (p1394)",
        ("trauma_above_clavicles",),
        lambda p: _present_implies(
            p.trauma_above_clavicles,
            p.suspected_open_or_depressed_fracture,
            p.obvious_penetrating_injury_or_depressed_fracture,
            p.haemotympanum,
            p.raccoon_eyes,
            p.csf_otorrhoea_or_rhinorrhoea,
            p.battle_sign,
        ),
        also_reads=(
            "suspected_open_or_depressed_fracture",
            "obvious_penetrating_injury_or_depressed_fracture",
            "haemotympanum",
            "raccoon_eyes",
            "csf_otorrhoea_or_rhinorrhoea",
            "battle_sign",
        ),
    ),
    # p101: "Seizure was defined as a suspected or witnessed seizure after the
    # traumatic event."
    _Criterion(
        "noc.finding.seizure",
        "Seizure",
        "risk_factor",
        SOURCE_FINDINGS,
        ("post_traumatic_seizure",),
        lambda p: _from_finding(p.post_traumatic_seizure),
    ),
)

# Coagulopathy is read only for a note (p103), never as a criterion.
NOC_INPUTS = _in_field_order(
    (
        *rule_inputs(*INCLUSION_CRITERIA, *FINDINGS),
        "bleeding_disorder",
        "oral_anticoagulant",
    )
)


# --- Evaluation -------------------------------------------------------------

NOTE_NOT_APPLICABLE = (
    "The New Orleans Criteria were not derived for this patient and give no "
    "guidance on CT. This is not a 'CT not required' result."
)
NOTE_GCS_15_ONLY = (
    "The New Orleans Criteria apply only to patients with GCS 15 (Haydel 2000, p101)."
)
NOTE_CANADIAN_COVERS_13_14 = " The Canadian CT Head Rule covers GCS 13-15."
# p101: "Patients with isolated deficits in short-term memory and an otherwise
# normal score on the Glasgow Coma Scale were considered to have a normal
# score"; repeated in the Discussion (p103).
NOTE_RESCORE_GCS = (
    "Haydel 2000 scored patients whose only abnormality was a short-term memory "
    "deficit as GCS 15 (pp101, 103). If that is why GCS is 14, re-score as 15."
)
# p103: "Since patients with coagulopathy were underrepresented in our study,
# we could not evaluate this criterion." Table 1 (p102): 1 patient.
NOTE_COAGULOPATHY = (
    "Bleeding disorder or anticoagulant use: Haydel 2000 could not evaluate "
    "coagulopathy (1 patient in the study, p103), so the criteria are "
    "untested for this patient."
)


def evaluate_noc(patient: Patient) -> RuleResult:
    """Apply the New Orleans Criteria to one patient."""
    result = decide(
        "noc",
        patient,
        INCLUSION_CRITERIA,
        (),
        ((None, Outcome.CT_RECOMMENDED, FINDINGS),),
    )

    notes = []
    if result.outcome is Outcome.NOT_APPLICABLE:
        notes.append(NOTE_NOT_APPLICABLE)
    gcs = patient.initial_ed_gcs
    if gcs is not None and gcs != 15:
        canadian = NOTE_CANADIAN_COVERS_13_14 if 13 <= gcs <= 14 else ""
        notes.append(NOTE_GCS_15_ONLY + canadian)
        if gcs == 14 and patient.short_term_memory_deficit is Finding.PRESENT:
            notes.append(NOTE_RESCORE_GCS)
    if Finding.PRESENT in (patient.bleeding_disorder, patient.oral_anticoagulant):
        notes.append(NOTE_COAGULOPATHY)
    return with_notes(result, *notes)
