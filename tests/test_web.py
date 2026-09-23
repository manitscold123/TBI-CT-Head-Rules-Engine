"""Local web form: one page and two JSON endpoints, served on localhost only."""

import dataclasses
import http.client
import json
import threading
from pathlib import Path

import pytest
from patients import PRESENT, negative_patient

from ct_head_rules.api import (
    DISCLAIMER,
    RULES,
    evaluate_all,
    parse_values,
    patient_to_values,
    result_to_dict,
)
from ct_head_rules.cli import build_parser
from ct_head_rules.patient import Patient
from ct_head_rules.web import MAX_BODY_BYTES, make_server

EXAMPLES = Path(__file__).parent.parent / "examples"


@pytest.fixture(scope="module")
def server():
    httpd = make_server(port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()


def request(server, method, path, body=None, headers=None):
    host, port = server.server_address[:2]
    connection = http.client.HTTPConnection(host, port, timeout=5)
    if isinstance(body, dict | list):
        body = json.dumps(body)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    data = response.read()
    connection.close()
    return response, data


def evaluate(server, values):
    response, data = request(server, "POST", "/api/evaluate", values)
    return response.status, json.loads(data)


# --- The page -------------------------------------------------------------------


def test_page_is_html_with_the_disclaimer(server):
    response, data = request(server, "GET", "/")
    page = data.decode()

    assert response.status == 200
    assert response.getheader("Content-Type").startswith("text/html")
    assert DISCLAIMER in page


def test_page_is_self_contained(server):
    page = request(server, "GET", "/")[1].decode()
    assert "<script src" not in page
    assert "<link" not in page
    assert "https://" not in page and "http://" not in page


def test_unknown_path_is_404(server):
    assert request(server, "GET", "/nope")[0].status == 404


def test_server_listens_on_localhost_only(server):
    assert server.server_address[0] == "127.0.0.1"


def test_request_for_another_host_is_refused(server):
    response, _ = request(server, "GET", "/", headers={"Host": "evil.example"})
    assert response.status == 403


# --- Field list -----------------------------------------------------------------


def test_fields_lists_every_patient_field_with_type_and_help(server):
    response, data = request(server, "GET", "/api/fields")
    body = json.loads(data)

    assert response.status == 200
    assert body["disclaimer"] == DISCLAIMER
    names = [f["name"] for f in body["fields"]]
    assert names == [f.name for f in dataclasses.fields(Patient)]
    by_name = {f["name"]: f for f in body["fields"]}
    assert by_name["battle_sign"]["type"] == "finding"
    assert by_name["age_years"]["type"] == "integer"
    assert by_name["fall_height_m"]["type"] == "number"
    assert "Kuppermann" in by_name["fall_height_m"]["help"]
    assert by_name["battle_sign"]["rules"] == ["cchr", "pecarn"]


def test_fields_lists_each_rules_title_and_inputs(server):
    body = json.loads(request(server, "GET", "/api/fields")[1])
    for name, spec in RULES.items():
        assert body["rules"][name]["title"] == spec.title
        assert body["rules"][name]["inputs"] == list(spec.inputs)


# --- Evaluation -----------------------------------------------------------------


def test_results_match_the_engine_exactly(server):
    values = json.loads((EXAMPLES / "on_warfarin.json").read_text())
    status, body = evaluate(server, values)

    assert status == 200
    assert body["disclaimer"] == DISCLAIMER
    expected = evaluate_all(parse_values(values))
    for name, result in expected.items():
        got = body["results"][name]
        assert {k: got[k] for k in result_to_dict(result)} == result_to_dict(result)


def test_results_carry_short_text_for_the_cards(server):
    values = json.loads((EXAMPLES / "on_warfarin.json").read_text())
    body = evaluate(server, values)[1]["results"]

    assert body["cchr"]["title"] == RULES["cchr"].title
    assert body["cchr"]["outcome_text"] == "Rule not applicable to this patient"
    assert body["cchr"]["summary"] == "Oral anticoagulant use"
    assert body["noc"]["summary"] == "Age over 60"


def test_empty_patient_is_indeterminate_and_age_is_asked_first(server):
    status, body = evaluate(server, {})

    assert status == 200
    assert all(r["outcome"] == "indeterminate" for r in body["results"].values())
    assert body["next"] == "age_years"
    assert body["needed"]["age_years"] == ["cchr", "noc", "pecarn"]


def test_nothing_needed_once_every_rule_is_settled(server):
    values = patient_to_values(negative_patient(headache=PRESENT))
    body = evaluate(server, values)[1]

    assert body["results"]["noc"]["outcome"] == "ct_recommended"
    assert body["needed"] == {}
    assert body["next"] is None


def test_short_answers_are_accepted(server):
    status, body = evaluate(server, {"oral_anticoagulant": "y"})
    assert status == 200
    assert body["results"]["cchr"]["outcome"] == "not_applicable"


def test_rules_can_be_limited(server):
    response, data = request(server, "POST", "/api/evaluate?rules=noc,pecarn", {})
    assert list(json.loads(data)["results"]) == ["noc", "pecarn"]


@pytest.mark.parametrize(
    ("body", "fragment"),
    [
        ({"batle_sign": "present"}, "batle_sign"),
        ({"initial_ed_gcs": 16}, "GCS"),
        ({"battle_sign": True}, "battle_sign"),
        ([1, 2], "object"),
        ("{not json", "JSON"),
    ],
)
def test_bad_input_is_400_with_the_reason(server, body, fragment):
    response, data = request(server, "POST", "/api/evaluate", body)
    assert response.status == 400
    assert fragment in json.loads(data)["error"]


def test_unknown_rule_is_400(server):
    response, data = request(server, "POST", "/api/evaluate?rules=nope", {})
    assert response.status == 400
    assert "nope" in json.loads(data)["error"]


def test_oversized_body_is_refused(server):
    body = json.dumps({"age_years": 30}) + " " * MAX_BODY_BYTES
    response, _ = request(server, "POST", "/api/evaluate", body)
    assert response.status == 413


# --- CLI ------------------------------------------------------------------------


def test_serve_command_takes_a_port():
    args = build_parser().parse_args(["serve", "--port", "8123"])
    assert args.rule == "serve" and args.port == 8123


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numbers_are_400(server, literal):
    body = f'{{"age_years": 1, "fall_height_m": {literal}}}'
    response, data = request(server, "POST", "/api/evaluate", body)
    assert response.status == 400
    assert "fall_height_m" in json.loads(data)["error"]


# --- Fuzzing ------------------------------------------------------------------------

ODD_VALUES = [None, True, False, 0, -1, 2.5, 10**30, "", "present", "y", "NaN",
              "é", [], {}, [1], {"a": 1}, "15", 1e308]  # fmt: skip
ODD_KEYS = ["", "__proto__", "age_years ", "AGE_YEARS", "é", "0"]
ODD_BODIES = [b"", b"null", b"[]", b'"x"', b"{", b"\xff\xfe", b"{}" * 5,
              b'{"age_years": 1e400}', b'{"age_years": -0.0}',
              b'{"a": ' * 3000]  # fmt: skip


def random_body(rng) -> bytes:
    from ct_head_rules.api import ALL_INPUTS

    body = {}
    for _ in range(rng.randint(0, 6)):
        key = rng.choice([*ALL_INPUTS, *ODD_KEYS]) if rng.random() < 0.9 else "x"
        body[key] = rng.choice(ODD_VALUES)
    return json.dumps(body).encode()


def test_random_bodies_never_cause_a_server_error(server):
    import random

    rng = random.Random(20260923)
    bodies = ODD_BODIES + [random_body(rng) for _ in range(300)]
    for body in bodies:
        response, data = request(server, "POST", "/api/evaluate", body)
        assert response.status in (200, 400), (body[:80], response.status, data[:200])
        json.loads(data)  # always a JSON reply


@pytest.mark.parametrize("length", ["abc", "-5", "1.5", ""])
def test_bad_content_length_is_400(server, length):
    host, port = server.server_address[:2]
    connection = http.client.HTTPConnection(host, port, timeout=5)
    connection.putrequest("POST", "/api/evaluate")
    connection.putheader("Content-Length", length)
    connection.endheaders(b"{}")
    response = connection.getresponse()
    response.read()
    connection.close()
    assert response.status == 400 if length else response.status in (200, 400)


def test_body_shorter_than_its_content_length_does_not_hold_the_server(server):
    import socket

    from ct_head_rules.web import Handler

    assert Handler.timeout and Handler.timeout <= 30
    host, port = server.server_address[:2]
    with socket.create_connection((host, port), timeout=5) as sock:
        sock.sendall(
            b"POST /api/evaluate HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Content-Length: 100\r\n\r\n{}"
        )
        # Meanwhile the server still answers other requests.
        assert request(server, "GET", "/api/fields")[0].status == 200


@pytest.mark.parametrize(
    "body",
    [
        b'{"vomiting_episodes": 1' + b"0" * 400 + b"}",
        b'{"age_years": 1' + b"0" * 5000 + b"}",
    ],
)
def test_huge_numbers_are_400(server, body):
    response, _ = request(server, "POST", "/api/evaluate", body)
    assert response.status == 400


def test_non_ascii_digit_content_length_is_400(server):
    import socket

    host, port = server.server_address[:2]
    with socket.create_connection((host, port), timeout=5) as sock:
        sock.sendall(
            b"POST /api/evaluate HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Content-Length: \xb2\r\n\r\n{}"
        )
        assert sock.recv(64).startswith(b"HTTP/1.0 400")


def test_cross_site_simple_post_is_refused(server):
    # A page elsewhere can send text/plain without a CORS preflight.
    response, _ = request(
        server, "POST", "/api/evaluate", b"{}", {"Content-Type": "text/plain"}
    )
    assert response.status == 415
