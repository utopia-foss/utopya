"""Tests the utopya run CLI command"""

from . import invoke_cli
from .test_models import TEST_MODEL, registry

# -----------------------------------------------------------------------------


def test_minimal(registry):
    """Tests a simple invocation of the utopya run command"""
    res = invoke_cli(("run", TEST_MODEL))
    print(res.output)
    print(res.exception)
    assert res.exit_code == 0
