"""Equal-loudness compensation filter API.

Serves the precomputed preset grid built by ``precompute_presets.py``. The
fitting itself takes 20-45 s per preset and never runs here: this process is a
dictionary lookup, so it needs neither NumPy nor SciPy and starts in
milliseconds on a one-core box.

Liberal in what it accepts -- unknown query parameters are ignored, numbers may
be written any reasonable way, and levels are snapped to the nearest grid
point. Rigorous in what it emits -- every response, including every error and
every unhandled exception, is well-formed JSON with the same top-level shape.

    GET /v1/filters?level=65[&reference=83][&scale=1.0]
    GET /v1/meta
    GET /health
"""

import json
import os
import re

from flask import Flask, jsonify, request

API_VERSION = "1"

# A deliberately strict grammar for a deliberately liberal parser: accept the
# ways a human or a form might reasonably write a level, and nothing else. No
# exponents, no infinities, no unicode digits, nothing that reaches float()
# without having been looked at first.
_NUMBER_RE = re.compile(r"^[+-]?(?:\d{1,4}(?:\.\d{1,4})?|\.\d{1,4})$")

DEFAULT_REFERENCE_DB = 83.0
DEFAULT_SCALE = 1.0

# Everything else in the query string is ignored, by design.
KNOWN_PARAMS = ("level", "reference", "scale")

# Guard rails on the *input* before it is snapped to the grid. Wider than the
# grid itself so that an in-range-but-unsatisfiable request gets a specific
# explanation rather than a generic range error.
LEVEL_BOUNDS = (20.0, 120.0)
REFERENCE_BOUNDS = (50.0, 100.0)
SCALE_BOUNDS = (0.1, 1.0)

_HERE = os.path.dirname(os.path.abspath(__file__))
PRESETS_PATH = os.environ.get("PRESETS_PATH", os.path.join(_HERE, "presets.json"))


def load_presets(path=PRESETS_PATH):
    """Read the precomputed grid. Fails loudly at import: a running API with no
    data is worse than one that refuses to start."""
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


DATA = load_presets()
PRESETS = DATA["presets"]
OFFSET_MIN, OFFSET_MAX = DATA["offset_range_db"]
AVAILABLE_SCALES = [round(s, 2) for s in DATA["scales"]]
MAX_AVAILABLE_SCALE = max(AVAILABLE_SCALES)

# The grid is fitted wider than it can serve: the deepest offsets are fitted,
# refused by check_budget and stored as refusals. A client building a level
# control needs the range that actually works, not the range that was attempted.
_SERVABLE = sorted(e["offset"] for e in PRESETS.values() if not e["refused"])
SERVABLE_MIN, SERVABLE_MAX = _SERVABLE[0], _SERVABLE[-1]

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


# --- Response shaping -------------------------------------------------------

def _source_block():
    return {
        "api_version": API_VERSION,
        "iso_edition": DATA["iso_edition"],
        "generated_utc": DATA["generated_utc"],
    }


def _received():
    """The parameters we understand, as the caller sent them.

    Read from the request rather than threaded through every caller: it is the
    same derived value at every error site, and passing it around was the only
    reason this module had a six-argument function.
    """
    return {k: v for k, v in request.args.items() if k in KNOWN_PARAMS}


def _error(code, message, http_status, parameter=None, suggestions=None):
    """Every failure leaves by this door, in the same shape as a success."""
    error = {"code": code, "message": message}
    if parameter is not None:
        error["parameter"] = parameter
    if suggestions:
        error["suggestions"] = suggestions
    payload = {
        "status": {
            "ok": False,
            "error": error,
            "received": _received(),
            "source": _source_block(),
        },
        "filters": [],
    }
    return jsonify(payload), http_status


# --- Parameter handling -----------------------------------------------------

def _number(raw, name, bounds):
    """Validate one numeric query parameter. Returns (value, None) or
    (None, error_response)."""
    text = raw.strip()
    if not _NUMBER_RE.match(text):
        return None, _error(
            "invalid_parameter",
            f"'{name}' must be a decimal number, for example 65 or 65.5.",
            400, parameter=name)
    value = float(text)
    low, high = bounds
    if not low <= value <= high:
        return None, _error(
            "out_of_range",
            f"'{name}' must be between {low:g} and {high:g} dB.",
            422, parameter=name)
    return value, None


def _refusal_message(reason, level, reference):
    """Restate why the fit was refused, using the caller's own numbers.

    The stored reason names the nominal levels the grid point was fitted at,
    which are not the levels this caller asked about whenever they supplied
    their own reference. Keep the substance -- the part after the colon, which
    is the actual budget that was exceeded -- and re-attach their request.
    """
    substance = reason.splitlines()[0].split(":", 1)[-1].strip()
    return (f"Cannot build a usable filter set for level={level:g}, "
            f"reference={reference:g}: {substance}")


def _api_suggestions(reason, reference):
    """Restate the generator's advice in this API's own terms.

    check_budget writes for the command line -- "--scale 0.85", "--level 62".
    Echoing that verbatim would hand a caller flags that are not query
    parameters, and would recommend 'scale' while v1 rejects it. Translate, and
    drop any suggestion this version cannot honour.
    """
    out = []
    for line in reason.splitlines():
        line = line.strip()
        match = re.match(r"^--scale\s+([\d.]+)", line)
        if match and round(float(match.group(1)), 2) in AVAILABLE_SCALES:
            out.append(f"scale={float(match.group(1)):g}"
                       " for partial compensation.")
        match = re.match(r"^--level\s+([\d.]+)", line)
        if match:
            # The generator's suggestion is expressed against the nominal
            # reference the grid was fitted at. Shift it onto the caller's
            # reference, or a request using their own reference gets told to
            # aim at a level from a different curve entirely.
            offset = float(match.group(1)) - DATA["nominal_reference_db"]
            out.append(f"level={reference + offset:g}"
                       " — target a higher listening level.")
        if line.startswith("--reference"):
            out.append(f"A lower 'reference' than {reference:g},"
                       " if this recording is mastered quieter.")
    return out


def _snap_scale(scale):
    """Nearest grid scale. The grid is 0.1 apart; taste does not need finer."""
    return round(round(scale / 0.1) * 0.1, 2)


def _parse(args):
    """Pull the parameters we know about and ignore everything else."""
    if "level" not in args:
        return None, _error(
            "missing_parameter",
            "'level' is required: the measured listening level in dB SPL "
            "(broadband, C-weighted, slow).",
            400, parameter="level")

    level, err = _number(args["level"], "level", LEVEL_BOUNDS)
    if err:
        return None, err

    reference = DEFAULT_REFERENCE_DB
    if "reference" in args:
        reference, err = _number(args["reference"], "reference",
                                 REFERENCE_BOUNDS)
        if err:
            return None, err

    scale = DEFAULT_SCALE
    if "scale" in args:
        scale, err = _number(args["scale"], "scale", SCALE_BOUNDS)
        if err:
            return None, err

    return (level, reference, scale), None


# --- Routes -----------------------------------------------------------------

@app.route("/v1/filters", methods=["GET"])
def filters():
    """Return the filter set for one (level, reference, scale) request."""
    parsed, err = _parse(request.args)
    if err:
        return err
    level, reference, scale = parsed

    offset = int(round(level - reference))
    snapped_scale = _snap_scale(scale)
    notes = []

    if abs((level - reference) - offset) > 1e-9:
        notes.append(
            f"Offset rounded to the nearest 1 dB grid point ({offset:+d} dB).")
    if abs(snapped_scale - scale) > 1e-9:
        notes.append(f"Scale rounded to the nearest 0.1 ({snapped_scale:g}).")
    if reference != DATA["nominal_reference_db"]:
        notes.append(
            f"Fitted at a {DATA['nominal_reference_db']:g} dB reference. The "
            f"curve depends on level minus reference, which matches yours to "
            f"within {DATA['equivalence_tolerance_db']} dB over references "
            f"72-85 dB.")

    if not OFFSET_MIN <= offset <= OFFSET_MAX:
        return _error(
            "offset_unavailable",
            f"level - reference is {offset:+d} dB, outside the "
            f"{OFFSET_MIN:+d}..{OFFSET_MAX:+d} dB range this service covers.",
            422,
            suggestions=[f"Choose a level between "
                         f"{reference + OFFSET_MIN:g} and "
                         f"{reference + OFFSET_MAX:g} dB for this reference."])

    # Partial compensation is a v2 feature: the grid ships full compensation
    # only. Reject rather than silently serve a curve the caller did not ask
    # for -- being liberal about *form* must not extend to changing meaning.
    if snapped_scale not in AVAILABLE_SCALES:
        return _error(
            "scale_unavailable",
            f"Only full compensation (scale {MAX_AVAILABLE_SCALE:g}) is "
            f"available in API version {API_VERSION}.",
            422, parameter="scale",
            suggestions=[f"Omit 'scale', or pass "
                         f"scale={MAX_AVAILABLE_SCALE:g}."])

    entry = PRESETS.get(f"{offset:+d}|{snapped_scale:.2f}")
    if entry is None:
        return _error("preset_unavailable",
                      "No preset exists for that combination.",
                      422)

    if entry["refused"]:
        return _error("correction_exceeds_budget",
                      _refusal_message(entry["reason"], level, reference), 422,
                      suggestions=_api_suggestions(entry["reason"], reference))

    return jsonify({
        "status": {
            "ok": True,
            "request": {"level": level, "reference": reference, "scale": scale},
            "resolved": {"offset_db": offset, "scale": snapped_scale},
            "preset": {
                "band_count": DATA["band_count"],
                "design_fs": DATA["design_fs"],
                "headroom_db": entry["headroom_db"],
                "max_residual_db": entry["max_residual_db"],
                "target_met": entry["target_met"],
            },
            "source": _source_block(),
            "notes": notes,
        },
        "filters": entry["filters"],
    })


@app.route("/v1/meta", methods=["GET"])
def meta():
    """What this service can serve, without asking for a preset."""
    return jsonify({
        "status": {"ok": True, "source": _source_block()},
        "coverage": {
            "offset_range_db": [SERVABLE_MIN, SERVABLE_MAX],
            "offset_step_db": 1,
            "scales_available": AVAILABLE_SCALES,
            "nominal_reference_db": DATA["nominal_reference_db"],
            "equivalence_tolerance_db": DATA["equivalence_tolerance_db"],
            "band_count": DATA["band_count"],
            "design_fs": DATA["design_fs"],
            "preset_count": len(PRESETS),
        },
        "filters": [],
    })


@app.route("/health", methods=["GET"])
def health():
    """Liveness probe."""
    return jsonify({"status": {"ok": True, "presets": len(PRESETS)},
                    "filters": []})


# --- Error handlers: no HTML ever leaves this process -----------------------

@app.errorhandler(404)
def _not_found(_exc):
    return _error("not_found",
                  "Unknown endpoint. Try GET /v1/filters?level=65.", 404)


@app.errorhandler(405)
def _method_not_allowed(_exc):
    return _error("method_not_allowed", "This endpoint accepts GET only.", 405)


@app.errorhandler(Exception)
def _unhandled(exc):
    app.logger.exception("unhandled error", exc_info=exc)
    return _error("internal_error",
                  "The service failed to handle that request.", 500)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
