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

    # May also be None, in which case an empty dict is returned as well
    ucfg.write_to_cfg_dir("user", None)
    assert ucfg.load_from_cfg_dir("user") == dict()

    # Error messages
    with pytest.raises(ValueError, match="invalid"):
        ucfg.load_from_cfg_dir("invalid")
