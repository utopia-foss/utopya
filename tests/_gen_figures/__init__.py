"""A module that implements python functions that generate figures which
are embedded into the documentation.
These are implemented as pytests to allow using the fixtures defined throughout
the utopya test suite.

NOTE Test function names should ideally be unique within this subpackage!

     This is because this test module is run from within the sphinx build
     routine (see doc/conf.py) and sets ``UTOPYA_ABBREVIATE_TEST_OUTPUT_DIR``,
     thus potentially allowing to overwrite files from other tests if the
     test functions have the same name.
"""
