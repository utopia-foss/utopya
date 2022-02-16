"""Tests the utopya models <...> subcommands of the CLI"""

import os

import pytest

import utopya

from .. import DEMO_DIR, DUMMY_MODEL
from . import invoke_cli

# -- Fixtures -----------------------------------------------------------------

TEST_MODEL = DUMMY_MODEL + "Test"
"""Name of the model that is used for testing the CLI"""


@pytest.fixture
def registry():
    """A fixture that prepares the model registry by adding a dummy model
    and ensuring to remove it again in the teardown of a test.
    """
    mr = utopya.MODELS

    # Register the dummy model under a new name and with multiple labels
    assert TEST_MODEL not in mr

    DUMMY_EXECUTABLE = os.path.join(
        DEMO_DIR, "models", DUMMY_MODEL, f"{DUMMY_MODEL}.py"
    )
    reg_args = (
        "models",
        "register",
        "single",
        TEST_MODEL,
        "-e",
        DUMMY_EXECUTABLE,
    )

    res = invoke_cli(reg_args)
    assert res.exit_code == 0
    assert TEST_MODEL in mr

    res = invoke_cli(reg_args + ("--label", "some_label"))
    assert res.exit_code == 0

    res = invoke_cli(reg_args + ("--label", "another_label"))
    assert res.exit_code == 0

    assert "set_via_cli" in mr[TEST_MODEL]
    assert "some_label" in mr[TEST_MODEL]
    assert "another_label" in mr[TEST_MODEL]

    yield mr

    if TEST_MODEL in mr:
        mr.remove_entry(TEST_MODEL)


# -----------------------------------------------------------------------------


def test_list():
    """Tests utopya models ls"""
    # Lists models as expected
    res = invoke_cli(("models", "ls"))
    assert "Model Registry" in res.output
    assert DUMMY_MODEL in res.output

    # Also shows the number of bundles available in "long" mode
    res = invoke_cli(("models", "ls", "--long"))
    assert "bundle(s), default:" in res.output

    assert res.output == invoke_cli(("models", "ls", "-l")).output


def test_register_single(registry):
    """Tests utopya models register single"""
    pass


def test_register_from_manifest(registry):
    """Tests utopya models register from-manifest"""

    DUMMY_INFO = os.path.join(
        DEMO_DIR, "models", DUMMY_MODEL, f"{DUMMY_MODEL}_info.yml"
    )
    reg_args = ("models", "register", "from-manifest", DUMMY_INFO)
    reg_args += ("--model-name", TEST_MODEL)

    res = invoke_cli(reg_args)
    print(res.output)
    assert res.exit_code == 0
    assert "from_manifest_file" in res.output

    reg_args += ("--label", "custom_label")
    res = invoke_cli(reg_args)
    print(res.output)
    assert res.exit_code == 0
    assert "from_manifest_file" not in res.output
    assert "custom_label" in res.output


def test_remove(registry):
    """Tests utopya models rm

    This is based on the registry fixture, which adds a bunch of entries to
    the model registry which can then be removed here.
    """
    # Remove a single label
    res = invoke_cli(("models", "rm", TEST_MODEL, "--label", "some_label"))
    assert res.exit_code == 0
    assert "set_via_cli" in registry[TEST_MODEL]
    assert "some_label" not in registry[TEST_MODEL]
    assert "another_label" in registry[TEST_MODEL]

    # ... with prompt for bundle name
    res = invoke_cli(("models", "rm", TEST_MODEL), input="another_label\n")
    assert res.exit_code == 0
    assert "set_via_cli" in registry[TEST_MODEL]
    assert "some_label" not in registry[TEST_MODEL]
    assert "another_label" not in registry[TEST_MODEL]

    # Now remove it completely
    res = invoke_cli(("models", "rm", TEST_MODEL, "--all"), input="N\n")
    print(res.output)
    assert res.exit_code == 0
    assert "Not removing anything" in res.output

    res = invoke_cli(("models", "rm", TEST_MODEL, "--all"), input="y\n")
    print(res.output)
    assert res.exit_code == 0
    assert TEST_MODEL not in registry


def test_edit():
    """Tests utopya models edit

    This will not succeed in the test context, because no editor can be opened.
    """
    res = invoke_cli(("models", "edit", DUMMY_MODEL), input="y\n")
    assert res.exit_code == 1
    assert "Editing model registry file failed!" in res.output

    # Not continuing
    res = invoke_cli(("models", "edit", DUMMY_MODEL), input="N\n")
    assert res.exit_code == 0
    assert "Not opening" in res.output
