"""Tests `utopya batch` subcommand"""

import os
import shutil

import pytest

import utopya

from .. import get_cfg_fpath
from . import invoke_cli

BATCH_FILE = get_cfg_fpath("batch_file.yml")

# Fixtures --------------------------------------------------------------------
from .._fixtures import *


@pytest.fixture(autouse=True)
def register_test_project(tmp_projects):
    """Use on all tests in this module"""
    pass


# -----------------------------------------------------------------------------


def test_batch(with_test_models):  # FIXME creates test artifacts in output dir
    """Tests the `utopya batch` subcommand"""
    res = invoke_cli(("batch", "-d", "-s", "--note", "some_note", BATCH_FILE))
    print(res.output)

    # Currently, this will fail:
    assert res.exit_code != 0
    assert "Nothing to plot" in res.output
