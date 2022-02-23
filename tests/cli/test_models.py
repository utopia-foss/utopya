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

    # Register the test model under a new name and with multiple labels
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

    res = invoke_cli(("models", "set-default", TEST_MODEL, "set_via_cli"))
    assert res.exit_code == 0

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
    """Tests utopya models register single

    NOTE The fixture already performs some of the tests
    """
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
    reg_args += ("--label", "some_label")  # already exists
    reg_args += ("--source-dir", "./")

    res = invoke_cli(reg_args)
    print(res.output)
    assert res.exit_code != 0
    assert "Registration failed!" in res.output
    assert "Bundle validation failed" in res.output


def test_register_from_list(registry):
    """Tests utopya models register single

    NOTE The fixture already performs some of the tests
    """
    DUMMY_EXECUTABLE = os.path.join(
        DEMO_DIR, "models", DUMMY_MODEL, f"{DUMMY_MODEL}.py"
    )

    reg_args = (
        "models",
        "register",
        "from-list",
        TEST_MODEL,
        "--executables",
        DUMMY_EXECUTABLE,
    )
    res = invoke_cli(reg_args + ("--label", "some_new_label"))
    print(res.output)
    assert res.exit_code == 0
    assert "Model registration succeeded" in res.output

    # Can also use format strings
    reg_args = (
        "models",
        "register",
        "from-list",
        TEST_MODEL,
        "--executable-fstr",
        "{model_name:}/{model_name:}.py",
        "--source-dir-fstr",
        "{model_name:}/",
        "--base-executable-dir",
        os.path.join(DEMO_DIR, "models"),
        "--base-source-dir",
        os.path.join(DEMO_DIR, "models"),
    )
    res = invoke_cli(reg_args + ("--label", "yet_another_label"))
    print(res.output)
    assert res.exit_code == 0
    assert "Model registration succeeded" in res.output

    # Mutually exclusive
    res = invoke_cli(
        (
            "models",
            "register",
            "from-list",
            TEST_MODEL,
            "--executable-fstr",
            "{model_name:}/{model_name:}.py",
            "--source-dir-fstr",
            "{model_name:}/",
            "--source-dirs",
            "/foo/bar",
        )
    )
    print(res.output)
    assert res.exit_code != 0
    assert "mutually exclusive" in res.output

    # Superfluous arguments
    res = invoke_cli(reg_args + ("--executables", "'foo;bar'"))
    print(res.output)
    assert res.exit_code != 0
    assert "mutually exclusive" in res.output

    # Missing arguments
    reg_args = (
        "models",
        "register",
        "from-list",
        TEST_MODEL,
    )
    res = invoke_cli(reg_args)
    print(res.output)
    assert res.exit_code != 0
    assert "Missing argument --executables or" in res.output

    # Length mismatch
    reg_args = (
        "models",
        "register",
        "from-list",
        f"'{TEST_MODEL};{TEST_MODEL}'",
        "--executables",
        DUMMY_EXECUTABLE,
    )
    res = invoke_cli(reg_args)
    print(res.output)
    assert res.exit_code != 0
    assert "Mismatch of sequence lengths" in res.output


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

    # With custom label
    extd_reg_args = reg_args + ("--label", "custom_label")
    res = invoke_cli(extd_reg_args)
    print(res.output)
    assert res.exit_code == 0
    assert "from_manifest_file" not in res.output
    assert "custom_label" in res.output
    assert "custom_label" in registry[TEST_MODEL]

    # With custom model name
    extd_reg_args += ("--model-name", "MyCustomModelName")
    res = invoke_cli(extd_reg_args)
    print(res.output)
    assert len(registry["MyCustomModelName"]) == 1
    assert "custom_label" in registry["MyCustomModelName"]
    registry.remove_entry("MyCustomModelName")

    # Custom model name fails with more than one manifest file
    res = invoke_cli(extd_reg_args + (DUMMY_INFO,))
    print(res.output)
    assert res.exit_code != 0
    assert "can only be specified if only a single manifest file" in res.output


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


def test_set_default(registry):
    """Tests utopya models set-default"""
    assert registry[TEST_MODEL].default_label == "set_via_cli"  # see fixture

    res = invoke_cli(("models", "set-default", TEST_MODEL, "some_label"))
    print(res.output)
    assert res.exit_code == 0
    assert "some_label" in res.output
    assert registry[TEST_MODEL].default_label == "some_label"


def test_edit(monkeypatch):
    """Tests utopya models edit"""
    res = invoke_cli(("models", "edit", DUMMY_MODEL), input="y\n")
    assert res.exit_code == 1
    assert "Editing model registry file failed!" in res.output

    monkeypatch.setenv("EDITOR", "echo")  # this will always work
    res = invoke_cli(("models", "edit", DUMMY_MODEL), input="y\n")
    assert res.exit_code == 0
    assert "Successfully edited registry file" in res.output

    # Not continuing
    res = invoke_cli(("models", "edit", DUMMY_MODEL), input="N\n")
    assert res.exit_code == 0
    assert "Not opening" in res.output
