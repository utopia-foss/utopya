"""Tests the utopya_backend.tools module"""

import os

import pytest
from dantro._import_tools import get_resource_path

import utopya_backend.tools as t

# -----------------------------------------------------------------------------


def test_load_cfg_file(tmpdir):
    """Tests the generic config file loading function"""
    # Attempts to load files (which are not there, of course)
    with pytest.raises(FileNotFoundError):
        t.load_cfg_file(tmpdir.join("some_file.yml"))
    with pytest.raises(FileNotFoundError):
        t.load_cfg_file(tmpdir.join("some_file.yaml"))
    with pytest.raises(FileNotFoundError):
        t.load_cfg_file(tmpdir.join("some_file.yAmL"))

    # Can also explicitly specify a loader
    with pytest.raises(FileNotFoundError):
        t.load_cfg_file(tmpdir.join("some_file.foobar"), loader="yaml")

    # Otherwise will get an earlier error due to a unsupported load format
    with pytest.raises(ValueError, match="Unsupported loader"):
        t.load_cfg_file(tmpdir.join("some_file.foobar"))

    # Can also load an actual file
    fpath = get_resource_path("utopya", "cfg/base_cfg.yml")
    cfg = t.load_cfg_file(fpath)
    assert "parameter_space" in cfg

    cfg = t.load_cfg_file(fpath, loader="yAmL")
    assert "parameter_space" in cfg


def test_import_package_from_dir(tmpdir):
    """Tests the path-based import function"""
    # Import the backend testing module right here
    mod_path = os.path.dirname(__file__)
    mod = t.import_package_from_dir(mod_path)
    assert mod.__file__.endswith("backend/__init__.py")

    # Can also specify a module string:
    mod2 = t.import_package_from_dir(mod_path, mod_str="backend")
    assert mod2 == mod

    # Can also import from higher-up, without needing to adjust the directory
    mod3 = t.import_package_from_dir(mod_path, mod_str="tests.backend")
    assert mod3.__file__.endswith("backend/__init__.py")

    # Is robust against trailing slash
    mod4 = t.import_package_from_dir(mod_path + "/", mod_str="tests.backend")
    assert mod4.__file__.endswith("backend/__init__.py")

    # Path needs to be absolute
    with pytest.raises(ValueError, match="Need an absolute path"):
        t.import_package_from_dir("some/relative/path")

    # Path needs to point to an existing *directory*
    with pytest.raises(FileNotFoundError, match="existing directory"):
        t.import_package_from_dir(__file__)

    # Path needs to point to an *existing* directory
    with pytest.raises(FileNotFoundError, match="existing directory"):
        t.import_package_from_dir("~/some/imaginary/directory")

    # Mock failing import
    mod_path = tmpdir.join("my_test_module")
    os.makedirs(mod_path)
    with open(mod_path.join("__init__.py"), "x") as f:
        f.write("raise\n")

    with pytest.raises(ImportError, match="Failed importing module 'my_test_"):
        t.import_package_from_dir(mod_path)
