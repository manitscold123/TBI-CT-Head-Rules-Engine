"""The question tree: broad questions first, details only when they matter.

A broad question may only settle its details if "No" to it means "No" to
every detail, under every paper's definition. Each gate's wording must
therefore name everything it rules out; the table below says where.
"""

import dataclasses

import pytest

from ct_head_rules.api import FIELDS, InputError
from ct_head_rules.findings import Finding
from ct_head_rules.patient import Patient
from ct_head_rules.questions import (
    GATES,
    PARENT,
    ROOTS,
    ancestors,
    answer_gate,
    descendant_fields,
    gate_state,
    next_prompt,
)

# For every child of every gate: a phrase in the gate's question that covers
# the child's definition. Hand-checked against the papers:
COVERAGE = {
    # Stiell p1391: "witnessed loss of consciousness, definite amnesia, or
    # witnessed disorientation"; Haydel p101: LOC or amnesia for the event.
    "gate.loc_amnesia_disorientation": {
        "history_of_loc": "loss of consciousness",
        "gate.amnesia": "amnesia",
        "witnessed_disorientation": "disorientation",
    },
    # Kuppermann p1162: "a period of unconsciousness"; field help: known or
    # suspected (p1167). Stiell p1391 witnessed; Haydel p101 patient-reported.
    "history_of_loc": {
        "witnessed_loc": "seen by a witness",
        "patient_reported_loc": "reported by the patient",
        "loc_duration_seconds": "however brief",
    },
    # Stiell p1391 "definite amnesia" (type not defined) and Panel 1 "amnesia
    # before impact"; Haydel p101 amnesia for the event, and short-term memory
    # deficit = "persistent anterograde amnesia".
    "gate.amnesia": {
        "definite_amnesia": "any amnesia",
        "amnesia_for_event": "the event itself",
        "retrograde_amnesia_minutes": "before it",
        "short_term_memory_deficit": "forming new memories",
    },
    # Haydel p101: "any external evidence of injury, including contusions,
    # abrasions, lacerations, deformities, and signs of facial or skull
    # fracture". Kuppermann p1161: scalp haematoma is "swelling of the scalp";
    # palpable skull fracture, or "unclear on the basis of swelling".
    "trauma_above_clavicles": {
        "non_frontal_scalp_haematoma": "swelling",
        "palpable_or_unclear_skull_fracture": "skull fracture",
        "obvious_penetrating_injury_or_depressed_fracture": "penetrating",
        "suspected_open_or_depressed_fracture": "open or depressed",
        "gate.basal_skull_fracture": "basal skull fracture",
    },
    # Stiell Panel 1 (p1394); Kuppermann p1161.
    "gate.basal_skull_fracture": {
        "haemotympanum": "eardrum",
        "raccoon_eyes": "raccoon eyes",
        "csf_otorrhoea_or_rhinorrhoea": "CSF",
        "battle_sign": "Battle's sign",
    },
    # Stiell Panel 1: "fall from height >3 feet or five stairs"; Kuppermann
    # p1163: falls over 0.9 m / 1.5 m.
    "gate.fall": {
        "fall_height_m": "any height",
        "fall_from_height_gt_3ft_or_5_stairs": "stairs",
    },
    # Kuppermann p1163 includes ejection and a pedestrian struck; Stiell Panel
    # 1's "occupant ejected" and "pedestrian struck" are narrower.
    "severe_non_fall_mechanism": {
        "ejected_from_motor_vehicle": "ejected",
        "pedestrian_struck_by_motor_vehicle": "pedestrian",
    },
    # Haydel p101: "any head pain"; Kuppermann p1161: severe headache.
    "headache": {"severe_headache": "any headache"},
    # Kuppermann p1161-63: "agitation, somnolence, repetitive questioning, or
    # slow response to verbal communication"; parent: "at baseline or not".
    "gate.behaviour": {
        "other_altered_mental_status": "agitation",
        "not_acting_normally_per_parent": "not acting normally",
    },
}


# --- Shape of the tree -----------------------------------------------------------


def test_every_gate_is_hand_checked():
    assert set(COVERAGE) == set(GATES)
    for gate_id, children in COVERAGE.items():
        assert set(children) == set(GATES[gate_id].children), gate_id


@pytest.mark.parametrize("gate_id", sorted(COVERAGE))
def test_gate_wording_names_everything_no_rules_out(gate_id):
    text = GATES[gate_id].text.lower()
    for child, phrase in COVERAGE[gate_id].items():
        assert phrase.lower() in text, f"{gate_id} does not cover {child}"


def test_every_gate_cites_its_sources():
    for gate in GATES.values():
        assert any(p in gate.source for p in ("Stiell", "Haydel", "Kuppermann"))


def test_every_field_appears_exactly_once():
    seen = [*ROOTS]
    for gate in GATES.values():
        seen += gate.children
    fields = [name for name in seen if name in FIELDS]
    assert sorted(fields) == sorted(FIELDS)
    assert len(seen) == len(set(seen))


def test_gates_that_are_fields_are_patient_findings():
    for gate_id in GATES:
        if gate_id in FIELDS:
            assert FIELDS[gate_id].type is Finding


def test_seizures_are_not_grouped():
    # Stiell p1392 excludes a seizure "before assessment", which may precede
    # the injury; Haydel p101 counts only seizures "after the traumatic event".
    # Neither covers the other, so neither can settle the other.
    assert "seizure_before_ed_assessment" in ROOTS
    assert "post_traumatic_seizure" in ROOTS


def test_ancestors_run_from_the_top():
    assert ancestors("haemotympanum") == (
        "trauma_above_clavicles",
        "gate.basal_skull_fracture",
    )
    assert ancestors("age_years") == ()
    assert PARENT["witnessed_loc"] == "history_of_loc"


def test_descendant_fields_include_nested_gates_that_are_fields():
    fields = descendant_fields("gate.loc_amnesia_disorientation")
    assert "history_of_loc" in fields
    assert "witnessed_loc" in fields
    assert "short_term_memory_deficit" in fields
    assert "gate.amnesia" not in fields


# --- Answering a gate --------------------------------------------------------------


def test_no_settles_every_detail_including_numbers():
    values = answer_gate({}, "gate.loc_amnesia_disorientation", Finding.ABSENT)

    assert values["history_of_loc"] == "absent"
    assert values["witnessed_loc"] == "absent"
    assert values["witnessed_disorientation"] == "absent"
    assert values["loc_duration_seconds"] == 0
    assert values["retrograde_amnesia_minutes"] == 0
    assert "gate.amnesia" not in values  # only Patient fields are stored


def test_no_on_a_field_gate_also_answers_the_field():
    values = answer_gate({}, "trauma_above_clavicles", Finding.ABSENT)
    assert values["trauma_above_clavicles"] == "absent"
    assert values["battle_sign"] == "absent"


def test_yes_answers_only_the_gate_field():
    assert answer_gate({}, "headache", Finding.PRESENT) == {"headache": "present"}
    assert answer_gate({}, "gate.fall", Finding.PRESENT) == {}


def test_unknown_changes_nothing_below():
    values = answer_gate(
        {"battle_sign": "absent"}, "trauma_above_clavicles", Finding.UNKNOWN
    )
    assert values == {"battle_sign": "absent", "trauma_above_clavicles": "unknown"}


@pytest.mark.parametrize(
    ("known", "gate_id"),
    [
        ({"battle_sign": "present"}, "trauma_above_clavicles"),
        ({"fall_height_m": 1.2}, "gate.fall"),
        ({"history_of_loc": "present"}, "gate.loc_amnesia_disorientation"),
    ],
)
def test_no_that_contradicts_a_known_detail_is_refused(known, gate_id):
    field = next(iter(known))
    with pytest.raises(InputError, match=field):
        answer_gate(known, gate_id, Finding.ABSENT)


def test_answers_from_gates_make_a_valid_patient():
    values = {}
    for gate_id in GATES:
        values = answer_gate(values, gate_id, Finding.ABSENT)
    patient = Patient(
        **{k: (Finding(v) if isinstance(v, str) else v) for k, v in values.items()}
    )
    assert dataclasses.asdict(patient)


# --- Gate state read from the answers ----------------------------------------------


@pytest.mark.parametrize(
    ("values", "state"),
    [
        ({}, None),
        ({"haemotympanum": "present"}, "yes"),
        ({"fall_height_m": 0.5}, None),  # not under this gate
        ({"trauma_above_clavicles": "present"}, "yes"),
        ({"trauma_above_clavicles": "absent"}, None),  # details still unknown
    ],
)
def test_gate_state_of_injury_above_clavicles(values, state):
    assert gate_state("trauma_above_clavicles", values) == state


def test_gate_state_is_no_once_every_detail_is_absent():
    values = answer_gate({}, "gate.fall", Finding.ABSENT)
    assert gate_state("gate.fall", values) == "no"
    assert gate_state("gate.fall", {"fall_height_m": 2}) == "yes"


# --- Which prompt comes before a field ---------------------------------------------


def test_topmost_open_gate_is_asked_before_a_detail():
    assert (
        next_prompt("haemotympanum", asked=set(), values={}) == "trauma_above_clavicles"
    )
    asked = {"trauma_above_clavicles"}
    assert next_prompt("haemotympanum", asked, {}) == "gate.basal_skull_fracture"
    asked.add("gate.basal_skull_fracture")
    assert next_prompt("haemotympanum", asked, {}) == "haemotympanum"


def test_gate_is_skipped_when_a_detail_already_says_yes():
    values = {"raccoon_eyes": "present"}
    assert next_prompt("haemotympanum", set(), values) == "haemotympanum"


def test_root_fields_are_asked_directly():
    assert next_prompt("age_years", set(), {}) == "age_years"


def test_gate_already_answered_as_a_field_is_not_asked_again():
    values = {"trauma_above_clavicles": "absent"}
    assert next_prompt("haemotympanum", set(), values) == "gate.basal_skull_fracture"


def test_gate_is_skipped_when_it_could_settle_only_one_needed_detail():
    # Asking a broad question costs a question; it only pays off when "No"
    # can settle two or more details still needed.
    needed = {"haemotympanum"}
    assert next_prompt("haemotympanum", set(), {}, needed) == "haemotympanum"
    needed = {"haemotympanum", "battle_sign"}
    assert next_prompt("haemotympanum", set(), {}, needed) == ("trauma_above_clavicles")
    asked = {"trauma_above_clavicles"}
    assert next_prompt("haemotympanum", asked, {}, needed) == (
        "gate.basal_skull_fracture"
    )


def test_gate_that_is_itself_needed_is_always_asked():
    needed = {"trauma_above_clavicles", "haemotympanum"}
    assert next_prompt("haemotympanum", set(), {}, needed) == "trauma_above_clavicles"
