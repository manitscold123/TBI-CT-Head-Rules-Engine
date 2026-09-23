"""The patient record shared by all rules."""

import dataclasses

import pytest

from ct_head_rules.findings import Finding
from ct_head_rules.patient import Patient


def test_every_field_defaults_to_unknown():
    patient = Patient()
    for field in dataclasses.fields(Patient):
        value = getattr(patient, field.name)
        assert value is None or value is Finding.UNKNOWN, field.name


def test_only_known_findings_need_to_be_given():
    patient = Patient(age_years=70, headache=Finding.PRESENT)

    assert patient.age_years == 70
    assert patient.headache is Finding.PRESENT
    assert patient.battle_sign is Finding.UNKNOWN


def test_fields_must_be_passed_by_name():
    with pytest.raises(TypeError):
        Patient(70)


def test_every_field_documents_its_definition_and_source():
    for field in dataclasses.fields(Patient):
        help_text = field.metadata.get("help", "")
        assert any(
            paper in help_text for paper in ("Stiell", "Haydel", "Kuppermann")
        ), field.name


NUMBER_FIELDS = [f.name for f in dataclasses.fields(Patient) if f.type is not Finding]


@pytest.mark.parametrize("name", NUMBER_FIELDS)
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_numbers_are_rejected(name, value):
    # NaN compares false with everything, so it would act as a negative.
    with pytest.raises(ValueError, match=name):
        Patient(**{name: value})
