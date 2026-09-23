"""One entry point shared by the CLI, the interview and the web form.

Educational use only, not for clinical use. Any finding not supplied is
UNKNOWN, never ABSENT.
"""

import dataclasses
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from ct_head_rules.cchr import CCHR_INPUTS, evaluate_cchr
from ct_head_rules.findings import Finding
from ct_head_rules.noc import NOC_INPUTS, evaluate_noc
from ct_head_rules.patient import Patient
from ct_head_rules.pecarn import PECARN_INPUTS, evaluate_pecarn
from ct_head_rules.rules import CriterionResult, Outcome, RuleResult

DISCLAIMER = "Educational use only. NOT for clinical use."

FIELDS = {field.name: field for field in dataclasses.fields(Patient)}
FINDING_VALUES = [finding.value for finding in Finding]

# Short answers accepted wherever a finding is typed. JSON true/false and 0/1
# are still rejected: which of them would mean "unknown" is not obvious.
FINDING_ALIASES = {
    "yes": Finding.PRESENT,
    "y": Finding.PRESENT,
    "no": Finding.ABSENT,
    "n": Finding.ABSENT,
    "u": Finding.UNKNOWN,
    "?": Finding.UNKNOWN,
} | {finding.value: finding for finding in Finding}

OUTCOME_LABELS = {
    Outcome.CT_RECOMMENDED: "CT recommended",
    Outcome.OBSERVATION_OR_CT: "Observation or CT, based on other clinical factors",
    Outcome.CT_NOT_REQUIRED: "CT not required by this rule",
    Outcome.NOT_APPLICABLE: "Rule not applicable to this patient",
    Outcome.INDETERMINATE: "Indeterminate: missing inputs prevent a conclusion",
}


@dataclass(frozen=True)
class RuleSpec:
    title: str
    evaluate: Callable[[Patient], RuleResult]
    inputs: tuple[str, ...]


RULES = {
    "cchr": RuleSpec(
        "Canadian CT Head Rule (Stiell et al., Lancet 2001)", evaluate_cchr, CCHR_INPUTS
    ),
    "noc": RuleSpec(
        "New Orleans Criteria (Haydel et al., N Engl J Med 2000)",
        evaluate_noc,
        NOC_INPUTS,
    ),
    "pecarn": RuleSpec(
        "PECARN (Kuppermann et al., Lancet 2009)", evaluate_pecarn, PECARN_INPUTS
    ),
}

ALL_INPUTS = tuple(FIELDS)  # every rule's inputs, in Patient field order


class InputError(Exception):
    """Patient input that cannot be turned into a Patient."""


def parse_finding(value: str) -> Finding:
    """A typed finding: present/absent/unknown or yes/y, no/n, u/?."""
    try:
        return FINDING_ALIASES[value.strip().lower()]
    except KeyError:
        raise InputError(
            f"must be one of {', '.join(FINDING_VALUES)} (or y/n/u), got {value!r}"
        ) from None


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except OSError as error:
        raise InputError(f"cannot read {path}: {error.strerror}") from error
    except json.JSONDecodeError as error:
        raise InputError(f"{path} is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise InputError(f"{path} must contain a JSON object")
    check_field_names(data, where=str(path))
    return data


def check_field_names(data: dict, where: str = "input") -> None:
    unrecognised = sorted(set(data) - set(FIELDS))
    if unrecognised:
        raise InputError(f"{where}: unrecognised field(s): {', '.join(unrecognised)}")


def parse_values(values: dict) -> Patient:
    """Field values as found in JSON (findings as strings) to a Patient."""
    check_field_names(values)
    kwargs = {}
    for name, value in values.items():
        if FIELDS[name].type is not Finding:
            kwargs[name] = value
        elif value is None:
            kwargs[name] = Finding.UNKNOWN
        elif isinstance(value, Finding):
            kwargs[name] = value
        elif isinstance(value, str):
            try:
                kwargs[name] = parse_finding(value)
            except InputError as error:
                raise InputError(f"{name} {error}") from None
        else:
            raise InputError(
                f"{name} must be one of {', '.join(FINDING_VALUES)}, got {value!r}"
            )
    try:
        return Patient(**kwargs)
    except (TypeError, ValueError) as error:
        raise InputError(str(error)) from error


def patient_to_values(patient: Patient, names: Iterable[str] = ALL_INPUTS) -> dict:
    """The inverse of parse_values, for the named fields."""
    values = {}
    for name in names:
        value = getattr(patient, name)
        values[name] = value.value if isinstance(value, Finding) else value
    return values


def template(inputs: Iterable[str]) -> dict:
    return patient_to_values(Patient(), inputs)


def evaluate_all(
    patient: Patient, rules: Iterable[str] = tuple(RULES)
) -> dict[str, RuleResult]:
    return {name: RULES[name].evaluate(patient) for name in rules}


def _criterion_dict(criterion: CriterionResult) -> dict:
    return {
        "id": criterion.id,
        "label": criterion.label,
        "kind": criterion.kind,
        "status": criterion.status.value,
        "source": criterion.source,
        "inputs_used": list(criterion.inputs_used),
        "missing_inputs": list(criterion.missing_inputs),
    }


def result_to_dict(result: RuleResult) -> dict:
    return {
        "rule": result.rule,
        "disclaimer": DISCLAIMER,
        "outcome": result.outcome.value,
        "risk_level": result.risk_level.value if result.risk_level else None,
        "triggered": [c.id for c in result.triggered],
        "exclusion_reasons": [c.id for c in result.exclusion_reasons],
        "missing_inputs": list(result.missing_inputs),
        "notes": list(result.notes),
        "criteria": [_criterion_dict(c) for c in result.criteria],
    }
