"""Command-line interface. Educational use only, not for clinical use.

Any finding not supplied, by flag or in the JSON file, is UNKNOWN, never ABSENT.
"""

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from ct_head_rules.cchr import (
    CCHRInput,
    CCHRResult,
    CriterionResult,
    Outcome,
    evaluate_cchr,
)
from ct_head_rules.findings import Finding

DISCLAIMER = "Educational use only. NOT for clinical use."

FIELDS = dataclasses.fields(CCHRInput)
FINDING_VALUES = [finding.value for finding in Finding]

OUTCOME_LABELS = {
    Outcome.CT_RECOMMENDED: "CT recommended",
    Outcome.CT_NOT_REQUIRED: "CT not required by this rule",
    Outcome.NOT_APPLICABLE: "Rule not applicable to this patient",
    Outcome.INDETERMINATE: "Indeterminate: missing inputs prevent a conclusion",
}


class InputError(Exception):
    """Patient input that cannot be turned into a CCHRInput."""


def _flag(name: str) -> str:
    return "--" + name.replace("_", "-")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ct-head-rules",
        description=f"Clinical decision rules for head CT imaging. {DISCLAIMER}",
    )
    rules = parser.add_subparsers(dest="rule", required=True, metavar="RULE")
    cchr = rules.add_parser(
        "cchr",
        help="Canadian CT Head Rule (Stiell et al., Lancet 2001)",
        description=f"Canadian CT Head Rule (Stiell et al., Lancet 2001). {DISCLAIMER}",
        epilog="Any finding not given is treated as unknown, never as absent.",
    )
    cchr.add_argument(
        "--json",
        type=Path,
        metavar="FILE",
        help="patient findings as a JSON object; flags override values in it",
    )
    cchr.add_argument("--format", choices=["text", "json"], default="text")
    cchr.add_argument(
        "--template",
        action="store_true",
        help="print a JSON template with every finding unknown, then exit",
    )

    findings = cchr.add_argument_group("patient findings")
    for field in FIELDS:
        if field.type is Finding:
            findings.add_argument(_flag(field.name), choices=FINDING_VALUES)
        else:
            number = int if field.type == int | None else float
            findings.add_argument(_flag(field.name), type=number, metavar="N")
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

    unrecognised = sorted(set(data) - {field.name for field in FIELDS})
    if unrecognised:
        raise InputError(f"{path}: unrecognised field(s): {', '.join(unrecognised)}")
    return data


def _to_input(values: dict) -> CCHRInput:
    kwargs = {}
    for field in FIELDS:
        value = values.get(field.name)
        if field.type is not Finding:
            kwargs[field.name] = value
        elif value is None:
            kwargs[field.name] = Finding.UNKNOWN
        elif isinstance(value, str) and value in FINDING_VALUES:
            kwargs[field.name] = Finding(value)
        else:
            raise InputError(
                f"{field.name} must be one of {', '.join(FINDING_VALUES)}, "
                f"got {value!r}"
            )
    try:
        return CCHRInput(**kwargs)
    except (TypeError, ValueError) as error:
        raise InputError(str(error)) from error


def _template() -> dict:
    return {
        field.name: Finding.UNKNOWN.value if field.type is Finding else None
        for field in FIELDS
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


def format_json(result: CCHRResult) -> str:
    return json.dumps(
        {
            "rule": "cchr",
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


def format_text(result: CCHRResult) -> str:
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

    lines = ["Canadian CT Head Rule (Stiell et al., Lancet 2001)", DISCLAIMER, ""]
    lines.append(f"Outcome: {outcome}")
    for title, items in sections:
        if items:
            lines += ["", f"{title}:", *(f"  - {item}" for item in items)]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.template:
        print(json.dumps(_template(), indent=2))
        return 0

    try:
        values = _load_json(args.json) if args.json else {}
        for field in FIELDS:
            flag_value = getattr(args, field.name)
            if flag_value is not None:
                values[field.name] = flag_value
        patient = _to_input(values)
    except InputError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    result = evaluate_cchr(patient)
    print(format_json(result) if args.format == "json" else format_text(result))
    return 0
