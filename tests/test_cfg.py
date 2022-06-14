"""Test the cfg module"""

import os

import pytest

import utopya.cfg as ucfg

from ._fixtures import tmp_cfg_dir

# Fixtures --------------------------------------------------------------------


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
