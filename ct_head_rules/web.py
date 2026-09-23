"""Local web form. Educational use only, not for clinical use.

Standard library only. It listens on 127.0.0.1 and serves one self-contained
page plus two JSON endpoints:

- GET  /api/fields    every Patient field (type, help, rules using it)
- POST /api/evaluate  the same JSON as --json; returns every rule's result,
                      the inputs that could still change one, and the next
                      question the interview would ask. ?rules=cchr,noc limits
                      the rules.
"""

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from urllib.parse import parse_qs, urlsplit

from ct_head_rules.api import (
    ALL_INPUTS,
    DISCLAIMER,
    FIELDS,
    RULES,
    InputError,
    evaluate_all,
    outcome_text,
    parse_values,
    result_to_dict,
    summary_reason,
)
from ct_head_rules.findings import Finding
from ct_head_rules.interview import needed_inputs, next_question

HOST = "127.0.0.1"
ALLOWED_HOSTNAMES = {"127.0.0.1", "localhost"}
MAX_BODY_BYTES = 64 * 1024


def _field_type(name: str) -> str:
    field_type = FIELDS[name].type
    if field_type is Finding:
        return "finding"
    return "integer" if field_type == int | None else "number"


def fields_payload() -> dict:
    return {
        "disclaimer": DISCLAIMER,
        "rules": {
            name: {"title": spec.title, "inputs": list(spec.inputs)}
            for name, spec in RULES.items()
        },
        "fields": [
            {
                "name": name,
                "type": _field_type(name),
                "help": FIELDS[name].metadata["help"],
                "rules": [rule for rule, spec in RULES.items() if name in spec.inputs],
            }
            for name in ALL_INPUTS
        ],
    }


def evaluate_payload(values: dict, rules: tuple[str, ...]) -> dict:
    results = evaluate_all(parse_values(values), rules)
    return {
        "disclaimer": DISCLAIMER,
        "results": {
            name: result_to_dict(result)
            | {
                "title": RULES[name].title,
                "outcome_text": outcome_text(result),
                "summary": summary_reason(result),
                "triggered_detail": [
                    {"label": c.label, "source": c.source} for c in result.triggered
                ],
            }
            for name, result in results.items()
        },
        "needed": needed_inputs(results),
        "next": next_question(results, asked=set()),
    }


def _page() -> bytes:
    return resources.files("ct_head_rules").joinpath("web_page.html").read_bytes()


class Handler(BaseHTTPRequestHandler):
    server_version = "ct-head-rules"
    # Seconds a connection may sit idle, e.g. sending less than its
    # Content-Length, before the server gives up on it.
    timeout = 10

    def log_message(self, format, *args):  # keep the terminal quiet
        pass

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload).encode(), "application/json")

    def _error(self, status: int, message: str) -> None:
        self._json(status, {"error": message})

    def _host_allowed(self) -> bool:
        # Refuse other Host headers, so a web page elsewhere cannot reach this
        # server through DNS rebinding.
        hostname = urlsplit(f"//{self.headers.get('Host', '')}").hostname
        return hostname in ALLOWED_HOSTNAMES

    def do_GET(self) -> None:
        if not self._host_allowed():
            return self._error(HTTPStatus.FORBIDDEN, "unexpected Host header")
        path = urlsplit(self.path).path
        if path == "/":
            return self._send(HTTPStatus.OK, _page(), "text/html; charset=utf-8")
        if path == "/api/fields":
            return self._json(HTTPStatus.OK, fields_payload())
        self._error(HTTPStatus.NOT_FOUND, "not found")

    def do_POST(self) -> None:
        if not self._host_allowed():
            return self._error(HTTPStatus.FORBIDDEN, "unexpected Host header")
        url = urlsplit(self.path)
        if url.path != "/api/evaluate":
            return self._error(HTTPStatus.NOT_FOUND, "not found")

        length_header = self.headers.get("Content-Length", "0").strip() or "0"
        if not length_header.isdigit():
            self.close_connection = True
            return self._error(HTTPStatus.BAD_REQUEST, "invalid Content-Length")
        length = int(length_header)
        if length > MAX_BODY_BYTES:
            self.close_connection = True
            return self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "body too large")
        try:
            values = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            return self._error(HTTPStatus.BAD_REQUEST, f"not valid JSON: {error}")
        except RecursionError:
            return self._error(HTTPStatus.BAD_REQUEST, "JSON is nested too deeply")
        if not isinstance(values, dict):
            return self._error(HTTPStatus.BAD_REQUEST, "body must be a JSON object")

        rules = tuple(parse_qs(url.query).get("rules", [",".join(RULES)])[0].split(","))
        unknown = [rule for rule in rules if rule not in RULES]
        if unknown:
            return self._error(
                HTTPStatus.BAD_REQUEST, f"unknown rule(s): {', '.join(unknown)}"
            )
        try:
            payload = evaluate_payload(values, rules)
        except InputError as error:
            return self._error(HTTPStatus.BAD_REQUEST, str(error))
        self._json(HTTPStatus.OK, payload)


def make_server(port: int = 8000) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((HOST, port), Handler)


def serve(port: int = 8000) -> int:
    httpd = make_server(port)
    print(DISCLAIMER)
    print(f"Serving on http://{HOST}:{httpd.server_address[1]}/  (Ctrl-C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        httpd.server_close()
    return 0
