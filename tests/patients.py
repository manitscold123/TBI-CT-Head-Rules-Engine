"""Test patient builders for the Canadian CT Head Rule."""

from ct_head_rules.cchr import CCHRInput
from ct_head_rules.findings import Finding

PRESENT = Finding.PRESENT
ABSENT = Finding.ABSENT
UNKNOWN = Finding.UNKNOWN


def negative_patient(**overrides) -> CCHRInput:
    """An eligible adult with minor head injury, every input known, no criterion met.

    Override any field to build a specific scenario.
    """
    fields = dict(
        # applicability
        age_years=30,
        blunt_head_trauma=PRESENT,
        witnessed_loc=PRESENT,
        definite_amnesia=ABSENT,
        witnessed_disorientation=ABSENT,
        initial_ed_gcs=15,
        hours_since_injury=3.0,
        obvious_penetrating_injury_or_depressed_fracture=ABSENT,
        acute_focal_neuro_deficit=ABSENT,
        unstable_vitals_major_trauma=ABSENT,
        seizure_before_ed_assessment=ABSENT,
        bleeding_disorder=ABSENT,
        oral_anticoagulant=ABSENT,
        return_visit_same_injury=ABSENT,
        pregnant=ABSENT,
        # high risk
        gcs_2h_post_injury=15,
        suspected_open_or_depressed_fracture=ABSENT,
        haemotympanum=ABSENT,
        raccoon_eyes=ABSENT,
        csf_otorrhoea_or_rhinorrhoea=ABSENT,
        battle_sign=ABSENT,
        vomiting_episodes=0,
        # medium risk
        retrograde_amnesia_minutes=0,
        pedestrian_struck_by_motor_vehicle=ABSENT,
        ejected_from_motor_vehicle=ABSENT,
        fall_from_height_gt_3ft_or_5_stairs=ABSENT,
    )
    fields.update(overrides)
    return CCHRInput(**fields)
