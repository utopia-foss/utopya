"""Test the project_registry submodule"""

import pytest

from utopya.cfg import UTOPYA_CFG_SUBDIRS
from utopya.project_registry import PROJECTS, Project, ProjectRegistry

from . import DEMO_DIR, TEST_PROJECT_NAME
from ._fixtures import *

# Fixtures --------------------------------------------------------------------


@pytest.fixture(autouse=True)
def with_models(with_test_models):
    """Use on all tests in this module"""
    pass


@pytest.fixture
def project() -> Project:
    from utopya import PROJECTS

    return PROJECTS[TEST_PROJECT_NAME]


# Project object --------------------------------------------------------------


def test_Project(project, tmpdir):
    """Tests the Project object, akin to a RegistryEntry"""
    prj = project

    assert prj.project_name == TEST_PROJECT_NAME

    # TODO more here


def test_Project_framework(project):
    """Tests framework project association"""
    prj = project

    assert prj.project_name == TEST_PROJECT_NAME
    assert prj.framework_name is None
    assert prj.framework_project is None

    # Assign itself as framework
    prj.framework_name = TEST_PROJECT_NAME
    assert prj.framework_name == TEST_PROJECT_NAME
    assert prj.framework_project.project_name == TEST_PROJECT_NAME


def test_Project_git_info(project):
    """Tests git information retrieval"""
    prj = project

    info = prj.get_git_info()
    print(info)

    assert isinstance(info, dict)
    assert info["project_base_dir"] == str(prj.paths.base_dir)
    assert info["project_name"] == prj.project_name
    assert info["dirty"] == "unknown"
    assert info["git_status"] == []
    assert info["git_diff"] == ""
    assert info["have_git_repo"]  # because the demo project is part of utopya
    assert info["latest_commit"] is not None
    assert info["latest_commit"]["gitdir"].endswith("utopya/.git")

    # Now include patch info
    info = prj.get_git_info(include_patch_info=True)
    print(info)

    assert isinstance(info["dirty"], bool)
    assert isinstance(info["git_status"], list)
    assert isinstance(info["git_diff"], str)


# ProjectRegistry -------------------------------------------------------------


def test_ProjectRegistry(tmpdir):
    """Tests features specific to the ProjectRegistry."""

    assert PROJECTS.registry_dir == UTOPYA_CFG_SUBDIRS["projects"]

    # With a custom projects subdirectory, will create the folder
    reg_dir = tmpdir.join("my_reg_dir")
    assert not reg_dir.exists()
    pr = ProjectRegistry(reg_dir)
    assert reg_dir.isdir()


def test_ProjectRegistry_register(tmpdir):
    """Tests ProjectRegistry.register method"""
    pr = ProjectRegistry(tmpdir)

    # Have no projects, of course
    assert len(pr) == 0

    # Register the demo project
    pr.register(base_dir=DEMO_DIR)
    assert len(pr) == 1
    assert "utopyaDemoProject" in pr

    # And again with a custom name
    pr.register(base_dir=DEMO_DIR, custom_project_name=TEST_PROJECT_NAME)
    assert len(pr) == 2
    assert TEST_PROJECT_NAME in pr

    # Can test if names are matching
    pr.register(
        base_dir=DEMO_DIR,
        custom_project_name="utopyaDemoProject",
        require_matching_names=True,
        exists_action="overwrite",
    )
    assert len(pr) == 2

    with pytest.raises(ValueError, match="does not match"):
        pr.register(
            base_dir=DEMO_DIR,
            custom_project_name="some other name",
            require_matching_names=True,
        )
    assert len(pr) == 2

    # Can pass the demo file explicitly, relative or absolute path
    pr.register(
        base_dir=DEMO_DIR,
        info_file=".utopya-project.yml",
        custom_project_name="demo2",
    )

    pr.register(
        base_dir=DEMO_DIR,
        info_file=os.path.join(DEMO_DIR, ".utopya-project.yml"),
        custom_project_name="demo3",
    )

    # Directory without project info file
    with pytest.raises(ValueError, match="Missing project info file!"):
        pr.register(base_dir=os.path.join(DEMO_DIR, "some bad path"))
