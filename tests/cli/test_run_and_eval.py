"""Tests the utopya run CLI command"""

import logging
import time
import traceback

import pytest

from .. import ADVANCED_MODEL, DUMMY_MODEL
from .._fixtures import *
from . import invoke_cli


def _check_result(res, expected_exit: int = 0):
    if res.exception:
        print(res.output)
        traceback.print_tb(res.exception.__traceback__)

    elif res.exit_code != expected_exit:
        print(res.output)

    assert res.exit_code == expected_exit


# -----------------------------------------------------------------------------


def test_run(with_test_models, tmp_output_dir):
    """Tests the invocation of the utopya run command"""
    # Simplest case with the dummy model
    res = invoke_cli(("run", DUMMY_MODEL, "-d"))
    _check_result(res, expected_exit=0)
    assert not "Now creating plots" in res.output  # evaluation not attempted

    # Again, but with the advanced model
    res = invoke_cli(("run", ADVANCED_MODEL, "-d"))
    _check_result(res, expected_exit=0)

    # ... and with higher debug level
    res = invoke_cli(("run", ADVANCED_MODEL, "-dd"))
    _check_result(res, expected_exit=0)

    # Adjusting some of the meta config parameters, testing if they show up
    args = ("run", DUMMY_MODEL, "--no-eval", "--note", "some_note", "-d")
    res = invoke_cli(
        args
        + (
            "-N",
            "23",
            "--we",
            "5",
            "--ws",
            "7",
            "--mp",
            "foo.bar=ABCXYZ",
            "-W",
            "1",
        )
    )
    _check_result(res, expected_exit=0)

    assert "Updates to meta configuration" in res.output
    assert "ABCXYZ" in res.output


def test_run_existing(with_test_models, tmp_output_dir):
    """Tests the invocation of the utopya run_exisitng command"""

    # Simplest case with the dummy model
    res_prep = invoke_cli(
        (
            "run",
            DUMMY_MODEL,
            "-d",
            "--num-seeds",
            "4",
            "--no-work",
            "--no-eval",
        )
    )
    _check_result(res_prep, expected_exit=0)
    assert "Finished working." in res_prep.output

    # search output for run directory
    __find = res_prep.output.find(tmp_output_dir)
    __end = __find + res_prep.output[__find:].find("\n")
    run_dir = res_prep.output[__find:__end]

    assert os.path.isdir(run_dir)
    assert os.path.isdir(os.path.join(run_dir, "config"))
    assert os.path.isdir(os.path.join(run_dir, "data"))
    for uni in range(1, 5):
        assert os.path.isdir(os.path.join(run_dir, "data", f"uni{uni}"))
        assert not os.path.isfile(
            os.path.join(run_dir, "data", f"uni{uni}", "data.h5")
        )
        assert not os.path.isfile(
            os.path.join(run_dir, "data", f"uni{uni}", "out.log")
        )
    assert os.path.isdir(os.path.join(run_dir, "eval"))

    res = invoke_cli(("run-existing", DUMMY_MODEL, run_dir, "--uni", "uni1"))
    _check_result(res, expected_exit=0)
    assert "uni1" in res.output
    assert not "Now creating plots" in res.output  # evaluation not attempted

    res_fail_repeat = invoke_cli(
        ("run-existing", DUMMY_MODEL, run_dir, "--uni", "uni1")
    )
    _check_result(res_fail_repeat, expected_exit=1)
    # Repeat failed

    res = invoke_cli(
        (
            "run-existing",
            DUMMY_MODEL,
            run_dir,
            "--uni",
            "uni2",
            "--uni",
            "uni3",
        )
    )
    _check_result(res, expected_exit=0)
    assert run_dir in res.output
    assert not "Now creating plots" in res.output  # evaluation not attempted

    # Check that data exists
    for uni in range(1, 4):
        assert os.path.isfile(
            os.path.join(run_dir, "data", f"uni{uni}", "data.h5")
        )
        assert os.path.isfile(
            os.path.join(run_dir, "data", f"uni{uni}", "out.log")
        )

    # Check that uni4 never was run
    assert not os.path.isfile(os.path.join(run_dir, "data", "uni4", "data.h5"))
    assert not os.path.isfile(os.path.join(run_dir, "data", "uni4", "out.log"))


def test_eval(with_test_models, tmp_output_dir, delay):
    """Tests the invocation of the utopya eval command"""
    # Simplest case
    res = invoke_cli(("eval", ADVANCED_MODEL, "-d"))
    _check_result(res, expected_exit=0)

    time.sleep(1)

    # Adjusting some of the meta config parameters
    args = ("eval", ADVANCED_MODEL, "-d")
    res = invoke_cli(args + ("-p", "plot_manager.raise_exc=true"))
    _check_result(res, expected_exit=0)
    assert "Updates to meta configuration" in res.output
