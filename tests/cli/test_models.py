"""Tests the utopya models <...> subcommands of the CLI"""

import os
import traceback

import pytest

import utopya

from .._fixtures import *
from . import invoke_cli

# -----------------------------------------------------------------------------


def test_list(with_test_models):
    """Tests utopya models ls"""
    # Lists models as expected
    res = invoke_cli(("models", "ls"))
    assert "model registry" in res.output
    assert DUMMY_MODEL in res.output

    # Also shows the number of bundles available in "long" mode
    res = invoke_cli(("models", "ls", "--long"))
    assert "bundle" in res.output
    assert "Default bundles are marked" in res.output
    assert "(*)" in res.output

    assert res.output == invoke_cli(("models", "ls", "-l")).output


def test_register_single(registry):
    """Tests utopya models register single"""
    reg_args = (
        "models",
        "register",
        "single",
        DUMMY_MODEL,
        "-e",
        DUMMY_EXECUTABLE,
    )
    reg_args += ("--label", TEST_LABEL)  # already exists
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
    reg_args = (
        "models",
        "register",
        "from-list",
        DUMMY_MODEL,
        "--executables",
        DUMMY_EXECUTABLE,
    )
    res = invoke_cli(reg_args + ("--label", "some_new_label"))
    print(res.output)
    if res.exception:
        traceback.print_tb(res.exception.__traceback__)
    assert res.exit_code == 0
    assert "Model registration succeeded" in res.output

    # Can also use format strings
    reg_args = (
        "models",
        "register",
        "from-list",
        DUMMY_MODEL,
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
            DUMMY_MODEL,
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
        DUMMY_MODEL,
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
        f"'{DUMMY_MODEL};{DUMMY_MODEL}'",
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
    reg_args += ("--model-name", DUMMY_MODEL)

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
    assert "custom_label" in registry[DUMMY_MODEL]

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
    # Add some additional entries (to have something to remove)
    labels = (
        f"{TEST_LABEL}_foo",
        f"{TEST_LABEL}_bar",
        f"{TEST_LABEL}_spam",
    )
    for label in labels:
        reg_args = (
            "models",
            "register",
            "single",
            DUMMY_MODEL,
            "-e",
            DUMMY_EXECUTABLE,
        )
        reg_args += ("--label", label)
        reg_args += ("--source-dir", "./")

        res = invoke_cli(reg_args)
        print(res.output)
        assert res.exit_code == 0

    # Remove a single label
    res = invoke_cli(("models", "rm", DUMMY_MODEL, "--label", labels[0]))
    assert res.exit_code == 0
    assert TEST_LABEL in registry[DUMMY_MODEL]
    assert labels[0] not in registry[DUMMY_MODEL]
    assert labels[1] in registry[DUMMY_MODEL]
    assert labels[2] in registry[DUMMY_MODEL]

    # ... with prompt for bundle name
    res = invoke_cli(("models", "rm", DUMMY_MODEL), input=f"{labels[1]}\n")
    assert res.exit_code == 0
    assert TEST_LABEL in registry[DUMMY_MODEL]
    assert labels[0] not in registry[DUMMY_MODEL]
    assert labels[1] not in registry[DUMMY_MODEL]
    assert labels[2] in registry[DUMMY_MODEL]

    # Now remove it completely
    res = invoke_cli(("models", "rm", DUMMY_MODEL, "--all"), input="N\n")
    print(res.output)
    assert res.exit_code == 0
    assert "Not removing anything" in res.output

    res = invoke_cli(("models", "rm", DUMMY_MODEL, "--all"), input="y\n")
    print(res.output)
    assert res.exit_code == 0
    assert DUMMY_MODEL not in registry


def test_set_default(registry):
    """Tests utopya models set-default"""
    assert registry[DUMMY_MODEL].default_label == TEST_LABEL

    # Unset default and re-set via CLI
    registry[DUMMY_MODEL].default_label = None
    res = invoke_cli(("models", "set-default", DUMMY_MODEL, TEST_LABEL))
    print(res.output)
    assert res.exit_code == 0
    assert TEST_LABEL in res.output
    assert registry[DUMMY_MODEL].default_label == TEST_LABEL

    # Fails for invalid label name, keeping the old default
    assert "invalid_label" not in registry[DUMMY_MODEL]
    res = invoke_cli(("models", "set-default", DUMMY_MODEL, "invalid_label"))
    print(res.output)
    assert res.exit_code != 0
    assert "invalid_label" in res.output
    assert registry[DUMMY_MODEL].default_label == TEST_LABEL


def test_edit(monkeypatch, with_test_models):
    """Tests utopya models edit"""
    res = invoke_cli(("models", "edit", DUMMY_MODEL), input="y\n")
    print(res.output)
    assert res.exit_code == 1
    assert "Editing model registry file failed!" in res.output

    monkeypatch.setenv("EDITOR", "echo")  # this will always work
    res = invoke_cli(("models", "edit", DUMMY_MODEL), input="y\n")
    print(res.output)
    assert res.exit_code == 0
    assert "Successfully edited registry file" in res.output

    # Not continuing
    res = invoke_cli(("models", "edit", DUMMY_MODEL), input="N\n")
    print(res.output)
    assert res.exit_code == 0
    assert "Not opening" in res.output


@pytest.mark.skip("NotImplemented")
def test_copy():
    """Tests utopya models copy"""
    new_model_args = ("--new-name", "foo", "--target-project", "bar")
    res = invoke_cli(("models", "copy", DUMMY_MODEL) + new_model_args)
    assert res.exit_code == 0
