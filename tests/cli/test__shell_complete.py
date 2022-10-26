"""Tests shell completion features (indirectly)"""

import pytest

from utopya_cli._shared import *

from .. import ADVANCED_MODEL, DUMMY_MODEL, TEST_PROJECT_NAME
from .._fixtures import *
from . import invoke_cli
from .test_run_and_eval import _check_result


class MockContext:
    def __init__(self, **kwargs):
        for key, val in kwargs.items():
            setattr(self, key, val)


# -----------------------------------------------------------------------------


def test_complete_model_names(with_test_models):
    """Tests auto-completion of model names"""
    ctx = None
    param = None
    complete = complete_model_names

    assert DUMMY_MODEL in complete(ctx, param, "")
    assert ADVANCED_MODEL in complete(ctx, param, "")

    # With a (long enough) incomplete string, will reduce the list
    incomplete = ADVANCED_MODEL[:5]
    assert complete(ctx, param, incomplete) == [ADVANCED_MODEL]


def test_complete_project_names(with_test_models):
    """Tests auto-completion of project names"""
    ctx = None
    param = None
    complete = complete_project_names

    assert TEST_PROJECT_NAME in complete(ctx, param, "")

    # With a (long enough) incomplete string, will reduce the list
    incomplete = TEST_PROJECT_NAME[:10]
    assert complete(ctx, param, incomplete) == [TEST_PROJECT_NAME]


def test_complete_run_dirs(with_test_models, tmp_output_dir):
    """Tests auto-completion of model names"""
    ctx = MockContext(params=dict(model_name="invalid model name"))
    param = None
    complete = complete_run_dirs

    # Should be empty for invalid model names
    assert not complete(ctx, param, "")

    # Now use a valid model name to generate some output
    # Need to make some runs first to have some output
    res = invoke_cli(("run", DUMMY_MODEL, "-d"))
    _check_result(res, expected_exit=0)

    res = invoke_cli(
        ("run", DUMMY_MODEL, "--no-eval", "--note", "some_note", "-d")
    )
    _check_result(res, expected_exit=0)

    # Now check if there are completed directories available
    # NOTE Need to set `extra_search_dirs` because otherwise would create side
    #      effects from the test or miss the temporary directory
    ctx = MockContext(params=dict(model_name=DUMMY_MODEL))
    c1 = complete(ctx, None, "")
    c2 = complete(ctx, None, "", extra_search_dirs=[str(tmp_output_dir)])
    assert len(c1) <= len(c2)

    # Check that the latest run directory is part of the suggestions.
    # Need to (tediously) parse the CLI output to get to the run directory.
    IGNORE = ("eval", ".h5", ".yml")
    run_dir = [
        line.strip()
        for line in res.output.split("\n")
        if "_some_note" in line and not any(s in line for s in IGNORE)
    ][0]
    # assert os.path.basename(run_dir) not in c1 # FIXME test has wrong out_dir
    assert os.path.basename(run_dir) in c2
