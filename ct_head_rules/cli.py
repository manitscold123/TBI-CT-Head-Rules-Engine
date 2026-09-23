"""Command-line interface. Educational use only, not for clinical use.

Any finding not supplied, by flag or in the JSON file, is UNKNOWN, never ABSENT.
"""

import argparse
import dataclasses
import json
import sys
from collections.abc import Callable
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


class InputError(Exception):
    """Patient input that cannot be turned into a Patient."""


def _flag(name: str) -> str:
    return "--" + name.replace("_", "-")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ct-head-rules",
        description=f"Clinical decision rules for head CT imaging. {DISCLAIMER}",
    )
    rules = parser.add_subparsers(dest="rule", required=True, metavar="RULE")
    for name, spec in RULES.items():
        rule = rules.add_parser(
            name,
            help=spec.title,
            description=f"{spec.title}. {DISCLAIMER}",
            epilog="Any finding not given is treated as unknown, never as absent.",
        )
        rule.add_argument(
            "--json",
            type=Path,
            metavar="FILE",
            help="patient findings as a JSON object (any rule's fields); "
            "flags override values in it",
        )
        rule.add_argument("--format", choices=["text", "json"], default="text")
        rule.add_argument(
            "--template",
            action="store_true",
            help="print a JSON template of this rule's inputs, all unknown, then exit",
        )

        findings = rule.add_argument_group("patient findings")
        for field_name in spec.inputs:
            field = FIELDS[field_name]
            help_text = field.metadata["help"]
            if field.type is Finding:
                findings.add_argument(
                    _flag(field_name), choices=FINDING_VALUES, help=help_text
                )
            else:
                number = int if field.type == int | None else float
                findings.add_argument(
                    _flag(field_name), type=number, metavar="N", help=help_text
                )
    return parser


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except OSError as error:
        raise InputError(f"cannot read {path}: {error.strerror}") from error
    except json.JSONDecodeError as error:
        raise InputError(f"{path} is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise InputError(f"{path} must contain a JSON object")

    unrecognised = sorted(set(data) - set(FIELDS))
    if unrecognised:
        raise InputError(f"{path}: unrecognised field(s): {', '.join(unrecognised)}")
    return data


def _to_input(values: dict) -> Patient:
    kwargs = {}
    for name, value in values.items():
        if FIELDS[name].type is not Finding:
            kwargs[name] = value
        elif value is None:
            kwargs[name] = Finding.UNKNOWN
        elif isinstance(value, str) and value in FINDING_VALUES:
            kwargs[name] = Finding(value)
        else:
            raise InputError(
                f"{name} must be one of {', '.join(FINDING_VALUES)}, got {value!r}"
            )
    try:
        return Patient(**kwargs)
    except (TypeError, ValueError) as error:
        raise InputError(str(error)) from error


def _template(inputs: tuple[str, ...]) -> dict:
    return {
        name: Finding.UNKNOWN.value if FIELDS[name].type is Finding else None
        for name in inputs
    }


def _criterion_json(criterion: CriterionResult) -> dict:
    return {
        "id": criterion.id,
        "label": criterion.label,
        "kind": criterion.kind,
        "status": criterion.status.value,
        "source": criterion.source,
        "inputs_used": list(criterion.inputs_used),
        "missing_inputs": list(criterion.missing_inputs),
    }


def format_json(result: RuleResult) -> str:
    return json.dumps(
        {
            "rule": result.rule,
            "disclaimer": DISCLAIMER,
            "outcome": result.outcome.value,
            "risk_level": result.risk_level.value if result.risk_level else None,
            "triggered": [c.id for c in result.triggered],
            "exclusion_reasons": [c.id for c in result.exclusion_reasons],
            "missing_inputs": list(result.missing_inputs),
            "notes": list(result.notes),
            "criteria": [_criterion_json(c) for c in result.criteria],
        },
        indent=2,
    )


def format_text(result: RuleResult) -> str:
    outcome = OUTCOME_LABELS[result.outcome]
    if result.risk_level:
        outcome += f" ({result.risk_level.value} risk)"

    def reason(criterion: CriterionResult) -> str:
        prefix = "Not met: " if criterion.kind == "inclusion" else ""
        return f"{prefix}{criterion.label} [{criterion.source}]"

    sections = [
        (
            "Triggered criteria",
            [f"{c.label} [{c.source}]" for c in result.triggered],
        ),
        ("Rule does not apply because", [reason(c) for c in result.exclusion_reasons]),
        (
            "Missing inputs",
            [f"{name} ({_flag(name)})" for name in result.missing_inputs],
        ),
        ("Notes", list(result.notes)),
    ]

    lines = [RULES[result.rule].title, DISCLAIMER, ""]
    lines.append(f"Outcome: {outcome}")
    for title, items in sections:
        if items:
            lines += ["", f"{title}:", *(f"  - {item}" for item in items)]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    spec = RULES[args.rule]

    if args.template:
        print(json.dumps(_template(spec.inputs), indent=2))
        return 0

    try:
        values = _load_json(args.json) if args.json else {}
        for name in spec.inputs:
            flag_value = getattr(args, name)
            if flag_value is not None:
                values[name] = flag_value
        patient = _to_input(values)
    except InputError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    result = spec.evaluate(patient)
    print(format_json(result) if args.format == "json" else format_text(result))
    return 0
