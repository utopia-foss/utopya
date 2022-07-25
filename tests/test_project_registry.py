"""Test the project_registry submodule"""

import pytest

from utopya.project_registry import Project, ProjectRegistry

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


def test_Project(project):
    """Tests the Project object, akin to a RegistryEntry"""
    prj = project

    assert prj.project_name == TEST_PROJECT_NAME

    # TODO more here


def test_Project_git_info(project):
    """Tests git information retrieval"""
    prj = project

    info = prj.get_git_info()
    print(info)

    assert isinstance(info, dict)
    assert info["project_base_dir"] == str(prj.paths.base_dir)
    assert info["project_name"] == prj.project_name
    assert info["dirty"] == "unknown"
    assert info["have_git_info"]  # because the demo project is part of utopya
    assert info["latest_commit"] is not None
    assert info["latest_commit"]["gitdir"].endswith("utopya/.git")


# ProjectRegistry -------------------------------------------------------------
