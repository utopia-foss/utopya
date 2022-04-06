"""Tests the internal _import_tools module"""

import copy
import os
import sys

import pytest

import utopya.cfg as ucfg
from utopya.cfg import write_to_cfg_dir

# Fixtures --------------------------------------------------------------------
from .test_cfg import tmp_cfg_dir


@pytest.fixture
def tmp_sys_path():
    """Work on a temporary sys.path"""
    initial_sys_path = copy.deepcopy(sys.path)
    yield

    sys.path = initial_sys_path


# -----------------------------------------------------------------------------


@pytest.mark.skip(reason="needs implementation")
def test_temporary_sys_path():
    pass


@pytest.mark.skip(reason="needs implementation")
def test_temporary_modules_cache():
    pass


@pytest.mark.skip(reason="needs implementation")
def test_import_module_from_path():
    pass
