"""Tests the utopya.batch module"""

import builtins
import contextlib
import copy
import os
import platform

import pytest

from utopya.batch import BatchTaskManager
from utopya.model import Model
from utopya.tools import load_yml, recursive_update

from . import ADVANCED_MODEL, DUMMY_MODEL, get_cfg_fpath
from ._fixtures import *

BATCH_FILE_PATH = get_cfg_fpath("batch_file.yml")
BATCH_CFG = load_yml(get_cfg_fpath("batch.yml"))

# -----------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def with_models(with_test_models):
    """Use on all tests in this module"""
    pass


skip_if_on_macOS = pytest.mark.skipif(
    (
        platform.system() == "Darwin"
        and not os.environ.get("OBJC_DISABLE_INITIALIZE_FORK_SAFETY")
    ),
    reason="Fails on macOS without OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES",
)


# -----------------------------------------------------------------------------


def test_BatchTaskManager_basics(tmp_projects):
    """Tests BatchTaskManager"""
    # Make sure the required models have some output generated
    for model_name in (DUMMY_MODEL,):
        Model(name=model_name).create_mv(
            paths=dict(model_note="btm-basics")
        ).run()

    # Can't use a relative output directory
    with pytest.raises(ValueError, match="needs to be absolute"):
        BatchTaskManager(debug=True, paths=dict(out_dir="not/an/abs/path"))

    # Can test other basics here ...
    # ...


@skip_if_on_macOS
def test_BatchTaskManager(tmpdir):
    """Tests BatchTaskManager"""
    # Make sure the required models have some output generated
    for model_name in (ADVANCED_MODEL,):
        Model(name=model_name).create_mv(paths=dict(model_note="btm")).run()

    # Test multiple scenarios
    for test_case, test_cfg in copy.deepcopy(BATCH_CFG).items():
        print(f"Testing case '{test_case}' ...")

        # Use temporary directory for batch output
        test_cfg = recursive_update(
            test_cfg,
            dict(
                paths=dict(
                    out_dir=str(tmpdir.join(test_case)),
                    note=test_case,
                )
            ),
        )

        # Error handling
        _raises = test_cfg.pop("_raises", None)
        _match = test_cfg.pop("_match", None)

        if _raises:
            ctx = pytest.raises(getattr(builtins, _raises), match=_match)
        else:
            ctx = contextlib.nullcontext()

        with ctx:
            btm = BatchTaskManager(debug=True, **test_cfg)
            btm.perform_tasks()


@skip_if_on_macOS
def test_batch_file():
    """Tests the BatchTaskManager via a batch file"""
    # Make sure the required models have some output generated
    for model_name in (ADVANCED_MODEL,):
        Model(name=model_name).create_mv(
            paths=dict(model_note="batch-file")
        ).run()

    # Set up the BatchTaskManager
    btm = BatchTaskManager(batch_cfg_path=BATCH_FILE_PATH, debug=True)

    # Check some default values
    assert "BatchTaskManager" in str(btm)
    assert btm.debug
    assert btm.parallelization_level == "batch"

    # And now perform all tasks
    btm.perform_tasks()
