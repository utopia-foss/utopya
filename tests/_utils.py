"""Test utilities, fixtures, ..."""

import os

import pytest

import utopya.cfg as ucfg
import utopya.model_registry as umr

from . import DEMO_DIR, DEMO_PROJECT_NAME


@pytest.fixture
def tmp_cfg_dir(tmpdir):
    """Adjust the config directory and paths to be something temporary and
    clean it up again afterwards...

    .. note::

        This does NOT change the already loaded models and project registry!
    """
    # Store the old ones
    old_cfg_dir = ucfg.UTOPYA_CFG_DIR
    old_cfg_file_paths = ucfg.UTOPYA_CFG_FILE_PATHS

    # Place a temporary one
    ucfg.UTOPYA_CFG_DIR = str(tmpdir)
    ucfg.UTOPYA_CFG_FILE_PATHS = {
        k: os.path.join(ucfg.UTOPYA_CFG_DIR, fname)
        for k, fname in ucfg.UTOPYA_CFG_FILE_NAMES.items()
    }
    yield str(tmpdir)

    # Teardown code: reinstate the old paths
    ucfg.UTOPYA_CFG_DIR = old_cfg_dir
    ucfg.UTOPYA_CFG_FILE_PATHS = old_cfg_file_paths


@pytest.fixture
def tmp_model_registry(tmp_cfg_dir) -> umr._ModelRegistry:
    """A temporary model registry"""
    return umr._ModelRegistry(tmp_cfg_dir)


@pytest.fixture
def tmp_projects(tmp_cfg_dir):
    """A "temporary" projects registry that adds the demo project to it and
    removes it again at fixture teardown"""
    from utopya import PROJECTS

    original_project_names = list(PROJECTS)

    PROJECTS.register(base_dir=DEMO_DIR, exists_action="raise")
    assert DEMO_PROJECT_NAME in PROJECTS
    yield

    # Make sure no projects added by the test remain in the registry
    new_project_names = [
        name for name in PROJECTS if name not in original_project_names
    ]
    for project_name in new_project_names:
        PROJECTS.remove_entry(project_name)
