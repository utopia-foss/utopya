"""Tests deprecations

NOTE This test should be carried out first and there should not be any imports
     here on the test module level, otherwise the deprecations will already
     have been emitted.
"""
import pytest

# -----------------------------------------------------------------------------


def test_utopya_import_tools_deprecation():
    """Makes sure that importing utopya._import_tools raises a warning"""
    with pytest.deprecated_call():
        import utopya._import_tools


def test_utopya_plotting_deprecation():
    """Makes sure that importing utopya.plotting raises a warning"""
    with pytest.deprecated_call():
        import utopya.plotting
