#!/usr/bin/python3
"""This is a custom entrypoint to pytest which takes care that pytest is
run within the ``if __name__ == '__main__'`` guard, thereby resolving issues
with the multiprocessing module.

We are not the only ones with this problem, see:
    - https://github.com/pytest-dev/pytest/issues/958
    - https://github.com/web-platform-tests/wpt/issues/24880
"""

import os
import sys

import pytest

# Ensure that the root directory of the utopya packages are in the path and
# utopya is already imported at this point.
# If not doing this, discovery of the utopya modules may fail if the test
# modules are imported when *spawning* a new multiprocessing.Process ...
sys.path.insert(0, os.path.dirname(__file__))

import dantro
import dantro.logging

# Import packages for which re-imports should be avoided or which need to be
# imported early to avoid errors from partial imports.
import numpy

# NOTE Do not import utopya here as this hinders measuring test coverage

# Set an invalid EDITOR variable
os.environ["EDITOR"] = "mock-editor"

if __name__ == "__main__":
    sys.exit(pytest.main([__file__] + sys.argv[1:]))
