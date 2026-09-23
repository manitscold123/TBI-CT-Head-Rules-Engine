"""Every numeric threshold in the three papers, checked on both sides.

Each row changes one input of an otherwise negative patient. Sources are the
ones cited on the criteria in cchr.py, noc.py and pecarn.py.
"""

import pytest
from patients import negative_child, negative_patient

from ct_head_rules.cchr import evaluate_cchr
from ct_head_rules.noc import evaluate_noc
from ct_head_rules.pecarn import evaluate_pecarn
from ct_head_rules.rules import Outcome

CT = Outcome.CT_RECOMMENDED
OBS = Outcome.OBSERVATION_OR_CT
NO_CT = Outcome.CT_NOT_REQUIRED
NA = Outcome.NOT_APPLICABLE

ADULT = negative_patient


def CHILD_5(**overrides):
    return negative_child(overrides.pop("age_years", 5), **overrides)


def CHILD_1(**overrides):
    return negative_child(overrides.pop("age_years", 1), **overrides)


ROWS = [
    # Canadian CT Head Rule (Stiell 2001)
    ("cchr", ADULT, "age_years", 15, NA),  # Methods p1392: "less than 16"
    ("cchr", ADULT, "age_years", 16, NO_CT),
    ("cchr", ADULT, "age_years", 64, NO_CT),  # Panel 1 p1394: "Age >=65"
    ("cchr", ADULT, "age_years", 65, CT),
    ("cchr", ADULT, "initial_ed_gcs", 12, NA),  # Methods p1392: GCS 13 or more
    ("cchr", ADULT, "initial_ed_gcs", 13, NO_CT),
    ("cchr", ADULT, "gcs_2h_post_injury", 14, CT),  # Panel 1: "GCS <15 at 2 h"
    ("cchr", ADULT, "gcs_2h_post_injury", 15, NO_CT),
    ("cchr", ADULT, "vomiting_episodes", 1, NO_CT),  # Panel 1: ">=2 episodes"
    ("cchr", ADULT, "vomiting_episodes", 2, CT),
    ("cchr", ADULT, "retrograde_amnesia_minutes", 30, NO_CT),  # Panel 1: ">30 min"
    ("cchr", ADULT, "retrograde_amnesia_minutes", 31, CT),
    ("cchr", ADULT, "hours_since_injury", 24, NO_CT),  # Methods p1392: 24 h
    ("cchr", ADULT, "hours_since_injury", 24.1, NA),
    # New Orleans Criteria (Haydel 2000)
    ("noc", ADULT, "age_years", 2, NA),  # Methods p100: aged 3 or older
    ("noc", ADULT, "age_years", 3, NO_CT),
    ("noc", ADULT, "age_years", 60, NO_CT),  # Results p101: "older than 60"
    ("noc", ADULT, "age_years", 61, CT),
    ("noc", ADULT, "initial_ed_gcs", 14, NA),  # Methods p101: GCS 15
    ("noc", ADULT, "initial_ed_gcs", 15, NO_CT),
    ("noc", ADULT, "vomiting_episodes", 0, NO_CT),  # Results p101: any vomiting
    ("noc", ADULT, "vomiting_episodes", 1, CT),
    ("noc", ADULT, "hours_since_injury", 24, NO_CT),  # Methods p100: 24 h
    ("noc", ADULT, "hours_since_injury", 24.1, NA),
    # PECARN (Kuppermann 2009)
    ("pecarn", CHILD_5, "age_years", 17, NO_CT),  # Methods p1161: under 18
    ("pecarn", CHILD_5, "age_years", 18, NA),
    ("pecarn", CHILD_5, "initial_ed_gcs", 13, NA),  # p1162: GCS 14-15
    ("pecarn", CHILD_5, "initial_ed_gcs", 14, CT),  # GCS <15 is altered status
    ("pecarn", CHILD_5, "hours_since_injury", 24, NO_CT),  # p1162: within 24 h
    ("pecarn", CHILD_5, "hours_since_injury", 24.1, NA),
    ("pecarn", CHILD_5, "vomiting_episodes", 1, OBS),  # Figure 3: any vomiting
    ("pecarn", CHILD_5, "fall_height_m", 1.5, NO_CT),  # p1163: "more than 1.5 m"
    ("pecarn", CHILD_5, "fall_height_m", 1.51, OBS),
    ("pecarn", CHILD_1, "fall_height_m", 0.9, NO_CT),  # p1163: "more than 0.9 m"
    ("pecarn", CHILD_1, "fall_height_m", 0.91, OBS),
    ("pecarn", CHILD_1, "loc_duration_seconds", 4.9, NO_CT),  # Figure 3: >=5 s
    ("pecarn", CHILD_1, "loc_duration_seconds", 5, OBS),
    ("pecarn", CHILD_1, "initial_ed_gcs", 14, CT),
]

EVALUATE = {"cchr": evaluate_cchr, "noc": evaluate_noc, "pecarn": evaluate_pecarn}


@pytest.mark.parametrize(
    ("rule", "patient", "field", "value", "outcome"),
    ROWS,
    ids=[f"{r}-{f}={v}" for r, p, f, v, o in ROWS],
)
def test_threshold(rule, patient, field, value, outcome):
    result = EVALUATE[rule](patient(**{field: value}))
    assert result.outcome is outcome


def test_age_2_uses_the_older_childrens_predictors():
    # Figure 3 (p1168): separate rules for "younger than 2 years" and "2 years
    # and older"; a 2-year-old's vomiting counts, an infant's does not.
    assert evaluate_pecarn(negative_child(2, vomiting_episodes=1)).outcome is OBS
    assert evaluate_pecarn(negative_child(1, vomiting_episodes=1)).outcome is NO_CT
