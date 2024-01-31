"""Tests the utopya test <...> subcommand of the CLI"""

import os
import sys

import pytest

from .._fixtures import *
from . import invoke_cli

# -----------------------------------------------------------------------------


# FIXME for whatever strange reason, this creates side effects in
#       eval/test_plotting.py::test_preloading
#       Removing "model_plots" from sys.modules here does not resolve it.
@pytest.mark.order("last")
def test_test(with_test_models):
    """Tests `utopya test`"""
    # No tests available for dummy model
    res = invoke_cli(("test", DUMMY_MODEL))
    print(res.output)
    assert res.exit_code == 0
    assert DUMMY_MODEL in res.output
    assert "No tests defined for this model" in res.output
    assert "test summary" not in res.output

    res2 = invoke_cli(("test", DUMMY_MODEL, "-xv"))
    assert res2.output == res.output

    # It does work for the advanced model
    res = invoke_cli(("test", ADVANCED_MODEL))
    print(res.output)
    assert res.exit_code == 0
    assert ADVANCED_MODEL in res.output
    assert "Full test command" in res.output
    assert "pytest" in res.output
    assert "test session starts" in res.output
    assert "collected 1 item" in res.output
    assert "test session starts" in res.output
    assert "1 passed" in res.output

    # Can also pass a label
    res = invoke_cli(("test", ADVANCED_MODEL, "--label", TEST_LABEL))
    print(res.output)
    assert res.exit_code == 0
    assert ADVANCED_MODEL in res.output
    assert "test session starts" in res.output

    # And further arguments
    res = invoke_cli(("test", ADVANCED_MODEL, "-x", "-v", "."))
    print(res.output)
    assert res.exit_code == 0
    assert ADVANCED_MODEL in res.output
    assert "pytest -x -v ." in res.output
    assert "test session starts" in res.output

    res = invoke_cli(("test", ADVANCED_MODEL, "-xv", "test_cfg_sets.py"))
    print(res.output)
    assert res.exit_code == 0
    assert ADVANCED_MODEL in res.output
    assert "pytest -xv test_cfg_sets.py" in res.output
    assert "test session starts" in res.output

    # May pass arguments that lead to zero tests being discovered
    res = invoke_cli(("test", ADVANCED_MODEL, "-xv", "test_foo.py"))
    print(res.output)
    assert res.exit_code == 4  # usage error
    assert "collected 0 items" in res.output
    assert "test session starts" in res.output
    assert "no tests ran" in res.output
    assert "file or directory not found" in res.output
