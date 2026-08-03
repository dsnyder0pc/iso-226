"""Shared fixtures.

``loudness-filters.py`` is hyphenated so that the documented CLI invocation
reads naturally, which means it cannot be imported by name. Load it once per
session rather than repeating the importlib dance in every test.
"""

import importlib.util
import os
import sys

import numpy as np
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

# The repo root must be on sys.path before the project modules import.
# pylint: disable=wrong-import-position
from iso226_utils import Compensation  # noqa: E402


def pytest_configure(config):
    """Register the markers this suite uses."""
    config.addinivalue_line(
        "markers",
        "slow: runs the optimizer (~30 s each); deselect with -m 'not slow'",
    )


@pytest.fixture(scope="session")
def annex_b_40_phon():
    """The 40 phon contour of ISO 226:2023 Annex B, Table B.1.

    These values belong to ISO and are not redistributable, so they live in
    `reference/annex_b_2023.py`, which is gitignored. Anyone holding a copy of
    the standard can populate it from `tests/annex_b_reference.py.example`;
    without it the one test that uses it skips and everything else still runs.
    """
    path = os.path.join(REPO_ROOT, "reference", "annex_b_2023.py")
    if not os.path.exists(path):
        pytest.skip(
            "reference/annex_b_2023.py not present. This fixture holds contour "
            "values from ISO 226:2023 Annex B, which are not redistributable. "
            "See tests/annex_b_reference.py.example to supply them from your "
            "own copy of the standard."
        )
    spec = importlib.util.spec_from_file_location("annex_b_2023", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    values = getattr(module, "ANNEX_B_40_PHON", None)
    if not values:
        pytest.skip("reference/annex_b_2023.py is present but not populated.")
    return np.array(values, dtype=float)


@pytest.fixture(scope="session")
def lf():
    """The filter generator module."""
    spec = importlib.util.spec_from_file_location(
        "loudness_filters", os.path.join(REPO_ROOT, "loudness-filters.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Requesting one fixture from another necessarily shadows its name; that is the
# pytest idiom, not an accident.
# pylint: disable=redefined-outer-name
@pytest.fixture(scope="session")
def preset(lf):
    """One real generated filter set, shared by every slow test.

    Generating a preset takes ~30 s, so the integration tests assert many
    properties of a single run rather than paying that cost repeatedly.
    """
    return lf.calculate_filters(Compensation(65.0, 83.0))
