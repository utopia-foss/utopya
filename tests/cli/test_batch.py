"""Tests `utopya batch` subcommand"""

import os
import shutil

import pytest

import utopya

from .. import get_cfg_fpath
from . import invoke_cli

BATCH_FILE: str = get_cfg_fpath("batch_file.yml")
"""Path to a test batch file"""

# -- Fixtures -----------------------------------------------------------------
from .._fixtures import *
from ..test_batch import skip_if_on_macOS


@pytest.fixture(autouse=True)
def register_test_project(tmp_projects):
    """Use on all tests in this module"""
    pass


# -----------------------------------------------------------------------------


@skip_if_on_macOS
def test_batch(with_test_models):  # FIXME creates test artifacts in output dir
    """Tests the `utopya batch` subcommand"""
    # Make sure the ExtendedModel has already run
    model = utopya.Model(name="ExtendedModel")
    mv = model.create_mv()
    mv.run()

    # Now actually perform the batch eval
    res = invoke_cli(("batch", "-d", "-s", "--note", "some_note", BATCH_FILE))
    print(res.output)

    assert res.exit_code == 0
    assert "time_series/mean_state" in res.output
