"""Tests the utopya run CLI command"""

import time

import pytest

from . import invoke_cli
from .test_models import TEST_MODEL, registry, tmp_output_dir

# -----------------------------------------------------------------------------


@pytest.fixture
def delay():
    """Delays test execution by a second to avoid identical time stamps"""
    time.sleep(1)


# -----------------------------------------------------------------------------


@pytest.mark.skip("Needs working plots config")
def test_run(registry, tmp_output_dir):
    """Tests the invocation of the utopya run command"""
    # Simplest case
    res = invoke_cli(("run", TEST_MODEL, "-d"))
    print(res.output)
    assert res.exit_code == 0

    # Adjusting some of the meta config parameters
    args = ("run", TEST_MODEL, "--no-eval", "--note", "some_note", "-d")
    res = invoke_cli(
        args + ("-N", "23", "--we", "5", "--ws", "7", "--mp", "foo.bar=spam")
    )
    print(res.output)
    assert res.exit_code == 0
    assert "spam" in res.output


@pytest.mark.skip("Needs working plots config")
def test_eval(registry, tmp_output_dir, delay):
    """Tests the invocation of the utopya eval command"""
    # Simplest case
    res = invoke_cli(("eval", TEST_MODEL, "-d"))
    print(res.output)
    assert res.exit_code == 0

    time.sleep(1)

    # Adjusting some of the meta config parameters
    args = ("eval", TEST_MODEL, "-d")
    res = invoke_cli(args + ("-p", "plot_manager.raise_exc=true"))
    print(res.output)
    assert res.exit_code == 0
    assert "Updates to meta configuration" in res.output
