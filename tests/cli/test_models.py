"""Tests the utopya models <...> subcommands of the CLI"""

import os
import pickle
import traceback
from shutil import rmtree

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

    # Workaround for side effects of DUMMY_MODEL persisting beyond a single
    # invocation, thus leading to test failures for repeated test calls.
    res = invoke_cli(("models", "rm", DUMMY_MODEL, "--all"), input="y\n")

    # Get path to directory
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


def test_copy(registry):
    """Tests utopya models copy"""
    cmd = ("models", "copy", ADVANCED_MODEL)
    shared_args = ("--dry-run", "--yes")
    COPIED_MODEL_NAME = f"_CopyTest_{ADVANCED_MODEL}"

    # Simple invocation with all parameters given
    args = (
        "--new-name",
        COPIED_MODEL_NAME,
        "--target-project",
        TEST_PROJECT_NAME,
    )
    res = invoke_cli(cmd + args + shared_args)
    assert res.exit_code == 0

    # Can disable postprocessing
    res = invoke_cli(cmd + args + shared_args + ("--no-pp",))
    assert res.exit_code == 0
    assert "Post-processing routines were disabled." in res.output

    # And may not be getting a prompt
    res = invoke_cli(cmd + args + ("--dry-run",))
    assert res.exit_code == 0

    # Can pass file extensions to skip, which may also lead to empty file maps
    res = invoke_cli(cmd + args + shared_args + ("--skip-exts", "pyc py .yml"))
    print(res.output)
    assert res.exit_code == 0
    assert ".pyc .py .yml" in res.output
    assert "check the file extensions" in res.output
    assert "No files found to copy!" in res.output  # ... as all are ignored

    # Informs about py_tests_dir or py_plots_dir not being defined
    res = invoke_cli(("models", "copy", DUMMY_MODEL) + args + shared_args)
    print(res.output, res.exception)
    assert res.exit_code == 0
    assert "do not define a 'py_tests_dir'" in res.output
    assert "do not define a 'py_plots_dir'" in res.output

    # .. Actually copy ........................................................
    model = registry[ADVANCED_MODEL].item()
    prj = model.project

    try:
        res = invoke_cli(cmd + args + ("--yes",))
        print(res.output)
        assert "Copying failed" not in res.output
        assert res.exit_code == 0

        # And do it again, which should trigger writing errors
        res = invoke_cli(cmd + args + ("--yes",))
        print(res.output)
        assert "Copying failed with FileExistsError" in res.output
        assert res.exit_code == 0

        # Copying error will also raise
        res = invoke_cli(cmd + args + ("--yes", "--debug"))
        print(res.output)
        assert res.exit_code != 0

        # File name replacements were carried out
        model_dir = os.path.join(prj.paths["models_dir"], COPIED_MODEL_NAME)
        cfg_file = os.path.join(model_dir, f"{COPIED_MODEL_NAME}_cfg.yml")
        assert os.path.isfile(cfg_file)

        # Replacements took place
        info_file = os.path.join(model_dir, f"{COPIED_MODEL_NAME}_info.yml")
        assert os.path.isfile(info_file)
        with open(info_file) as f:
            info_file = f.read()

        print(info_file)
        assert f"model_name: {COPIED_MODEL_NAME}" in info_file

        # .. Postprocessing . . . . . . . . . . . . . . . . . . . . . . . . . .
        cml_root = os.path.join(prj.paths["models_dir"], "CMakeLists.txt")
        cml_model = os.path.join(
            prj.paths["models_dir"], ADVANCED_MODEL, "CMakeLists.txt"
        )

        # With a CMakeLists.txt file in the file map, should trigger automatic
        # postprocessing ... regardless of content
        with open(cml_model, "w") as f:
            f.write("")

        res = invoke_cli(cmd + args + shared_args)
        print(res.output)
        assert "No CMakeLists.txt file found in expected loc" in res.output
        assert res.exit_code == 0

        # With the root file existing, extending it is attempted, but the
        # add_subdirectory command is missing.
        with open(cml_root, "w") as f:
            f.write("\n")

        res = invoke_cli(cmd + args + shared_args)
        print(res.output)
        assert "inserting at the end" in res.output
        assert "preview of how the new" in res.output
        assert res.exit_code == 0

        # Now with some add_subdirectory commands existing
        with open(cml_root, "a") as f:
            f.write("\n")
            f.write("# Some comment\n")
            f.write(f"add_subdirectory(__i_should_be_first__)\n")
            f.write(f"add_subdirectory({ADVANCED_MODEL})\n")
            f.write(f"add_subdirectory({DUMMY_MODEL})\n")
            f.write("\n")
            f.write("# More content here\n")
            f.write("\n")
            f.write("# End of file\n")

        res = invoke_cli(cmd + args + ("--yes",))
        print(res.output)
        assert res.exit_code == 0

        # ... the location is correct
        with open(cml_root, "r") as f:
            print("Written file:")
            f = f.read()
            print(f)
            assert f.find(COPIED_MODEL_NAME) > f.find("__i_should_be_first__")
            assert f.find(COPIED_MODEL_NAME) < f.find(ADVANCED_MODEL)
            assert f.find(COPIED_MODEL_NAME) < f.find(DUMMY_MODEL)
            assert f.find(COPIED_MODEL_NAME) < f.find("End of file")

        # Insert behind the last add_subdirectory command
        with open(cml_root, "w") as f:
            f.write("\n")
            f.write("# Some comment\n")
            f.write(f"add_subdirectory(__i_should_be_first__)\n")
            f.write("\n")
            f.write("# End of file\n")

        res = invoke_cli(cmd + args + ("--yes",))
        print(res.output)
        assert res.exit_code == 0

        with open(cml_root, "r") as f:
            print("Written file:")
            f = f.read()
            print(f)
            assert f.find(COPIED_MODEL_NAME) > f.find("__i_should_be_first__")
            assert f.find(COPIED_MODEL_NAME) < f.find("End of file")

    finally:
        # Remove artifacts
        rmtree(os.path.join(prj.paths["models_dir"], COPIED_MODEL_NAME))
        rmtree(os.path.join(prj.paths["py_tests_dir"], COPIED_MODEL_NAME))
        rmtree(os.path.join(prj.paths["py_plots_dir"], COPIED_MODEL_NAME))
        os.remove(cml_model)
        os.remove(cml_root)

    # .. Errors ...............................................................
    # Provoke a reading error by adding a binary file
    bad_file = os.path.join(prj.paths["models_dir"], ADVANCED_MODEL, "so_bad")
    try:
        with open(bad_file, mode="wb") as f:
            pickle.dump("some object", f)

        res = invoke_cli(cmd + args + shared_args)
        print(res.output)
        assert "Reading failed" in res.output
        assert res.exit_code == 0

        res = invoke_cli(cmd + args + shared_args + ("--debug",))
        print(res.output)
        assert "Reading failed" in res.output
        assert res.exit_code != 0

    finally:
        os.remove(bad_file)

    # Existing model name throws an error
    args = (
        "--new-name",
        ADVANCED_MODEL,  # already exists, of course
        "--target-project",
        TEST_PROJECT_NAME,
    )
    res = invoke_cli(cmd + args + shared_args)
    assert res.exit_code == 1
