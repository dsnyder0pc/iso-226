# CLAUDE.md — `tests/`

Working notes for the test suite. Loaded when Claude works with files under
`tests/`; the repository-wide notes are in the root `CLAUDE.md`. How to *run*
the suite is in `CONTRIBUTING.md`.

- **`tests/test_api.py`** — the HTTP service, through Flask's test client: no
  server, no port, no gunicorn, 0.3 s for the file. Flask is deliberately absent
  from the repository's `requirements.txt` (only `web/requirements.txt` has it),
  so the `api` fixture in `conftest.py` uses `importorskip` — a contributor
  working on the maths must not have to install a web framework. The two
  contracts worth the most are the uniform two-key response shape and that every
  level the API suggests can actually be served.
  - Live responses are also validated against the schemas in `openapi.yaml`.
    OpenAPI 3.1 schemas **are** JSON Schema 2020-12, so they are used directly
    rather than translated. The spec is registered with `referencing` under
    `SPEC_URI` and each response schema is reached by JSON pointer into that
    document — not lifted out as a value, because a bare `{"$ref": "#/..."}`
    resolves against itself and finds nothing, and because refs *inside* a
    lifted schema would lose the document they were written in.
    `test_the_schemas_are_strict_enough_to_reject_a_broken_response` breaks a
    real response two ways and requires the schema to notice; without it a
    permissive schema would make the whole group pass vacuously.
  - `jsonschema>=4.18` is in the root `requirements.txt` as a **test**
    dependency (4.18 is where the `referencing` registry arrived). It must
    never reach `web/requirements.txt`.

- **`tests/test_iso226.py`** — the math. `test_matches_published_annex_b` and
  the shelf-property tests are the ones that matter: they are the only checks
  not sharing code with the thing under test. The shelf tests caught a sign
  error in the RBJ high-shelf `b2` coefficient that had shipped since the first
  version and that `check.py` could never have detected.

- **`tests/test_generator.py`** — the generator plus the file formats that
  couple the two scripts. The Markdown/YAML round-trip tests are the ones most
  likely to earn their keep: `check.py` matches filter-type strings and table
  columns *positionally*, and nothing else notices when one side of that
  contract changes.
