"""Result types and decision steps shared by all rules. Not for clinical use."""

import dataclasses
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from ct_head_rules.findings import Finding
from ct_head_rules.patient import Patient


class CriterionStatus(Enum):
    MET = "met"
    NOT_MET = "not_met"
    UNKNOWN = "unknown"


class RiskLevel(Enum):
    HIGH = "high"  # for neurological intervention
    MEDIUM = "medium"  # for brain injury on CT


class Outcome(Enum):
    CT_RECOMMENDED = "ct_recommended"
    # PECARN's middle group: "observation versus CT on the basis of other
    # clinical factors" (Kuppermann 2009, Figure 3, p1168).
    OBSERVATION_OR_CT = "observation_or_ct"
    CT_NOT_REQUIRED = "ct_not_required"  # only when every relevant input is known
    NOT_APPLICABLE = "not_applicable"  # excluded, or outside the rule's population
    INDETERMINATE = "indeterminate"  # missing inputs prevent a conclusion


# "risk_factor" is for rules with a single tier, such as the New Orleans Criteria.
CriterionKind = Literal[
    "inclusion", "exclusion", "high_risk", "medium_risk", "risk_factor"
]


@dataclass(frozen=True)
class CriterionResult:
    """One criterion checked against one patient.

    For inclusions, MET means the requirement is satisfied. For exclusions,
    MET means the patient is excluded.
    """

    id: str
    label: str
    kind: CriterionKind
    status: CriterionStatus
    source: str
    inputs_used: tuple[str, ...]
    missing_inputs: tuple[str, ...]


@dataclass(frozen=True)
class RuleResult:
    rule: str  # "cchr", "noc" or "pecarn"
    outcome: Outcome
    risk_level: RiskLevel | None  # tiered rules only, when a tier is met
    triggered: tuple[CriterionResult, ...]  # met risk criteria, when a tier is met
    exclusion_reasons: tuple[CriterionResult, ...]  # why the rule does not apply
    criteria: tuple[CriterionResult, ...]  # every criterion checked, for audit
    missing_inputs: tuple[str, ...]  # in Patient field order
    notes: tuple[str, ...]


# --- Status helpers ---------------------------------------------------------


def _is_missing(value: object) -> bool:
    return value is None or value is Finding.UNKNOWN


def _from_finding(value: Finding) -> CriterionStatus:
    if value is Finding.PRESENT:
        return CriterionStatus.MET
    if value is Finding.ABSENT:
        return CriterionStatus.NOT_MET
    return CriterionStatus.UNKNOWN


def _either(*statuses: CriterionStatus) -> CriterionStatus:
    """MET if any is met; NOT_MET only if every one is known not met."""
    if CriterionStatus.MET in statuses:
        return CriterionStatus.MET
    if all(s is CriterionStatus.NOT_MET for s in statuses):
        return CriterionStatus.NOT_MET
    return CriterionStatus.UNKNOWN


def _any_of(*values: Finding) -> CriterionStatus:
    """MET if any is present; NOT_MET only if every one is known absent."""
    return _either(*(_from_finding(v) for v in values))


def _present_implies(primary: Finding, *implying: Finding) -> CriterionStatus:
    """MET if `primary` or any implying finding is present.

    Only PRESENT carries over from the implying findings: NOT_MET depends on
    `primary` alone, so an unknown or absent implying finding never blocks or
    decides a negative.
    """
    if primary is Finding.PRESENT or Finding.PRESENT in implying:
        return CriterionStatus.MET
    return _from_finding(primary)


def _compare(
    value: float | None, predicate: Callable[[float], bool]
) -> CriterionStatus:
    if value is None:
        return CriterionStatus.UNKNOWN
    return CriterionStatus.MET if predicate(value) else CriterionStatus.NOT_MET


@dataclass(frozen=True)
class _Criterion:
    id: str
    label: str
    kind: CriterionKind
    source: str
    inputs: tuple[str, ...]  # reported as missing when unknown
    evaluate: Callable[[Patient], CriterionStatus]
    also_reads: tuple[str, ...] = ()  # can only make the criterion MET

    def apply(self, patient: Patient) -> CriterionResult:
        return CriterionResult(
            id=self.id,
            label=self.label,
            kind=self.kind,
            status=self.evaluate(patient),
            source=self.source,
            inputs_used=self.inputs + self.also_reads,
            missing_inputs=tuple(
                name for name in self.inputs if _is_missing(getattr(patient, name))
            ),
        )


def _in_field_order(names: Iterable[str]) -> tuple[str, ...]:
    wanted = set(names)
    return tuple(f.name for f in dataclasses.fields(Patient) if f.name in wanted)


def rule_inputs(*criteria: _Criterion) -> tuple[str, ...]:
    """The fields a rule asks for, in Patient field order."""
    return _in_field_order(name for c in criteria for name in c.inputs)


def _any_status(criteria: Iterable[CriterionResult], status: CriterionStatus) -> bool:
    return any(c.status is status for c in criteria)


# --- Decision ---------------------------------------------------------------


def decide(
    rule: str,
    patient: Patient,
    inclusions: tuple[_Criterion, ...],
    exclusions: tuple[_Criterion, ...],
    tiers: tuple[tuple[RiskLevel | None, Outcome, tuple[_Criterion, ...]], ...],
) -> RuleResult:
    """The decision steps every rule shares. Rules add their own notes after.

    `tiers` lists the risk criteria from highest tier to lowest, each with the
    outcome it leads to. A rule with a single tier passes level None.
    """
    inclusion_results = tuple(c.apply(patient) for c in inclusions)
    exclusion_results = tuple(c.apply(patient) for c in exclusions)
    tier_results = tuple(
        (level, outcome, tuple(c.apply(patient) for c in criteria))
        for level, outcome, criteria in tiers
    )
    risk_results = tuple(r for _, _, results in tier_results for r in results)
    all_results = (*inclusion_results, *exclusion_results, *risk_results)

    def result(
        outcome: Outcome,
        risk_level: RiskLevel | None = None,
        triggered: tuple[CriterionResult, ...] = (),
        exclusion_reasons: tuple[CriterionResult, ...] = (),
    ) -> RuleResult:
        return RuleResult(
            rule=rule,
            outcome=outcome,
            risk_level=risk_level,
            triggered=triggered,
            exclusion_reasons=exclusion_reasons,
            criteria=all_results,
            missing_inputs=_in_field_order(
                name for c in all_results for name in c.missing_inputs
            ),
            notes=(),
        )

    # 1. A known exclusion or failed inclusion means the rule does not apply,
    #    whatever else is known or missing.
    reasons = tuple(
        c for c in inclusion_results if c.status is CriterionStatus.NOT_MET
    ) + tuple(c for c in exclusion_results if c.status is CriterionStatus.MET)
    if reasons:
        return result(Outcome.NOT_APPLICABLE, exclusion_reasons=reasons)

    # 2. A met risk criterion gives its tier's outcome, at the highest tier met,
    #    even if applicability is not fully known: missing data could only make
    #    the rule not apply (no guidance), never make CT unnecessary.
    triggered = tuple(c for c in risk_results if c.status is CriterionStatus.MET)
    for level, outcome, results in tier_results:
        if _any_status(results, CriterionStatus.MET):
            return result(outcome, level, triggered)

    # 3. Nothing met, but something unknown: unknown is never negative.
    if _any_status(all_results, CriterionStatus.UNKNOWN):
        return result(Outcome.INDETERMINATE)

    # 4. Eligible, every criterion known, none met.
    return result(Outcome.CT_NOT_REQUIRED)


def with_notes(result: RuleResult, *notes: str) -> RuleResult:
    return dataclasses.replace(result, notes=result.notes + notes)
