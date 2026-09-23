"""Command-line interface."""

import dataclasses
import json
from pathlib import Path

import pytest
from patients import PRESENT, negative_child, negative_patient

from ct_head_rules.cchr import CCHR_INPUTS
from ct_head_rules.cli import DISCLAIMER, main
from ct_head_rules.findings import Finding
from ct_head_rules.noc import NOC_INPUTS
from ct_head_rules.patient import Patient
from ct_head_rules.pecarn import PECARN_INPUTS

ALL_FIELDS = list(CCHR_INPUTS)  # the default rule in these tests is cchr


def as_json(patient: Patient) -> dict:
    return {
        name: value.value if isinstance(value, Finding) else value
        for name, value in dataclasses.asdict(patient).items()
    }


@pytest.fixture
def patient_file(tmp_path):
    def write(data) -> str:
        path = tmp_path / "patient.json"
        path.write_text(json.dumps(data))
        return str(path)

    return write


def run(capsys, *argv: str, rule: str = "cchr") -> tuple[int, str, str]:
    code = main([rule, *argv])
    out, err = capsys.readouterr()
    return code, out, err


def run_json(capsys, *argv: str, rule: str = "cchr") -> dict:
    code, out, _ = run(capsys, *argv, "--format", "json", rule=rule)
    assert code == 0
    return json.loads(out)


def help_text(capsys, rule: str) -> str:
    with pytest.raises(SystemExit):
        main([rule, "--help"])
    return capsys.readouterr().out


# --- Flags -------------------------------------------------------------------


def test_no_findings_is_indeterminate_with_everything_missing(capsys):
    result = run_json(capsys)

    assert result["outcome"] == "indeterminate"
    assert result["missing_inputs"] == ALL_FIELDS


def test_omitted_flags_are_unknown_not_absent(capsys):
    # Only age given: age >=65 is met, everything else stays unknown.
    result = run_json(capsys, "--age-years", "70")

    assert result["outcome"] == "ct_recommended"
    assert result["risk_level"] == "high"
    assert result["triggered"] == ["cchr.high.age_65_or_over"]
    assert "battle_sign" in result["missing_inputs"]


def test_finding_flag_takes_present_absent_or_unknown(capsys):
    result = run_json(capsys, "--oral-anticoagulant", "present")

    assert result["outcome"] == "not_applicable"
    assert result["exclusion_reasons"] == ["cchr.exclusion.oral_anticoagulant"]


@pytest.mark.parametrize(
    ("value", "finding"),
    [
        ("yes", "present"),
        ("y", "present"),
        ("Y", "present"),
        ("no", "absent"),
        ("n", "absent"),
        ("u", "unknown"),
        ("?", "unknown"),
    ],
)
def test_finding_flag_takes_short_answers(capsys, value, finding):
    result = run_json(capsys, "--battle-sign", value)
    by_id = {c["id"]: c for c in result["criteria"]}
    basal = by_id["cchr.high.basal_skull_fracture_sign"]
    assert ("battle_sign" in basal["missing_inputs"]) is (finding == "unknown")
    if finding == "present":
        assert basal["status"] == "met"


def test_json_finding_takes_short_answers(capsys, patient_file):
    data = as_json(negative_patient()) | {"battle_sign": "y"}
    assert run_json(capsys, "--json", patient_file(data))["triggered"] == [
        "cchr.high.basal_skull_fracture_sign"
    ]


def test_invalid_finding_flag_value_is_rejected(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["cchr", "--battle-sign", "maybe"])
    assert exit_info.value.code == 2


def test_non_numeric_value_for_numeric_flag_is_rejected(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["cchr", "--vomiting-episodes", "two"])
    assert exit_info.value.code == 2


def test_out_of_range_value_is_reported_as_error(capsys):
    code, out, err = run(capsys, "--initial-ed-gcs", "16")

    assert code == 2
    assert out == ""
    assert "initial_ed_gcs" in err


# --- JSON file ---------------------------------------------------------------


def test_json_file_with_negative_patient_does_not_require_ct(capsys, patient_file):
    path = patient_file(as_json(negative_patient()))
    result = run_json(capsys, "--json", path)

    assert result["outcome"] == "ct_not_required"
    assert result["missing_inputs"] == []


def test_field_left_out_of_json_is_unknown(capsys, patient_file):
    data = as_json(negative_patient())
    del data["battle_sign"]
    result = run_json(capsys, "--json", patient_file(data))

    assert result["outcome"] == "indeterminate"
    assert result["missing_inputs"] == ["battle_sign"]


def test_json_null_finding_is_unknown(capsys, patient_file):
    data = as_json(negative_patient()) | {"battle_sign": None}
    result = run_json(capsys, "--json", patient_file(data))

    assert result["missing_inputs"] == ["battle_sign"]


def test_flags_override_json_file(capsys, patient_file):
    path = patient_file(as_json(negative_patient()))
    result = run_json(capsys, "--json", path, "--vomiting-episodes", "3")

    assert result["triggered"] == ["cchr.high.vomiting_2_or_more"]


def test_misspelt_json_field_is_rejected(capsys, patient_file):
    data = as_json(negative_patient()) | {"batle_sign": "present"}
    code, _, err = run(capsys, "--json", patient_file(data))

    assert code == 2
    assert "batle_sign" in err


@pytest.mark.parametrize("value", [True, False, 1, "maybe"])
def test_json_finding_must_be_present_absent_or_unknown(capsys, patient_file, value):
    data = as_json(negative_patient()) | {"battle_sign": value}
    code, _, err = run(capsys, "--json", patient_file(data))

    assert code == 2
    assert "battle_sign" in err


def test_json_boolean_for_numeric_field_is_rejected(capsys, patient_file):
    data = as_json(negative_patient()) | {"vomiting_episodes": True}
    code, _, err = run(capsys, "--json", patient_file(data))

    assert code == 2
    assert "vomiting_episodes" in err


def test_json_file_that_is_not_an_object_is_rejected(capsys, patient_file):
    code, _, err = run(capsys, "--json", patient_file([1, 2]))
    assert code == 2
    assert "object" in err


def test_missing_json_file_is_reported(capsys, tmp_path):
    code, _, err = run(capsys, "--json", str(tmp_path / "nope.json"))
    assert code == 2
    assert "nope.json" in err


def test_template_lists_every_field_as_unknown(capsys):
    code, out, _ = run(capsys, "--template")

    template = json.loads(out)
    assert code == 0
    assert list(template) == ALL_FIELDS
    assert template["battle_sign"] == "unknown"
    assert template["age_years"] is None


def test_unfilled_template_is_accepted_and_indeterminate(capsys, patient_file):
    _, template, _ = run(capsys, "--template")
    result = run_json(capsys, "--json", patient_file(json.loads(template)))

    assert result["outcome"] == "indeterminate"
    assert result["missing_inputs"] == ALL_FIELDS


@pytest.mark.parametrize(
    ("rule", "example", "outcome"),
    [
        ("cchr", "minor_head_injury.json", "ct_not_required"),
        ("cchr", "on_warfarin.json", "not_applicable"),
        ("noc", "minor_head_injury.json", "ct_not_required"),
        ("noc", "on_warfarin.json", "ct_recommended"),  # age over 60
        ("pecarn", "child_vomited_once.json", "observation_or_ct"),
    ],
)
def test_readme_example_files_give_documented_outcome(capsys, rule, example, outcome):
    path = Path(__file__).parent.parent / "examples" / example
    result = run_json(capsys, "--json", str(path), rule=rule)

    assert result["rule"] == rule
    assert result["outcome"] == outcome
    assert result["missing_inputs"] == []


# --- New Orleans Criteria ----------------------------------------------------


def test_noc_gcs_14_is_not_applicable(capsys):
    result = run_json(capsys, "--initial-ed-gcs", "14", rule="noc")

    assert result["outcome"] == "not_applicable"
    assert result["exclusion_reasons"] == ["noc.inclusion.gcs_15"]


def test_one_json_file_works_for_both_rules(capsys, patient_file):
    path = patient_file(as_json(negative_patient(headache=PRESENT)))
    # headache is a New Orleans finding and is ignored by the Canadian rule.
    assert run_json(capsys, "--json", path)["outcome"] == "ct_not_required"
    assert run_json(capsys, "--json", path, rule="noc")["triggered"] == [
        "noc.finding.headache"
    ]


def test_each_rule_offers_only_its_own_flags(capsys):
    noc_help = help_text(capsys, "noc")
    cchr_help = help_text(capsys, "cchr")

    assert "--headache" in noc_help and "--battle-sign" not in noc_help
    assert "--battle-sign" in cchr_help and "--headache" not in cchr_help


def test_help_shows_each_fields_definition(capsys):
    noc_help = help_text(capsys, "noc")
    assert "anterograde" in noc_help  # short-term memory deficit
    assert "Haydel" in noc_help


def test_noc_template_lists_only_new_orleans_inputs(capsys):
    _, out, _ = run(capsys, "--template", rule="noc")
    assert list(json.loads(out)) == list(NOC_INPUTS)


def test_noc_text_output_has_its_own_title_and_no_tier(capsys):
    code, out, _ = run(capsys, "--headache", "present", rule="noc")

    assert code == 0
    assert "New Orleans Criteria (Haydel et al., N Engl J Med 2000)" in out
    assert DISCLAIMER in out
    assert "Outcome: CT recommended\n" in out


# --- Output ------------------------------------------------------------------


def test_text_output_shows_disclaimer_outcome_triggers_and_citation(capsys):
    code, out, _ = run(capsys, "--age-years", "70")

    assert code == 0
    assert DISCLAIMER in out
    assert "CT recommended (high risk)" in out
    assert "Age 65 or over" in out
    assert "Panel 1 (p1394)" in out
    assert "--battle-sign" in out  # missing inputs name the flag to supply


def test_text_output_for_excluded_patient_explains_why(capsys):
    _, out, _ = run(capsys, "--oral-anticoagulant", "present")

    assert "Rule not applicable to this patient" in out
    assert "Oral anticoagulant use" in out
    assert "no guidance" in out


def test_text_output_for_failed_inclusion_says_not_met(capsys, patient_file):
    data = as_json(negative_patient()) | {"initial_ed_gcs": 12}
    _, out, _ = run(capsys, "--json", patient_file(data))

    assert "Not met: Initial ED GCS 13-15" in out


def test_json_output_includes_disclaimer_and_full_audit(capsys):
    result = run_json(capsys, "--age-years", "70")

    assert result["disclaimer"] == DISCLAIMER
    assert len(result["criteria"]) == 20
    age = next(c for c in result["criteria"] if c["id"] == "cchr.high.age_65_or_over")
    assert age["status"] == "met"
    assert age["source"].endswith("Panel 1 (p1394)")


# --- PECARN ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("age", "outcome"), [(1, "observation_or_ct"), (5, "ct_not_required")]
)
def test_pecarn_same_fall_differs_by_age(capsys, patient_file, age, outcome):
    path = patient_file(as_json(negative_child(age, fall_height_m=1.2)))
    result = run_json(capsys, "--json", path, rule="pecarn")

    assert result["rule"] == "pecarn"
    assert result["outcome"] == outcome


def test_pecarn_text_output_names_observation_outcome(capsys, patient_file):
    path = patient_file(as_json(negative_child(5, vomiting_episodes=1)))
    code, out, _ = run(capsys, "--json", path, rule="pecarn")

    assert code == 0
    assert "PECARN (Kuppermann et al., Lancet 2009)" in out
    assert "Outcome: Observation or CT, based on other clinical factors" in out


def test_pecarn_template_lists_only_its_inputs(capsys):
    _, out, _ = run(capsys, "--template", rule="pecarn")
    assert list(json.loads(out)) == list(PECARN_INPUTS)


def test_pecarn_help_shows_its_own_flags_and_definitions(capsys):
    pecarn_help = help_text(capsys, "pecarn")

    assert "--fall-height-m" in pecarn_help and "--headache" not in pecarn_help
    assert "Kuppermann" in pecarn_help


# --- All rules at once ---------------------------------------------------------

EXAMPLES = Path(__file__).parent.parent / "examples"


def test_all_runs_every_rule_on_the_warfarin_example(capsys):
    result = run_json(capsys, "--json", str(EXAMPLES / "on_warfarin.json"), rule="all")

    assert result["disclaimer"] == DISCLAIMER
    assert {name: r["outcome"] for name, r in result["results"].items()} == {
        "cchr": "not_applicable",
        "noc": "ct_recommended",
        "pecarn": "not_applicable",
    }


def test_all_text_output_gives_one_line_per_rule_with_reason(capsys):
    code, out, _ = run(capsys, "--json", str(EXAMPLES / "on_warfarin.json"), rule="all")

    assert code == 0
    assert DISCLAIMER in out
    lines = out.splitlines()
    cchr = lines.index(next(line for line in lines if line.startswith("cchr")))
    assert "Rule not applicable" in lines[cchr]
    assert "Oral anticoagulant use" in lines[cchr + 1]
    assert any(line.startswith("noc") and "CT recommended" in line for line in lines)
    assert "Age over 60" in out
    assert "Not met: Age under 18" in out


def test_same_16_year_old_gets_a_different_outcome_from_each_rule(capsys, patient_file):
    data = as_json(negative_child(16, witnessed_loc=PRESENT))
    result = run_json(capsys, "--json", patient_file(data), rule="all")

    assert result["results"]["cchr"]["outcome"] == "ct_not_required"
    assert result["results"]["noc"]["outcome"] == "ct_not_required"
    assert result["results"]["pecarn"]["outcome"] == "observation_or_ct"


def test_all_rules_option_runs_a_subset(capsys):
    result = run_json(capsys, "--rules", "noc,pecarn", rule="all")
    assert list(result["results"]) == ["noc", "pecarn"]


def test_all_rejects_an_unknown_rule_name(capsys):
    with pytest.raises(SystemExit):
        main(["all", "--rules", "cchr,nope"])
    assert "nope" in capsys.readouterr().err


def test_all_merged_missing_inputs_name_the_rules_that_need_them(capsys):
    _, out, _ = run(capsys, "--age-years", "16", rule="all")

    line = next(line for line in out.splitlines() if "--battle-sign" in line)
    assert "cchr" in line and "pecarn" in line and "noc" not in line
    headache = next(line for line in out.splitlines() if "--headache" in line)
    assert "noc" in headache


def test_all_ignores_missing_inputs_of_rules_that_do_not_apply(capsys):
    _, out, _ = run(capsys, "--age-years", "72", rule="all")
    assert "--severe-headache" not in out  # PECARN only, and PECARN does not apply


def test_all_leaves_out_inputs_that_cannot_change_a_result(capsys):
    # Age 70 is Canadian high risk: lower-tier factors cannot change that, but
    # applicability inputs still can.
    _, out, _ = run(capsys, "--age-years", "70", "--rules", "cchr", rule="all")
    assert "--pregnant: cchr" in out
    assert "--retrograde-amnesia-minutes" not in out


def test_all_detail_adds_each_rules_full_report(capsys):
    _, out, _ = run(capsys, "--age-years", "70", "--detail", rule="all")
    for spec_title in (
        "Canadian CT Head Rule (Stiell et al., Lancet 2001)",
        "New Orleans Criteria (Haydel et al., N Engl J Med 2000)",
        "PECARN (Kuppermann et al., Lancet 2009)",
    ):
        assert spec_title in out
    assert "Panel 1 (p1394)" in out


def test_all_offers_every_field_as_a_flag(capsys):
    all_help = help_text(capsys, "all")
    for flag in ("--battle-sign", "--headache", "--fall-height-m"):
        assert flag in all_help


def test_all_template_lists_every_field_and_round_trips(capsys, patient_file):
    _, out, _ = run(capsys, "--template", rule="all")
    template = json.loads(out)
    assert list(template) == [f.name for f in dataclasses.fields(Patient)]

    result = run_json(capsys, "--json", patient_file(template), rule="all")
    assert all(r["outcome"] == "indeterminate" for r in result["results"].values())
