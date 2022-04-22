"""Test the cfg module"""

import os

import pytest

import utopya.cfg as ucfg

# Fixtures --------------------------------------------------------------------


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


# -----------------------------------------------------------------------------


def test_cfg(tmp_cfg_dir):
    """Test whether reading and writing to the config directory work as
    expected.
    """

    # There should be nothing in that directory, thus reading should return
    # empty dicts
    assert ucfg.load_from_cfg_dir("user") == dict()

    # Now, write something and make sure it was written
    ucfg.write_to_cfg_dir("user", dict(foo="bar"))
    assert ucfg.load_from_cfg_dir("user") == dict(foo="bar")

    # Writing again overwrites the existing entry
    ucfg.write_to_cfg_dir("user", dict(spam="spam"))
    assert ucfg.load_from_cfg_dir("user") == dict(spam="spam")

    # Error messages
    with pytest.raises(ValueError, match="invalid"):
        ucfg.load_from_cfg_dir("invalid")
