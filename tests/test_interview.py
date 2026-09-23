"""Guided interview: ask only what could still change a rule's outcome."""

import builtins
import json

import pytest
from patients import PRESENT, UNKNOWN, negative_child, negative_patient

from ct_head_rules.api import evaluate_all, parse_values, patient_to_values
from ct_head_rules.cchr import CCHR_INPUTS
from ct_head_rules.cli import main
from ct_head_rules.interview import interview, is_settled, next_question
from ct_head_rules.noc import NOC_INPUTS
from ct_head_rules.patient import Patient
from ct_head_rules.pecarn import PECARN_INPUTS, evaluate_pecarn
from ct_head_rules.rules import Outcome, RiskLevel

PECARN_ONLY = set(PECARN_INPUTS) - set(CCHR_INPUTS) - set(NOC_INPUTS)
ALL_RULES = ("cchr", "noc", "pecarn")


def answers_for(patient: Patient) -> dict[str, str]:
    """What a user would type to describe this patient."""
    return {
        name: "" if value is None else str(value)
        for name, value in patient_to_values(patient).items()
    }


class Script:
    """Types answers by field name; a list gives successive answers to one
    question. Anything else is left blank, i.e. unknown."""

    def __init__(self, answers: dict | None = None):
        self.answers = {
            name: list(answer) if isinstance(answer, list) else [answer]
            for name, answer in (answers or {}).items()
        }
        self.asked: list[str] = []
        self.said: list[str] = []

    def ask(self, name: str, prompt: str) -> str:
        self.asked.append(name)
        queue = self.answers.get(name, [])
        return queue.pop(0) if len(queue) > 1 else (queue[0] if queue else "")

    def say(self, text: str) -> None:
        self.said.append(text)


def run(script: Script, rules=ALL_RULES, values=None) -> dict:
    return interview(dict(values or {}), rules, script.ask, script.say)


# --- Which question comes next ---------------------------------------------------


def test_first_question_is_age():
    assert next_question(evaluate_all(Patient()), asked=set()) == "age_years"


def test_questions_already_asked_are_skipped():
    assert next_question(evaluate_all(Patient()), asked={"age_years"}) != "age_years"


def test_applicability_inputs_come_before_risk_factors():
    script = Script()
    run(script, rules=("cchr",))

    risk = script.asked.index("vomiting_episodes")
    for gate in (
        "blunt_head_trauma",
        "initial_ed_gcs",
        "hours_since_injury",
        "pregnant",
    ):
        assert script.asked.index(gate) < risk


def test_rule_that_stops_applying_stops_asking_its_inputs():
    script = Script({"age_years": "72"})
    run(script)

    assert script.asked[0] == "age_years"
    assert not PECARN_ONLY & set(script.asked)


def test_each_question_is_asked_once():
    script = Script()
    run(script)
    assert len(script.asked) == len(set(script.asked))


# --- When to stop ----------------------------------------------------------------


def test_stops_once_every_rule_is_settled():
    # Age 70 is high risk, so only applicability can still change the outcome:
    # the other risk factors are never asked.
    script = Script(answers_for(negative_patient(age_years=70)))
    values = run(script, rules=("cchr",))

    assert evaluate_all(parse_values(values), ("cchr",))["cchr"].outcome is (
        Outcome.CT_RECOMMENDED
    )
    assert "vomiting_episodes" not in script.asked
    assert "battle_sign" not in script.asked


def test_negative_adult_ends_with_ct_not_required_from_adult_rules():
    values = run(Script(answers_for(negative_patient())))

    results = evaluate_all(parse_values(values))
    assert results["cchr"].outcome is Outcome.CT_NOT_REQUIRED
    assert results["noc"].outcome is Outcome.CT_NOT_REQUIRED
    assert results["pecarn"].outcome is Outcome.NOT_APPLICABLE


def test_unknown_answers_never_give_ct_not_required():
    values = run(Script())

    results = evaluate_all(parse_values(values))
    assert all(r.outcome is Outcome.INDETERMINATE for r in results.values())


def test_ct_recommended_is_not_settled_while_applicability_is_unknown():
    result = evaluate_all(Patient(age_years=70))["cchr"]
    assert result.outcome is Outcome.CT_RECOMMENDED
    assert not is_settled(result)


def test_medium_risk_is_not_settled_while_a_high_risk_input_is_unknown():
    known = evaluate_all(negative_patient(retrograde_amnesia_minutes=45))["cchr"]
    unknown_high = evaluate_all(
        negative_patient(retrograde_amnesia_minutes=45, vomiting_episodes=None)
    )["cchr"]

    assert known.risk_level is RiskLevel.MEDIUM and is_settled(known)
    assert unknown_high.risk_level is RiskLevel.MEDIUM and not is_settled(unknown_high)


def test_pecarn_observation_is_open_while_a_ct_predictor_is_unknown():
    known = evaluate_pecarn(negative_child(5, vomiting_episodes=1))
    unknown_ct = evaluate_pecarn(
        negative_child(5, vomiting_episodes=1, other_altered_mental_status=UNKNOWN)
    )

    assert is_settled(known)
    assert unknown_ct.outcome is Outcome.OBSERVATION_OR_CT
    assert not is_settled(unknown_ct)


# --- Answers ---------------------------------------------------------------------


def test_short_answers_and_blank_for_unknown():
    values = run(
        Script(
            {
                "age_years": "30",
                "blunt_head_trauma": "y",
                "witnessed_loc": "n",
                "definite_amnesia": "",
            }
        ),
        rules=("cchr",),
    )

    assert values["age_years"] == 30
    assert values["blunt_head_trauma"] == "present"
    assert values["witnessed_loc"] == "absent"
    assert values["definite_amnesia"] == "unknown"


def test_invalid_answer_is_asked_again_with_the_reason():
    script = Script({"age_years": ["abc", "30"]})
    values = run(script)

    assert script.asked[:2] == ["age_years", "age_years"]
    assert values["age_years"] == 30
    assert any("number" in text for text in script.said)


def test_out_of_range_answer_is_asked_again_with_the_reason():
    script = Script({"age_years": "30", "initial_ed_gcs": ["16", "15"]})
    values = run(script, rules=("cchr",))

    assert script.asked.count("initial_ed_gcs") == 2
    assert values["initial_ed_gcs"] == 15
    assert any("GCS" in text for text in script.said)


def test_q_finishes_early():
    script = Script({"age_years": "30", "blunt_head_trauma": "q"})
    assert run(script) == {"age_years": 30}


def test_known_values_given_up_front_are_not_asked_again():
    script = Script()
    run(script, values={"age_years": 30, "initial_ed_gcs": 15})

    assert "age_years" not in script.asked
    assert "initial_ed_gcs" not in script.asked


# --- CLI -------------------------------------------------------------------------


@pytest.fixture
def typed(monkeypatch):
    """Answer `input()` prompts by field name; the prompt starts 'name: '."""

    def feed(answers: dict[str, str]) -> None:
        def fake_input(prompt: str = "") -> str:
            name = prompt.strip().split(":", 1)[0]
            if name not in answers:
                return ""
            answer = answers[name]
            if answer is None:
                raise EOFError
            return answer

        monkeypatch.setattr(builtins, "input", fake_input)

    return feed


def test_ask_prints_disclaimer_and_summary(capsys, typed):
    typed({"age_years": "72", "blunt_head_trauma": "q"})
    code = main(["ask"])
    out = capsys.readouterr().out

    assert code == 0
    assert "NOT for clinical use" in out
    assert "Not met: Age under 18" in out


def test_ask_end_of_input_finishes_like_q(capsys, typed):
    typed({"age_years": "72", "blunt_head_trauma": None})
    assert main(["ask"]) == 0
    assert "Not met: Age under 18" in capsys.readouterr().out


def test_ask_save_reloads_to_the_same_results(capsys, typed, tmp_path):
    saved = tmp_path / "answers.json"
    typed(answers_for(negative_patient(headache=PRESENT)))
    assert main(["ask", "--save", str(saved)]) == 0
    capsys.readouterr()

    assert json.loads(saved.read_text())["headache"] == "present"
    main(["all", "--json", str(saved), "--format", "json"])
    reloaded = json.loads(capsys.readouterr().out)["results"]
    assert reloaded["cchr"]["outcome"] == "ct_not_required"
    assert reloaded["noc"]["outcome"] == "ct_recommended"
    assert reloaded["pecarn"]["outcome"] == "not_applicable"


def test_ask_starts_from_a_json_file(capsys, typed, tmp_path):
    start = tmp_path / "start.json"
    start.write_text(json.dumps({"age_years": 72, "oral_anticoagulant": "present"}))
    typed({})

    assert main(["ask", "--json", str(start), "--rules", "cchr"]) == 0
    assert "Oral anticoagulant use" in capsys.readouterr().out


@pytest.mark.parametrize("answer", ["nan", "inf"])
def test_non_finite_answer_is_asked_again(answer):
    script = Script({"age_years": "1", "fall_height_m": [answer, "0"]})
    values = run(script, rules=("pecarn",))

    assert script.asked.count("fall_height_m") == 2
    assert values["fall_height_m"] == 0


def test_huge_number_answer_is_asked_again():
    script = Script({"age_years": "30", "vomiting_episodes": ["1" + "0" * 400, "0"]})
    values = run(script, rules=("noc",))
    assert values["vomiting_episodes"] == 0
