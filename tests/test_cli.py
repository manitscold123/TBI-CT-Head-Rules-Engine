"""Command-line interface."""

import dataclasses
import json
from pathlib import Path

import pytest
from patients import negative_patient

from ct_head_rules.cchr import CCHRInput
from ct_head_rules.cli import DISCLAIMER, main
from ct_head_rules.findings import Finding

ALL_FIELDS = [f.name for f in dataclasses.fields(CCHRInput)]


def as_json(patient: CCHRInput) -> dict:
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


def run(capsys, *argv: str) -> tuple[int, str, str]:
    code = main(["cchr", *argv])
    out, err = capsys.readouterr()
    return code, out, err


def run_json(capsys, *argv: str) -> dict:
    code, out, _ = run(capsys, *argv, "--format", "json")
    assert code == 0
    return json.loads(out)


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


def test_invalid_finding_flag_value_is_rejected(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["cchr", "--battle-sign", "yes"])
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


@pytest.mark.parametrize("value", [True, False, "yes", 1])
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
    ("example", "outcome"),
    [
        ("minor_head_injury.json", "ct_not_required"),
        ("on_warfarin.json", "not_applicable"),
    ],
)
def test_readme_example_files_give_documented_outcome(capsys, example, outcome):
    path = Path(__file__).parent.parent / "examples" / example
    result = run_json(capsys, "--json", str(path))

    assert result["outcome"] == outcome
    assert result["missing_inputs"] == []


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
