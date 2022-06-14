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

    # Adjusting some of the meta config parameters, testing if they show up
    args = ("run", DUMMY_MODEL, "--no-eval", "--note", "some_note", "-d")
    res = invoke_cli(
        args + ("-N", "23", "--we", "5", "--ws", "7", "--mp", "foo.bar=ABCXYZ")
    )
    _check_result(res, expected_exit=0)

    assert "Updates to meta configuration" in res.output
    assert "ABCXYZ" in res.output


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
