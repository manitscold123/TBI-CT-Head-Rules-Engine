"""Guided interview: ask only the inputs that could still change an outcome.

Educational use only, not for clinical use. A question left blank is recorded
as unknown, and unknown is never treated as absent.
"""

from collections.abc import Callable, Iterable

from ct_head_rules.api import (
    ALL_INPUTS,
    DISCLAIMER,
    FIELDS,
    InputError,
    evaluate_all,
    parse_finding,
    parse_values,
)
from ct_head_rules.findings import Finding
from ct_head_rules.rules import (
    CriterionResult,
    CriterionStatus,
    Outcome,
    RuleResult,
    _in_field_order,
)

APPLICABILITY = ("inclusion", "exclusion")
# Lower is a higher tier. The New Orleans Criteria have a single tier.
_TIER_RANK = {"high_risk": 0, "risk_factor": 0, "medium_risk": 1}


def open_criteria(result: RuleResult) -> tuple[CriterionResult, ...]:
    """Unknown criteria whose answer could still change this rule's outcome."""
    if result.outcome in (Outcome.NOT_APPLICABLE, Outcome.CT_NOT_REQUIRED):
        return ()
    unknown = tuple(c for c in result.criteria if c.status is CriterionStatus.UNKNOWN)
    if result.outcome is Outcome.INDETERMINATE:
        return unknown
    # A tier's outcome can still change only if the rule turns out not to
    # apply, or if a higher tier is met (see rules.decide, step 2).
    tier = min(_TIER_RANK[c.kind] for c in result.triggered)
    return tuple(
        c for c in unknown if c.kind in APPLICABILITY or _TIER_RANK[c.kind] < tier
    )


def is_settled(result: RuleResult) -> bool:
    return not any(c.missing_inputs for c in open_criteria(result))


def next_question(results: dict[str, RuleResult], asked: set[str]) -> str | None:
    """The next input to ask for, or None when nothing left could matter.

    Applicability inputs come first, so a rule that does not apply drops out
    before its risk factors are asked; then Patient field order.
    """
    gates: list[str] = []
    risks: list[str] = []
    for result in results.values():
        for criterion in open_criteria(result):
            group = gates if criterion.kind in APPLICABILITY else risks
            group.extend(criterion.missing_inputs)
    for group in (gates, risks):
        for name in _in_field_order(group):
            if name not in asked:
                return name
    return None


def needed_inputs(results: dict[str, RuleResult]) -> dict[str, list[str]]:
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


# --- The question loop ---------------------------------------------------------

_FINISH = object()


def _parse_answer(name: str, text: str):
    field = FIELDS[name]
    if field.type is Finding:
        if not text:
            return Finding.UNKNOWN.value
        try:
            return parse_finding(text).value
        except InputError as error:
            raise InputError(f"{name} {error}") from None
    if not text:
        return None
    whole = field.type == int | None
    try:
        return int(text) if whole else float(text)
    except ValueError:
        kind = "a whole number" if whole else "a number"
        raise InputError(f"{name} must be {kind}, got {text!r}") from None


def _prompt(name: str) -> str:
    field = FIELDS[name]
    hint = "y/n/u" if field.type is Finding else "number"
    return (
        f"\n{name}: {field.metadata['help']}\n"
        f"  [{hint}; Enter if unknown; q to finish] > "
    )


def _ask_one(name: str, values: dict, ask, say):
    while True:
        try:
            text = ask(name, _prompt(name)).strip()
        except EOFError:
            return _FINISH
        if text.lower() == "q":
            return _FINISH
        try:
            value = _parse_answer(name, text)
            parse_values(values | {name: value})  # range checks, e.g. GCS 3-15
            return value
        except InputError as error:
            say(f"  {error}. Try again.")


def interview(
    values: dict,
    rules: Iterable[str],
    ask: Callable[[str, str], str],
    say: Callable[[str], None],
) -> dict:
    """Ask questions until every rule is settled, or the user finishes.

    `ask(name, prompt)` returns the typed answer (EOFError finishes);
    `values` holds answers already known, in JSON form, and is returned
    with the new answers added.
    """
    rules = tuple(rules)
    say(DISCLAIMER)
    say("Answer each question. Press Enter if unknown, or q to finish.")
    asked: set[str] = set()
    while True:
        results = evaluate_all(parse_values(values), rules)
        name = next_question(results, asked)
        if name is None:
            return values
        asked.add(name)
        answer = _ask_one(name, values, ask, say)
        if answer is _FINISH:
            return values
        values = values | {name: answer}
