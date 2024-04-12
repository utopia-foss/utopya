"""Tests the utopya run CLI command"""

import logging
import os
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
    """Tests the invocation of the utopya run_existing command"""

    # Run the dummy model with --no-work flag
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

    # check that all folders exist
    assert os.path.isdir(run_dir)
    assert os.path.isdir(os.path.join(run_dir, "config"))
    assert os.path.isdir(os.path.join(run_dir, "data"))
    assert os.path.isdir(os.path.join(run_dir, "eval"))

    # check that every universe output directory has a config
    # but no data and log
    for uni in range(1, 5):
        assert os.path.isdir(os.path.join(run_dir, "data", f"uni{uni}"))
        assert not os.path.isfile(
            os.path.join(run_dir, "data", f"uni{uni}", "data.h5")
        )
        assert not os.path.isfile(
            os.path.join(run_dir, "data", f"uni{uni}", "out.log")
        )

    # Repeat uni1 with run-existing
    res = invoke_cli(("run-existing", DUMMY_MODEL, run_dir, "--uni", "uni1"))
    _check_result(res, expected_exit=0)
    assert "uni1" in res.output
    assert "Now creating plots" not in res.output  # evaluation not attempted

    # Check that cannot be repeated again as data already exists
    res_fail_repeat = invoke_cli(
        ("run-existing", DUMMY_MODEL, run_dir, "--uni", "uni1")
    )
    _check_result(res_fail_repeat, expected_exit=1)

    # Repeat with uni2 and uni3
    res = invoke_cli(
        (
            "run-existing",
            DUMMY_MODEL,
            run_dir,
            "--uni",
            "uni2",
            "-u",
            "uni3",
        )
    )
    _check_result(res, expected_exit=0)
    assert run_dir in res.output
    assert "Now creating plots" not in res.output  # evaluation not attempted

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

    # Repeat uni1 with clear existing option
    bad_file_path = os.path.join(
        run_dir, "data", "uni1", "this_file_should_not_exist.txt"
    )
    bad_file = open(bad_file_path, "a")
    bad_file.write("New line of text")
    bad_file.close()

    res = invoke_cli(
        (
            "run-existing",
            DUMMY_MODEL,
            run_dir,
            "--uni",
            "uni1",
            "--clear-existing",
        )
    )
    _check_result(res, expected_exit=0)
    assert "uni1" in res.output
    assert "Now creating plots" not in res.output  # evaluation not attempted

    assert not os.path.isfile(
        os.path.join(run_dir, "data", "uni1", "this_file_should_not_exist.txt")
    )

    # Run all but skip existing
    res = invoke_cli(
        (
            "run-existing",
            DUMMY_MODEL,
            run_dir,
            "--skip-existing",
        )
    )
    _check_result(res, expected_exit=0)

    # Check that uni4 was run
    assert "Finished working. Total tasks worked on: 1" in res.output
    assert os.path.isfile(os.path.join(run_dir, "data", "uni4", "data.h5"))
    assert os.path.isfile(os.path.join(run_dir, "data", "uni4", "out.log"))

    # Re-run all with clear existing option
    res = invoke_cli(
        (
            "run-existing",
            DUMMY_MODEL,
            run_dir,
            "--clear-existing",
        )
    )
    _check_result(res, expected_exit=0)

    assert "Finished working. Total tasks worked on: 4" in res.output


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
