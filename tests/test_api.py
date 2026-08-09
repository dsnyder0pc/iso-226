"""
Tests for the HTTP API in web/.

These run against Flask's test client, so they need no server, no port and no
gunicorn -- but they exercise the same code a request would. They skip whole
if Flask is absent, because the generator does not require it.

Two contracts are worth more than the rest and are why this file exists:

* **Every response has the same two top-level keys**, success or failure. A
  consumer that has to branch on shape before it can read an error is a
  consumer that will not read the error.
* **Every level this API suggests is one it can actually serve.** The grid is
  fitted wider than it can serve -- the deepest offsets are fitted, refused by
  check_budget and stored as refusals -- so a message quoting the fitted range
  sends callers to levels that then fail. The CLI holds itself to the same rule
  in test_suggestions_actually_fit_the_budget.
"""

import json
import os
import re

import pytest
import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC_PATH = os.path.join(REPO_ROOT, "web", "openapi.yaml")

with open(SPEC_PATH, encoding="utf-8") as _handle:
    SPEC = yaml.safe_load(_handle)


def _body(response):
    """The parsed JSON body, asserting the framing every response shares.

    `status` and `filters` are always present -- an endpoint may add to that
    (`/v1/meta` carries `coverage`), but never omit either, because a consumer
    reads `filters` before it knows which endpoint answered.
    """
    assert response.mimetype == "application/json", (
        f"{response.status_code} response was {response.mimetype}; "
        f"no HTML may ever leave this service")
    payload = json.loads(response.data)
    assert {"status", "filters"} <= set(payload), (
        f"top-level keys {sorted(payload)}, expected status and filters")
    assert isinstance(payload["filters"], list)
    assert isinstance(payload["status"]["ok"], bool)
    return payload


# --- The shape contract -----------------------------------------------------

@pytest.mark.parametrize("path,status", [
    ("/health", 200),
    ("/v1/meta", 200),
    ("/v1/filters?level=65", 200),
    ("/v1/filters?level=83", 200),
    ("/v1/filters", 400),
    ("/v1/filters?level=abc", 400),
    ("/v1/filters?level=1e3", 400),
    ("/v1/filters?level=200", 422),
    ("/v1/filters?level=30", 422),
    ("/v1/filters?level=59", 422),
    ("/v1/filters?level=65&scale=0.5", 422),
    ("/v1/nope", 404),
])
def test_every_response_is_json_in_the_same_shape(client, path, status):
    """One shape for success and failure alike, at every documented status."""
    response = client.get(path)
    assert response.status_code == status, response.data
    payload = _body(response)
    assert payload["status"]["ok"] is (status == 200)
    if status != 200:
        assert payload["filters"] == []
        assert set(payload["status"]["error"]) >= {"code", "message"}


def test_wrong_method_is_json_not_html(client):
    """Werkzeug's own 405 page is HTML; ours must not be."""
    response = client.post("/v1/filters?level=65")
    assert response.status_code == 405
    assert _body(response)["status"]["error"]["code"] == "method_not_allowed"


def test_an_unhandled_framework_error_keeps_its_status(client):
    """A client mistake must not be reported as a server fault.

    Werkzeug rejects an over-long URI itself, before any route runs. Without
    the HTTPException handler the catch-all would turn that 414 into a 500.
    """
    response = client.get("/v1/filters?level=65&pad=" + "x" * 20000)
    assert response.status_code in (200, 414, 431), response.status_code
    _body(response)


# --- Suggestions must be actionable -----------------------------------------

def test_the_advertised_range_is_the_one_that_works(client):
    """The offset range in an error must match the one /v1/meta publishes.

    The grid holds fitted-but-refused entries below the servable floor, so
    these two numbers can differ without anything looking wrong locally.
    """
    served = _body(client.get("/v1/meta"))["coverage"]["offset_range_db"]
    message = _body(client.get("/v1/filters?level=30"))["status"]["error"]["message"]
    low, high = re.search(r"([+-]\d+)\.\.([+-]\d+) dB range", message).groups()
    assert [int(low), int(high)] == served, (
        f"the error advertises {low}..{high} but /v1/meta serves {served}")


def test_every_suggested_level_can_actually_be_served(client):
    """Follow the advice the API gives and it must work.

    Both wordings are checked: the range suggestion on offset_unavailable, and
    the translated 'level=NN' advice on correction_exceeds_budget.
    """
    checked = 0
    for query, reference in (("level=30", 83.0), ("level=59", 83.0),
                             ("level=45&reference=75", 75.0)):
        error = _body(client.get(f"/v1/filters?{query}"))["status"]["error"]
        for suggestion in error.get("suggestions", []):
            levels = [float(value) for pair in
                      re.findall(r"between ([\d.]+) and ([\d.]+) dB", suggestion)
                      for value in pair]
            levels += [float(value)
                       for value in re.findall(r"level=([\d.]+)", suggestion)]
            for level in levels:
                followed = client.get(
                    f"/v1/filters?level={level:g}&reference={reference:g}")
                assert followed.status_code == 200, (
                    f"{query} suggested {suggestion!r}, but level={level:g} "
                    f"returns {followed.status_code}")
                checked += 1
    assert checked >= 3, "expected the suggestion wordings to be exercised"


def test_a_refusal_explains_itself_in_the_callers_own_numbers(client):
    """The stored reason names the grid's nominal levels, not the caller's."""
    error = _body(client.get(
        "/v1/filters?level=51&reference=75"))["status"]["error"]
    assert error["code"] == "correction_exceeds_budget"
    assert "level=51" in error["message"] and "reference=75" in error["message"]
    assert "83" not in error["message"].split(":")[0]


# --- Lookup behaviour -------------------------------------------------------

def test_the_curve_follows_the_offset_not_the_levels(client):
    """Equal offsets must return identical filters, whatever the references."""
    a = _body(client.get("/v1/filters?level=65&reference=83"))
    b = _body(client.get("/v1/filters?level=57&reference=75"))
    assert a["filters"] == b["filters"]
    assert b["status"]["notes"], "a non-nominal reference should say so"


def test_off_grid_requests_are_snapped_and_say_so(client):
    """Rounding is allowed; doing it silently is not."""
    payload = _body(client.get("/v1/filters?level=65.4"))
    assert payload["status"]["resolved"]["offset_db"] == -18
    assert any("rounded" in note.lower() for note in payload["status"]["notes"])


def test_unknown_parameters_are_ignored(client):
    """Liberal in what it accepts -- but only about form."""
    plain = _body(client.get("/v1/filters?level=65"))
    noisy = _body(client.get("/v1/filters?level=65&hifi=yes&utm_source=x"))
    assert plain["filters"] == noisy["filters"]
    assert plain["status"]["request"] == noisy["status"]["request"]


def test_partial_compensation_is_refused_rather_than_reinterpreted(client):
    """Serving full compensation for a scale request would change the meaning."""
    payload = _body(client.get("/v1/filters?level=65&scale=0.5"))
    assert payload["status"]["error"]["code"] == "scale_unavailable"


def test_the_reference_level_returns_no_filters_and_says_why(client):
    """Listening at the mastering level needs nothing applied."""
    payload = _body(client.get("/v1/filters?level=83"))
    assert payload["filters"] == []
    assert payload["status"]["preset"]["headroom_db"] == 0.0
    assert any("nothing to correct" in note for note in payload["status"]["notes"])


def test_headroom_is_never_positive(client):
    """It is applied as negative preamp; a positive figure would clip."""
    for offset in range(-23, 8):
        payload = _body(client.get(f"/v1/filters?level={83 + offset}"))
        assert payload["status"]["preset"]["headroom_db"] <= 0.0


def test_the_bypass_preamp_is_negative_and_near_the_headroom(client):
    """Both halves of that matter, and the second one is the interesting half.

    It is a preamp like any other, so it cannot ask for boost. And it is the
    headroom plus the cascade's gain at 500 Hz, which the gain ceiling keeps
    small -- 1.2 dB at the deepest rung and under half a decibel over most of
    the ladder. The bound below is loose enough to allow that and tight enough
    to catch a return to broadband loudness weighting, which asked for 2.4 dB
    at 83->75 and 7.6 dB at 83->60. See the bypass invariant in CLAUDE.md for
    what that cost the first time.
    """
    for offset in range(-23, 8):
        preset = _body(client.get(f"/v1/filters?level={83 + offset}"))["status"]["preset"]
        bypass = preset["bypass_headroom_db"]
        assert bypass <= 0.0
        assert abs(bypass - preset["headroom_db"]) <= 2.0, (
            f"offset {offset:+d}: bypass {bypass} against headroom "
            f"{preset['headroom_db']}")


def test_the_whole_servable_range_is_actually_servable(client):
    """/v1/meta is a promise; this keeps it one."""
    low, high = _body(client.get("/v1/meta"))["coverage"]["offset_range_db"]
    for offset in range(low, high + 1):
        response = client.get(f"/v1/filters?level={83 + offset}")
        assert response.status_code == 200, (
            f"offset {offset:+d} is advertised but returns "
            f"{response.status_code}")


# --- Nothing may leave that the declared schema would reject ----------------
#
# The tests above check the cases the spec writes down. These check the rule
# behind them: whatever the service answers, for whichever endpoint and status,
# must validate against the schema the spec declares for exactly that pair.
# OpenAPI 3.1 schemas are JSON Schema 2020-12, so they can be used directly --
# no translation, and therefore nothing to get wrong in the translation.

# (url, path template, status). The path template is how the response is looked
# up in the spec; the url is what actually gets requested.
SCHEMA_PROBES = [
    ("/health", "/health", 200),
    ("/v1/meta", "/v1/meta", 200),
    ("/v1/filters?level=65", "/v1/filters", 200),
    ("/v1/filters?level=83", "/v1/filters", 200),
    ("/v1/filters?level=65.4&reference=78", "/v1/filters", 200),
    ("/v1/filters?level=89", "/v1/filters", 200),
    ("/v1/filters", "/v1/filters", 400),
    ("/v1/filters?level=abc", "/v1/filters", 400),
    ("/v1/filters?level=200", "/v1/filters", 422),
    ("/v1/filters?level=30", "/v1/filters", 422),
    ("/v1/filters?level=59", "/v1/filters", 422),
    ("/v1/filters?level=65&scale=0.5", "/v1/filters", 422),
]


# The spec is not published at a URL, but $ref resolution needs a base to
# resolve against, so the document is registered under one. Anything stable
# does; .invalid is reserved by RFC 2606 and can never resolve for real.
SPEC_URI = "https://openapi.iso-226.invalid/openapi.yaml"


def _schema_ref(path, status):
    """A pointer to the schema the spec declares for one endpoint and status.

    Referred to by pointer rather than lifted out as a value, so that whether
    the spec writes the schema inline (`/health`) or as a `$ref` to components
    (everything else) makes no difference here, and so the refs *inside* it
    still resolve against the document they were written in.
    """
    responses = SPEC["paths"][path]["get"]["responses"]
    key = str(status) if str(status) in responses else "default"
    pointer = (f"/paths/{path.replace('~', '~0').replace('/', '~1')}"
               f"/get/responses/{key}/content/application~1json/schema")
    return {"$ref": f"{SPEC_URI}#{pointer}"}


def _validator(schema):
    """A validator for one schema, with the spec's own $refs resolvable.

    Imported through importorskip so this file still runs without the library,
    the way it already does without Flask.
    """
    jsonschema = pytest.importorskip("jsonschema")
    referencing = pytest.importorskip("referencing")
    resource = referencing.Resource.from_contents(
        SPEC, default_specification=referencing.jsonschema.DRAFT202012)
    registry = referencing.Registry().with_resource(SPEC_URI, resource)
    return jsonschema.Draft202012Validator(schema, registry=registry)


@pytest.mark.parametrize("url,path,status", SCHEMA_PROBES,
                         ids=[f"{p[2]} {p[0]}" for p in SCHEMA_PROBES])
def test_live_responses_validate_against_the_declared_schema(client, url, path,
                                                             status):
    """A response the spec's own schema rejects is a broken promise.

    Stronger than comparing the documented examples: those cover the cases
    someone thought to write down, this covers the shape of everything.
    """
    response = client.get(url)
    assert response.status_code == status, response.data
    errors = sorted(_validator(_schema_ref(path, status))
                    .iter_errors(json.loads(response.data)),
                    key=lambda err: list(err.absolute_path))
    assert not errors, "\n".join(
        f"{'/'.join(str(part) for part in err.absolute_path) or '<root>'}: "
        f"{err.message}" for err in errors)


def test_the_schemas_are_strict_enough_to_reject_a_broken_response(client):
    """A schema that accepts anything would make the test above meaningless.

    Rather than trusting that, break a real response in the two ways that
    matter -- a missing required field and a wrong type -- and require the
    schema to notice.
    """
    validator = _validator(_schema_ref("/v1/filters", 200))
    payload = json.loads(client.get("/v1/filters?level=65").data)
    assert validator.is_valid(payload), "the unmodified response must validate"

    missing = json.loads(json.dumps(payload))
    del missing["filters"][0]["gain"]
    assert not validator.is_valid(missing), (
        "the schema does not require a filter to carry its gain")

    wrong_type = json.loads(json.dumps(payload))
    wrong_type["filters"][0]["frequency"] = "sixty-six point seven"
    assert not validator.is_valid(wrong_type), (
        "the schema does not require a frequency to be a number")


# --- The spec must describe this service, not a previous one ----------------

def _example_url(path, value):
    """The request an example describes, reconstructed from the example.

    `status.request` on a success, `status.received` on an error -- which is
    the caller's input echoed back, so it is exactly what produced it.
    """
    params = value["status"].get("request") \
        or value["status"].get("received") or {}
    query = "&".join(f"{key}={val:g}" if isinstance(val, (int, float))
                     else f"{key}={val}" for key, val in params.items())
    return f"{path}?{query}" if query else path


def _spec_examples():
    """(id, url, status, example) for every response example in the spec."""
    out = []
    for path, methods in SPEC["paths"].items():
        for method, operation in methods.items():
            for status, response in operation.get("responses", {}).items():
                content = response.get("content", {}).get("application/json", {})
                for name, example in content.get("examples", {}).items():
                    out.append((f"{method.upper()} {path} {status} {name}",
                                _example_url(path, example["value"]),
                                int(status), example["value"]))
    return out


SPEC_EXAMPLES = _spec_examples()


@pytest.mark.parametrize("url,status,example",
                         [e[1:] for e in SPEC_EXAMPLES],
                         ids=[e[0] for e in SPEC_EXAMPLES])
def test_documented_examples_match_live_responses(client, url, status, example):
    """The spec is handed to front-end authors and code generators.

    An example that no longer matches is worse than no example: it is read as
    a promise. Everything is compared except `generated_utc`, which changes
    whenever the grid is rebuilt.
    """
    response = client.get(url)
    assert response.status_code == status, response.data
    live = _body(response)

    assert live["filters"] == example["filters"]
    if "coverage" in example:
        assert live["coverage"] == example["coverage"]
    if status == 200 and "preset" in example["status"]:
        assert live["status"]["preset"] == example["status"]["preset"]
        assert live["status"]["resolved"] == example["status"]["resolved"]
    if "error" in example["status"]:
        assert live["status"]["error"] == example["status"]["error"]
    assert live["status"]["source"]["iso_edition"] == \
        example["status"]["source"]["iso_edition"]


def test_the_spec_publishes_the_range_the_service_serves(client):
    """coverage.offset_range_db is the one number a client builds a UI from."""
    documented = SPEC["components"]["schemas"]["MetaResponse"]["properties"] \
        ["coverage"]["properties"]["offset_range_db"]["examples"][0]
    served = _body(client.get("/v1/meta"))["coverage"]["offset_range_db"]
    assert documented == served
