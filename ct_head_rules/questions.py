"""The question tree: broad questions first, details only when they matter.

Educational use only, not for clinical use.

A gate is a broad question. "No" to it answers every detail below it as
absent (or 0), so it may only group details that "No" really rules out under
every paper's definition; its wording names them all. "Yes" or "Unknown"
leaves the details to be asked. The rules themselves are unchanged: gates only
decide which Patient fields are asked, and fill some in.

Some gates are Patient fields themselves (e.g. trauma_above_clavicles); the
rest ("gate.*") exist only as questions.

Seizures are deliberately not grouped: Stiell 2001 (p1392) excludes a seizure
"before assessment", which may precede the injury, while Haydel 2000 (p101)
counts only seizures "after the traumatic event".
"""

from dataclasses import dataclass

from ct_head_rules.api import FIELDS, InputError
from ct_head_rules.findings import Finding


@dataclass(frozen=True)
class Gate:
    id: str
    text: str
    children: tuple[str, ...]
    source: str  # why "No" rules out every child
    label: str = ""  # a short name for forms; fields use their own name


GATES = {
    gate.id: gate
    for gate in (
        Gate(
            "gate.loc_amnesia_disorientation",
            "Any loss of consciousness, any amnesia, or any disorientation "
            "after the injury?",
            ("history_of_loc", "gate.amnesia", "witnessed_disorientation"),
            "Stiell 2001, Methods (p1391); Haydel 2000, Methods (p101); "
            "Kuppermann 2009, Panel 1 (p1161)",
            label="LOC, amnesia or disorientation",
        ),
        Gate(
            "history_of_loc",
            "Any loss of consciousness, known or suspected, however brief "
            "(seen by a witness or reported by the patient)?",
            ("witnessed_loc", "patient_reported_loc", "loc_duration_seconds"),
            "Kuppermann 2009, Panel 1 (p1161) and p1167; Stiell 2001 (p1391); "
            "Haydel 2000 (p101)",
        ),
        Gate(
            "gate.amnesia",
            "Any amnesia: for the event itself, for events before it, or "
            "ongoing trouble forming new memories?",
            (
                "definite_amnesia",
                "amnesia_for_event",
                "retrograde_amnesia_minutes",
                "short_term_memory_deficit",
            ),
            "Stiell 2001, Methods (p1391) and Panel 1 (p1394); Haydel 2000 (p101)",
            label="Amnesia",
        ),
        Gate(
            "trauma_above_clavicles",
            "Any injury above the collarbones: bruising, swelling, graze, cut or "
            "deformity; a penetrating injury; an open or depressed skull "
            "fracture; any palpable (or unclear) skull fracture; or any sign "
            "of facial or basal skull fracture?",
            (
                "non_frontal_scalp_haematoma",
                "palpable_or_unclear_skull_fracture",
                "obvious_penetrating_injury_or_depressed_fracture",
                "suspected_open_or_depressed_fracture",
                "gate.basal_skull_fracture",
            ),
            "Haydel 2000, Methods (p101); Kuppermann 2009, Panel 1 (p1161); "
            "Stiell 2001 (p1392) and Panel 1 (p1394)",
        ),
        Gate(
            "gate.basal_skull_fracture",
            "Any sign of basal skull fracture: blood behind the eardrum, "
            "raccoon eyes, CSF leaking from the ear or nose, or Battle's sign?",
            (
                "haemotympanum",
                "raccoon_eyes",
                "csf_otorrhoea_or_rhinorrhoea",
                "battle_sign",
            ),
            "Stiell 2001, Panel 1 (p1394); Kuppermann 2009, Panel 1 (p1161)",
            label="Signs of basal skull fracture",
        ),
        Gate(
            "gate.fall",
            "Did the injury involve a fall from any height, including down stairs?",
            ("fall_height_m", "fall_from_height_gt_3ft_or_5_stairs"),
            "Stiell 2001, Panel 1 (p1394); Kuppermann 2009 (p1163)",
            label="Fall",
        ),
        Gate(
            "severe_non_fall_mechanism",
            "Apart from a fall: a vehicle crash where someone was ejected, it "
            "rolled over or a passenger died; a pedestrian, or a cyclist without "
            "a helmet, struck by a motor vehicle; or the head struck by a "
            "high-impact object?",
            ("ejected_from_motor_vehicle", "pedestrian_struck_by_motor_vehicle"),
            "Kuppermann 2009 (p1163); Stiell 2001, Panel 1 (p1394)",
        ),
        Gate(
            "headache",
            "Any headache, mild or severe?",
            ("severe_headache",),
            "Haydel 2000 (p101); Kuppermann 2009, Panel 1 (p1161)",
        ),
        Gate(
            "gate.behaviour",
            "Any change in behaviour or alertness: agitation, sleepiness, "
            "repetitive questioning, slow response to speech, or a parent "
            "saying the child is not acting normally?",
            ("other_altered_mental_status", "not_acting_normally_per_parent"),
            "Kuppermann 2009, Panel 1 (p1161) and p1163",
            label="Behaviour or alertness change",
        ),
    )
}

PARENT = {child: gate.id for gate in GATES.values() for child in gate.children}

# Top-level questions in the order a form shows them: what decides which rules
# apply, then history, examination, mechanism, symptoms and background.
ROOTS = (
    "age_years",
    "initial_ed_gcs",
    "hours_since_injury",
    "blunt_head_trauma",
    "gate.loc_amnesia_disorientation",
    "gate.behaviour",
    "drug_or_alcohol_intoxication",
    "trauma_above_clavicles",
    "gate.fall",
    "severe_non_fall_mechanism",
    "trivial_mechanism_no_symptoms",
    "vomiting_episodes",
    "headache",
    "post_traumatic_seizure",
    "seizure_before_ed_assessment",
    "abnormal_brief_neuro_exam",
    "acute_focal_neuro_deficit",
    "gcs_2h_post_injury",
    "unstable_vitals_major_trauma",
    "penetrating_trauma",
    "bleeding_disorder",
    "oral_anticoagulant",
    "pregnant",
    "return_visit_same_injury",
    "brain_tumour",
    "neuro_disorder_complicating_assessment",
    "ventricular_shunt",
)


def ancestors(name: str) -> tuple[str, ...]:
    """The gates above a field or gate, topmost first."""
    chain = []
    while name in PARENT:
        name = PARENT[name]
        chain.append(name)
    return tuple(reversed(chain))


def descendant_fields(gate_id: str) -> tuple[str, ...]:
    """Every Patient field below a gate, including gates that are fields."""
    fields: list[str] = []
    for child in GATES[gate_id].children:
        if child in FIELDS:
            fields.append(child)
        if child in GATES:
            fields.extend(descendant_fields(child))
    return tuple(fields)


def absent_value(name: str):
    return Finding.ABSENT.value if FIELDS[name].type is Finding else 0


def _positive(value) -> bool:
    if isinstance(value, Finding):
        return value is Finding.PRESENT
    if isinstance(value, str):
        return value.strip().lower() in ("present", "yes", "y")
    return value is not None and value > 0


def _negative(value) -> bool:
    if isinstance(value, Finding):
        return value is Finding.ABSENT
    if isinstance(value, str):
        return value.strip().lower() in ("absent", "no", "n")
    return value == 0


def _own(gate_id: str) -> tuple[str, ...]:
    return (gate_id,) if gate_id in FIELDS else ()


def gate_state(gate_id: str, values: dict) -> str | None:
    """Return "yes" if anything under the gate is present, "no" if all of it
    is absent, otherwise None: the answers so far do not settle it."""
    names = (*_own(gate_id), *descendant_fields(gate_id))
    if any(_positive(values.get(n)) for n in names):
        return "yes"
    if all(_negative(values.get(n)) for n in names):
        return "no"
    return None


def answer_gate(values: dict, gate_id: str, answer: Finding) -> dict:
    """The answers after `answer` to a gate. "No" fills in every detail."""
    values = dict(values)
    if answer is Finding.ABSENT:
        below = descendant_fields(gate_id)
        clash = [n for n in below if _positive(values.get(n))]
        if clash:
            raise InputError(
                f"'No' contradicts {', '.join(clash)} already answered as present"
            )
        for name in below:
            values[name] = absent_value(name)
    if gate_id in FIELDS:
        values[gate_id] = answer.value
    return values


def next_prompt(
    field: str, asked: set[str], values: dict, needed: set[str] | None = None
) -> str:
    """What to ask before `field`: its topmost gate worth asking, or the field.

    A gate is skipped once asked, once its own field is answered, or once
    something below it is present (which makes it "yes"). With `needed` (the
    inputs that could still change a result), a gate is also skipped unless it
    is needed itself or "No" to it could settle two or more needed details:
    otherwise asking it only adds a question.
    """
    for gate_id in ancestors(field):
        if gate_id in asked or gate_state(gate_id, values) == "yes":
            continue
        own = values.get(gate_id) if gate_id in FIELDS else None
        if own is not None and own != Finding.UNKNOWN.value:
            continue
        if needed is not None and gate_id not in needed:
            below = set(descendant_fields(gate_id)) & needed
            if len(below) < 2:
                continue
        return gate_id
    return field


def question_text(name: str) -> str:
    if name in GATES:
        return GATES[name].text
    return FIELDS[name].metadata["help"]
