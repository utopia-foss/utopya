"""Tests the utopya run CLI command"""

import time

import pytest

from . import invoke_cli
from .test_models import TEST_MODEL, registry

# -----------------------------------------------------------------------------


@pytest.fixture
def delay():
    """Delays test execution by a second to avoid identical time stamps"""
    time.sleep(1)


# -----------------------------------------------------------------------------


def test_run_minimal(registry):
    """Tests a simple invocation of the utopya run command"""
    res = invoke_cli(("run", TEST_MODEL))
    print(res.output)
    print(res.exception)
    assert res.exit_code == 0


def test_eval_minimal(registry, delay):
    """Tests a simple invocation of the utopya run command"""
    res = invoke_cli(("eval", TEST_MODEL))
    print(res.output)
    print(res.exception)
    assert res.exit_code == 0


# -----------------------------------------------------------------------------
