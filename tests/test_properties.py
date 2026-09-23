"""Randomised property tests across all three rules.

Seeded, so every run checks the same cases. A failure names the seed and the
patient. Set CT_PROPERTY_CASES to run more (e.g. 50000) locally.
"""

import dataclasses
import json
import os
import random

import pytest

from ct_head_rules.api import (
    ALL_INPUTS,
    FIELDS,
    RULES,
    evaluate_all,
    parse_values,
    patient_to_values,
    result_to_dict,
)
from ct_head_rules.cli import main
from ct_head_rules.findings import Finding
from ct_head_rules.interview import interview, is_settled
from ct_head_rules.patient import Patient
from ct_head_rules.rules import CriterionStatus, Outcome
from ct_head_rules.web import evaluate_payload

CASES = int(os.environ.get("CT_PROPERTY_CASES", "1500"))
COMPLETIONS = 8
SEED = 20260923

# Values either side of every threshold in the three papers.
NUMBER_POOLS = {
    "age_years": [0, 1, 2, 3, 15, 16, 17, 18, 60, 61, 64, 65, 90],
    "initial_ed_gcs": [3, 12, 13, 14, 15],
    "gcs_2h_post_injury": [3, 13, 14, 15],
    "hours_since_injury": [0, 1.5, 2, 24, 24.1],
    "vomiting_episodes": [0, 1, 2, 5],
    "retrograde_amnesia_minutes": [0, 30, 30.5, 31],
    "loc_duration_seconds": [0, 4, 5, 60],
    "fall_height_m": [0, 0.9, 1.0, 1.5, 1.6],
}
assert set(NUMBER_POOLS) == {n for n in ALL_INPUTS if FIELDS[n].type is not Finding}

# What more information may turn each outcome into (rules.decide, steps 1-4).
ALLOWED_AFTER_MORE_INFO = {
    Outcome.CT_RECOMMENDED: {Outcome.CT_RECOMMENDED, Outcome.NOT_APPLICABLE},
    Outcome.OBSERVATION_OR_CT: {
        Outcome.OBSERVATION_OR_CT,
        Outcome.CT_RECOMMENDED,
        Outcome.NOT_APPLICABLE,
    },
    Outcome.CT_NOT_REQUIRED: {Outcome.CT_NOT_REQUIRED},
    Outcome.NOT_APPLICABLE: {Outcome.NOT_APPLICABLE},
    Outcome.INDETERMINATE: set(Outcome),
}


def _one_way_links() -> dict[str, set[str]]:
    """{implying field: fields it implies}, from each criterion's also_reads.

    A PRESENT implying field makes the criterion MET even if the implied field
    is ABSENT: contradictory data resolves towards "present".
    """
    from ct_head_rules import cchr, noc, pecarn
    from ct_head_rules.rules import _Criterion

    links: dict[str, set[str]] = {}
    for module in (cchr, noc, pecarn):
        for value in vars(module).values():
            if not isinstance(value, tuple):
                continue
            for criterion in value:
                if isinstance(criterion, _Criterion) and criterion.also_reads:
                    (implied,) = [
                        n for n in criterion.inputs if FIELDS[n].type is Finding
                    ]
                    for name in criterion.also_reads:
                        links.setdefault(name, set()).add(implied)
    return links


ONE_WAY_LINKS = _one_way_links()
assert ONE_WAY_LINKS["witnessed_loc"] == {"history_of_loc"}
assert ONE_WAY_LINKS["severe_headache"] == {"headache"}


def random_patient(rng: random.Random) -> Patient:
    unknown_rate = rng.choice([0.0, 0.05, 0.2, 0.5, 0.9])
    values = {}
    for name in ALL_INPUTS:
        if rng.random() < unknown_rate:
            continue  # left unknown
        if name in NUMBER_POOLS:
            values[name] = rng.choice(NUMBER_POOLS[name])
        else:
            values[name] = Finding.PRESENT if rng.random() < 0.15 else Finding.ABSENT
    return Patient(**values)


def complete(patient: Patient, rng: random.Random) -> Patient:
    """Fill every unknown input with a random known value that does not
    contradict what is known: a field implying one that is ABSENT stays ABSENT.
    """
    filled = {}
    for name in ALL_INPUTS:
        value = getattr(patient, name)
        if value is Finding.UNKNOWN:
            implied = ONE_WAY_LINKS.get(name, set())
            if any(getattr(patient, n) is Finding.ABSENT for n in implied):
                filled[name] = Finding.ABSENT
            else:
                filled[name] = rng.choice([Finding.PRESENT, Finding.ABSENT])
        elif value is None:
            filled[name] = rng.choice(NUMBER_POOLS[name])
    return dataclasses.replace(patient, **filled)


def patients(seed: int = SEED, count: int = CASES):
    rng = random.Random(seed)
    for case in range(count):
        yield case, rng, random_patient(rng)


def every_criterion_decided(result) -> bool:
    # An unknown input can still be listed as missing when its criterion is
    # already decided, e.g. amnesia when witnessed LOC is present ("reported but
    # not blocking", tests/test_*_missing.py). What must hold is that no
    # criterion is left unknown.
    return all(c.status is not CriterionStatus.UNKNOWN for c in result.criteria)


def where(case: int, patient: Patient) -> str:
    known = {
        k: v
        for k, v in patient_to_values(patient).items()
        if v is not None and v != "unknown"
    }
    return f"seed {SEED}, case {case}: {known}"


# --- 1-3: outcomes only move the ways the rules allow -----------------------------


def test_unknown_is_never_negative_and_settled_results_stay_settled():
    checked_settled = 0
    for case, rng, patient in patients():
        results = evaluate_all(patient)
        completions = [evaluate_all(complete(patient, rng)) for _ in range(COMPLETIONS)]
        for name, result in results.items():
            if result.outcome is Outcome.CT_NOT_REQUIRED:
                assert every_criterion_decided(result), where(case, patient)
            settled = is_settled(result)
            checked_settled += settled
            for completion in completions:
                after = completion[name]
                assert after.outcome in ALLOWED_AFTER_MORE_INFO[result.outcome], (
                    f"{name}: {result.outcome} became {after.outcome}; "
                    + where(case, patient)
                )
                if settled:
                    assert (after.outcome, after.risk_level) == (
                        result.outcome,
                        result.risk_level,
                    ), f"{name} was settled but changed; " + where(case, patient)
    assert checked_settled > CASES // 2  # the property was really exercised


# --- 4: the rules keep to their own populations and outcomes ------------------------


def test_rules_stay_within_their_populations_and_outcomes():
    for case, _, patient in patients():
        results = evaluate_all(patient)
        where_ = where(case, patient)
        for name in ("cchr", "noc"):
            assert results[name].outcome is not Outcome.OBSERVATION_OR_CT, where_
        age = patient.age_years
        if age is not None and age >= 18:
            assert results["pecarn"].outcome is Outcome.NOT_APPLICABLE, where_
        if age is not None and age < 16:
            assert results["cchr"].outcome is Outcome.NOT_APPLICABLE, where_
        if age is not None and age < 3:
            assert results["noc"].outcome is Outcome.NOT_APPLICABLE, where_
        for result in results.values():
            if result.outcome is Outcome.NOT_APPLICABLE:
                assert result.exclusion_reasons, where_
            if result.outcome in (Outcome.CT_RECOMMENDED, Outcome.OBSERVATION_OR_CT):
                assert result.triggered, where_


# --- 5: the interview always ends, asking each question once ------------------------

ANSWERS = ["y", "n", "u", "", "yes", "NO", "?", "abc", "-1", "0", "2", "15", "16",
           "24.1", "1e3", "nan", "inf", " 3 ", "１"]  # fmt: skip


def random_answers(rng: random.Random, asked: list[str], label: str):
    """Mostly random answers, valid or not; blank after 5 tries at one question."""

    def ask(name: str, prompt: str) -> str:
        if len(asked) > 10 * len(ALL_INPUTS):
            raise AssertionError(f"interview did not end; {label}")
        asked.append(name)
        tries = asked.count(name)
        return rng.choice(ANSWERS) if tries <= 5 else ""

    return ask


def test_interview_always_ends_and_asks_each_question_once():
    rng = random.Random(SEED)
    for case in range(CASES // 10):
        start = patient_to_values(random_patient(rng))
        start = {k: v for k, v in start.items() if v is not None and v != "unknown"}
        asked: list[str] = []
        label = f"case {case}: {start}"

        ask = random_answers(rng, asked, label)
        values = interview(dict(start), tuple(RULES), ask, lambda _: None)

        questions = [n for i, n in enumerate(asked) if i == 0 or asked[i - 1] != n]
        assert len(questions) == len(set(questions)), f"{label}; asked {asked}"
        parse_values(values)  # whatever was accepted is a valid patient


# --- 6: every surface gives the same answer -----------------------------------------


def test_values_round_trip():
    for case, _, patient in patients():
        assert parse_values(patient_to_values(patient)) == patient, where(case, patient)


def test_cli_and_web_give_identical_results(tmp_path, capsys):
    path = tmp_path / "patient.json"
    for case, _, patient in patients(count=CASES // 15):
        values = patient_to_values(patient)
        path.write_text(json.dumps(values))
        assert main(["all", "--json", str(path), "--format", "json"]) == 0
        cli = json.loads(capsys.readouterr().out)["results"]
        web = evaluate_payload(values, tuple(RULES))["results"]
        engine = {n: result_to_dict(r) for n, r in evaluate_all(patient).items()}
        for name in RULES:
            assert cli[name] == engine[name], where(case, patient)
            assert {k: web[name][k] for k in engine[name]} == engine[name]


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_different_seeds_also_hold(seed):
    rng = random.Random(seed)
    for _ in range(CASES // 10):
        patient = random_patient(rng)
        for result in evaluate_all(patient).values():
            if result.outcome is Outcome.CT_NOT_REQUIRED:
                assert every_criterion_decided(result)


# --- 8: answering through the question tree changes no result -----------------------


def consistent(patient: Patient) -> Patient:
    """A broad finding is present whenever something below it is present."""
    from ct_head_rules.questions import GATES, descendant_fields

    fixes = {}
    for gate_id in GATES:
        if gate_id in FIELDS and any(
            getattr(patient, n) is Finding.PRESENT
            or (FIELDS[n].type is not Finding and (getattr(patient, n) or 0) > 0)
            for n in descendant_fields(gate_id)
        ):
            fixes[gate_id] = Finding.PRESENT
    return dataclasses.replace(patient, **fixes)


def test_truthful_answers_through_the_tree_give_the_same_results():
    from patients import answers_through_tree

    for case, rng, patient in patients(count=CASES // 3):
        patient = consistent(complete(patient, rng))
        answers = answers_through_tree(patient)
        values = interview(
            {}, tuple(RULES), lambda name, _, a=answers: a.get(name, ""), lambda _: None
        )
        got = evaluate_all(parse_values(values))
        for name, expected in evaluate_all(patient).items():
            assert (got[name].outcome, got[name].risk_level) == (
                expected.outcome,
                expected.risk_level,
            ), f"{name}; " + where(case, patient)
