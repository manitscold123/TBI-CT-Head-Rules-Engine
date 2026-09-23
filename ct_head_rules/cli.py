"""Command-line interface. Educational use only, not for clinical use.

Any finding not supplied, by flag or in the JSON file, is UNKNOWN, never ABSENT.
"""

import argparse
import json
import sys
from pathlib import Path

from ct_head_rules.api import (
    ALL_INPUTS,
    DISCLAIMER,
    FIELDS,
    FINDING_VALUES,
    OUTCOME_LABELS,
    RULES,
    InputError,
    evaluate_all,
    load_json,
    parse_finding,
    parse_values,
    result_to_dict,
    template,
)
from ct_head_rules.findings import Finding
from ct_head_rules.interview import interview, open_criteria
from ct_head_rules.rules import CriterionResult, Outcome, RuleResult

__all__ = ["DISCLAIMER", "RULES", "build_parser", "format_text", "main"]

UNKNOWN_EPILOG = "Any finding not given is treated as unknown, never as absent."


def _flag(name: str) -> str:
    return "--" + name.replace("_", "-")


def _finding_arg(value: str) -> str:
    try:
        return parse_finding(value).value
    except InputError as error:
        raise argparse.ArgumentTypeError(str(error)) from None


def _rule_list(value: str) -> tuple[str, ...]:
    names = tuple(name.strip() for name in value.split(",") if name.strip())
    unknown = [name for name in names if name not in RULES]
    if unknown or not names:
        raise argparse.ArgumentTypeError(
            f"unknown rule(s) {', '.join(unknown) or '(none given)'}; "
            f"choose from {', '.join(RULES)}"
        )
    return names


def _add_input_arguments(parser: argparse.ArgumentParser, inputs, what: str) -> None:
    parser.add_argument(
        "--json",
        type=Path,
        metavar="FILE",
        help="patient findings as a JSON object (any rule's fields); "
        "flags override values in it",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument(
        "--template",
        action="store_true",
        help=f"print a JSON template of {what}, all unknown, then exit",
    )

    findings = parser.add_argument_group("patient findings")
    for field_name in inputs:
        field = FIELDS[field_name]
        help_text = field.metadata["help"]
        if field.type is Finding:
            findings.add_argument(
                _flag(field_name),
                type=_finding_arg,
                metavar="{" + ",".join(FINDING_VALUES) + "}",
                help=f"{help_text} (or y/n/u)",
            )
        else:
            number = int if field.type == int | None else float
            findings.add_argument(
                _flag(field_name), type=number, metavar="N", help=help_text
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ct-head-rules",
        description=f"Clinical decision rules for head CT imaging. {DISCLAIMER}",
    )
    commands = parser.add_subparsers(dest="rule", required=True, metavar="COMMAND")
    for name, spec in RULES.items():
        rule = commands.add_parser(
            name,
            help=spec.title,
            description=f"{spec.title}. {DISCLAIMER}",
            epilog=UNKNOWN_EPILOG,
        )
        _add_input_arguments(rule, spec.inputs, "this rule's inputs")

    every = commands.add_parser(
        "all",
        help="run every rule on one patient and compare",
        description=f"Run every rule on one patient. {DISCLAIMER}",
        epilog=UNKNOWN_EPILOG,
    )
    _add_rules_argument(every)
    every.add_argument(
        "--detail", action="store_true", help="add each rule's full report"
    )
    _add_input_arguments(every, ALL_INPUTS, "every rule's inputs")

    ask = commands.add_parser(
        "ask",
        help="answer questions one at a time; only what can change a result",
        description=f"Guided interview across the rules. {DISCLAIMER}",
        epilog="Press Enter for unknown; unknown is never treated as absent.",
    )
    _add_rules_argument(ask)
    ask.add_argument(
        "--json", type=Path, metavar="FILE", help="start from answers in this file"
    )
    ask.add_argument(
        "--save",
        type=Path,
        metavar="FILE",
        help="save the answers as JSON, for --json later",
    )
    return parser


def _add_rules_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--rules",
        type=_rule_list,
        default=tuple(RULES),
        metavar="LIST",
        help=f"comma-separated subset of {','.join(RULES)} (default: all)",
    )


# --- Output ------------------------------------------------------------------


def format_json(result: RuleResult) -> str:
    return json.dumps(result_to_dict(result), indent=2)


def _outcome_text(result: RuleResult) -> str:
    outcome = OUTCOME_LABELS[result.outcome]
    if result.risk_level:
        outcome += f" ({result.risk_level.value} risk)"
    return outcome


def _reason(criterion: CriterionResult) -> str:
    prefix = "Not met: " if criterion.kind == "inclusion" else ""
    return f"{prefix}{criterion.label}"


def format_text(result: RuleResult) -> str:
    sections = [
        (
            "Triggered criteria",
            [f"{c.label} [{c.source}]" for c in result.triggered],
        ),
        (
            "Rule does not apply because",
            [f"{_reason(c)} [{c.source}]" for c in result.exclusion_reasons],
        ),
        (
            "Missing inputs",
            [f"{name} ({_flag(name)})" for name in result.missing_inputs],
        ),
        ("Notes", list(result.notes)),
    ]

    lines = [RULES[result.rule].title, DISCLAIMER, ""]
    lines.append(f"Outcome: {_outcome_text(result)}")
    for title, items in sections:
        if items:
            lines += ["", f"{title}:", *(f"  - {item}" for item in items)]
    return "\n".join(lines)


def _summary_reason(result: RuleResult) -> str:
    if result.triggered:
        return "; ".join(c.label for c in result.triggered)
    if result.exclusion_reasons:
        return "; ".join(_reason(c) for c in result.exclusion_reasons)
    if result.outcome is Outcome.INDETERMINATE:
        count = len(result.missing_inputs)
        return f"{count} input{'s' if count != 1 else ''} missing"
    return "No criteria met"


def merged_missing(results: dict[str, RuleResult]) -> dict[str, list[str]]:
    """Inputs that could still change a result, with the rules that need them.

    Inputs that cannot change an outcome are left out, such as those of a rule
    that does not apply, or lower-tier factors once CT is recommended. Each
    rule's full list is in its own report (--detail).
    """
    needed: dict[str, list[str]] = {}
    for name, result in results.items():
        for criterion in open_criteria(result):
            for field in criterion.missing_inputs:
                if name not in needed.setdefault(field, []):
                    needed[field].append(name)
    return {field: needed[field] for field in ALL_INPUTS if field in needed}


def format_summary(results: dict[str, RuleResult], detail: bool = False) -> str:
    width = max(len(name) for name in results) + 2
    lines = [DISCLAIMER, ""]
    for name, result in results.items():
        lines.append(f"{name:<{width}}{_outcome_text(result)}")
        lines.append(f"{'':<{width}}{_summary_reason(result)}")

    missing = merged_missing(results)
    if missing:
        lines += ["", "Missing inputs that could change a result:"]
        lines += [
            f"  - {_flag(field)}: {', '.join(rules)}"
            for field, rules in missing.items()
        ]
    if detail:
        for result in results.values():
            lines += ["", "-" * 60, format_text(result)]
    return "\n".join(lines)


def format_summary_json(results: dict[str, RuleResult]) -> str:
    return json.dumps(
        {
            "disclaimer": DISCLAIMER,
            "results": {name: result_to_dict(r) for name, r in results.items()},
        },
        indent=2,
    )


# --- Main ----------------------------------------------------------------------


def _read_values(args: argparse.Namespace, inputs) -> dict:
    values = load_json(args.json) if args.json else {}
    for name in inputs:
        flag_value = getattr(args, name)
        if flag_value is not None:
            values[name] = flag_value
    return values


def _run_interview(args: argparse.Namespace) -> int:
    try:
        values = load_json(args.json) if args.json else {}
        parse_values(values)
    except InputError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    try:
        values = interview(values, args.rules, lambda _, prompt: input(prompt), print)
    except KeyboardInterrupt:
        print()
        return 130

    print()
    if args.save:
        args.save.write_text(json.dumps(values, indent=2) + "\n")
        print(f"Answers saved to {args.save}\n")
    print(format_summary(evaluate_all(parse_values(values), args.rules)))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.rule == "ask":
        return _run_interview(args)
    inputs = ALL_INPUTS if args.rule == "all" else RULES[args.rule].inputs

    if args.template:
        print(json.dumps(template(inputs), indent=2))
        return 0

    try:
        patient = parse_values(_read_values(args, inputs))
    except InputError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.rule == "all":
        results = evaluate_all(patient, args.rules)
        if args.format == "json":
            print(format_summary_json(results))
        else:
            print(format_summary(results, args.detail))
        return 0

    result = RULES[args.rule].evaluate(patient)
    print(format_json(result) if args.format == "json" else format_text(result))
    return 0
