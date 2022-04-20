"""Tests the utopya projects <...> subcommands of the CLI"""

import os

import pytest

import utopya
from utopya._projects import load_projects

from .. import DEMO_DIR, DEMO_PROJECT_NAME, get_cfg_fpath
from ..test_model_registry import tmp_cfg_dir, tmp_projects
from . import invoke_cli

VALID_INFO_FILE = get_cfg_fpath("project_info.yml")
INVALID_INFO_FILE = get_cfg_fpath("project_info_invalid.yml")

# -----------------------------------------------------------------------------


def test_list(tmp_projects):
    """Tests utopya projects ls"""
    # Lists projects as expected
    res = invoke_cli(("projects", "ls"))
    assert "Utopya Projects" in res.output
    assert DEMO_PROJECT_NAME in res.output

    # Long mode shows additional info
    res = invoke_cli(("projects", "ls", "--long"))
    print(res.output)
    assert "metadata" in res.output
    assert "paths" in res.output

    assert res.output == invoke_cli(("projects", "ls", "-l")).output


def test_edit(tmp_projects, monkeypatch):
    """Tests utopya projects edit"""
    res = invoke_cli(("projects", "edit"), input="y\n")
    assert res.exit_code == 1
    assert "Editing projects registry file failed!" in res.output  # bad editor

    monkeypatch.setenv("EDITOR", "echo")  # this will always work
    res = invoke_cli(("projects", "edit"), input="y\n")
    assert res.exit_code == 0
    assert "Successfully edited projects registry file" in res.output

    # Not continuing
    res = invoke_cli(("projects", "edit"), input="N\n")
    assert res.exit_code == 0
    assert "Not opening" in res.output


def test_remove(tmp_projects):
    """Tests utopya projects rm"""
    # Do not confirm
    res = invoke_cli(("projects", "rm", DEMO_PROJECT_NAME), input="N\n")
    assert "Not removing" in res.output
    assert res.exit_code == 0

    # Skip confirmation but project name missing
    assert "missingProjectName" not in load_projects()
    res = invoke_cli(("projects", "rm", "missingProjectName", "-y"))
    assert res.exit_code != 0
    assert "no project named 'missingProjectName'" in res.output
    assert "missingProjectName" not in load_projects()

    # Now remove it
    assert DEMO_PROJECT_NAME in load_projects()
    res = invoke_cli(("projects", "rm", "utopyaDemoProject", "-y"))
    assert res.exit_code == 0
    assert "utopyaDemoProject" not in load_projects()


def test_register(tmp_projects):
    """Tests utopya project register"""
    from utopya._projects import register_project

    assert DEMO_PROJECT_NAME in load_projects()

    reg_args = ("projects", "register", DEMO_DIR)

    # Can invoke again, despite existing entry: Will validate by default
    res = invoke_cli(reg_args)
    print(res.output)
    assert res.exit_code == 0
    assert "Validating" in res.output
    assert (
        f"Validation of project '{DEMO_PROJECT_NAME}' succeeded" in res.output
    )

    # Explicitly pass path to (same) info file
    res = invoke_cli(
        reg_args
        + ("--info-file", os.path.join(DEMO_DIR, ".utopya_project.yml"))
    )
    print(res.output)
    assert res.exit_code == 0
    assert "Validating" in res.output

    # Explicitly pass exists_action
    res = invoke_cli(reg_args + ("--exists-action", "validate"))
    print(res.output)
    assert res.exit_code == 0

    # exists_action: raise
    res = invoke_cli(reg_args + ("--exists-action", "raise"))
    print(res.output)
    assert res.exit_code != 0
    assert "already exists" in res.output

    # exists_action: overwrite
    res = invoke_cli(reg_args + ("--exists-action", "overwrite"))
    print(res.output)
    assert res.exit_code == 0
    assert "Overwriting" in res.output

    # exists_action: update
    res = invoke_cli(reg_args + ("--exists-action", "update"))
    print(res.output)
    assert res.exit_code == 0
    assert "Updating" in res.output

    # Invalid exists_action
    res = invoke_cli(reg_args + ("--exists-action", "bad_exists_action"))
    print(res.output)
    assert res.exit_code == 2  # error comes from click
    assert "bad_exists_action" in res.output

    with pytest.raises(ValueError, match="Invalid `exists_action`"):
        register_project(base_dir=DEMO_DIR, exists_action="bad_exists_action")

    # Store under custom name
    res = invoke_cli(reg_args + ("--custom-name", "some_custom_name"))
    print(res.output)
    assert res.exit_code == 0
    assert f"Successfully stored 'some_custom_name'" in res.output

    # Name needs to match
    res = invoke_cli(
        reg_args
        + ("--custom-name", "some_custom_name", "--require-matching-names")
    )
    print(res.output)
    assert res.exit_code != 0
    assert f"does not match the name given in the project info" in res.output

    # Missing info file
    res = invoke_cli(("projects", "register", os.path.join(DEMO_DIR, "../")))
    print(res.output)
    assert res.exit_code != 0

    # --- Use different files to test overwriting, updating, validating
    # Validation failure
    res = invoke_cli(
        reg_args
        + ("--info-file", VALID_INFO_FILE, "--custom-name", DEMO_PROJECT_NAME)
    )
    print(res.output)
    assert res.exit_code != 0
    assert "Validating" in res.output
    assert "their diff is as follows" in res.output

    # ... old info is still there
    project = load_projects()[DEMO_PROJECT_NAME]
    assert "A demo project" in project["metadata"]["description"]

    # Overwrite ...
    res = invoke_cli(
        reg_args
        + (
            "--info-file",
            VALID_INFO_FILE,
            "--custom-name",
            DEMO_PROJECT_NAME,
            "--exists-action",
            "overwrite",
        )
    )
    print(res.output)
    assert res.exit_code == 0
    assert "Overwriting" in res.output
    assert f"Successfully stored" in res.output

    # ... have new info there
    project = load_projects()[DEMO_PROJECT_NAME]
    assert "A TEST project" in project["metadata"]["description"]

    # Update ...
    # TODO

    # ... have updated info there now
    # TODO

    # Loading a file with bad syntax will fail
    res = invoke_cli(reg_args + ("--info-file", INVALID_INFO_FILE))
    print(res.output)
    assert res.exit_code != 0
    assert "Failed loading" in res.output
    assert "unexpected keys" in res.output
