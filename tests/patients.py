"""Test patient builders shared by all rules."""

from ct_head_rules.findings import Finding
from ct_head_rules.patient import Patient

PRESENT = Finding.PRESENT
ABSENT = Finding.ABSENT
UNKNOWN = Finding.UNKNOWN


def negative_patient(**overrides) -> Patient:
    """Eligible for both rules, every input known, no criterion of either met.

    Override any field to build a specific scenario.
    """
    fields = dict(
        # shared
        age_years=30,
        witnessed_loc=PRESENT,
        initial_ed_gcs=15,
        hours_since_injury=3.0,
        vomiting_episodes=0,
        bleeding_disorder=ABSENT,
        oral_anticoagulant=ABSENT,
        # Canadian CT Head Rule
        blunt_head_trauma=PRESENT,
        definite_amnesia=ABSENT,
        witnessed_disorientation=ABSENT,
        obvious_penetrating_injury_or_depressed_fracture=ABSENT,
        acute_focal_neuro_deficit=ABSENT,
        unstable_vitals_major_trauma=ABSENT,
        seizure_before_ed_assessment=ABSENT,
        return_visit_same_injury=ABSENT,
        pregnant=ABSENT,
        gcs_2h_post_injury=15,
        suspected_open_or_depressed_fracture=ABSENT,
        haemotympanum=ABSENT,
        raccoon_eyes=ABSENT,
        csf_otorrhoea_or_rhinorrhoea=ABSENT,
        battle_sign=ABSENT,
        retrograde_amnesia_minutes=0,
        pedestrian_struck_by_motor_vehicle=ABSENT,
        ejected_from_motor_vehicle=ABSENT,
        fall_from_height_gt_3ft_or_5_stairs=ABSENT,
        # New Orleans Criteria
        patient_reported_loc=ABSENT,
        amnesia_for_event=ABSENT,
        abnormal_brief_neuro_exam=ABSENT,
        headache=ABSENT,
        drug_or_alcohol_intoxication=ABSENT,
        short_term_memory_deficit=ABSENT,
        trauma_above_clavicles=ABSENT,
        post_traumatic_seizure=ABSENT,
    )
    fields.update(overrides)
    return Patient(**fields)
