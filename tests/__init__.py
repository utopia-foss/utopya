"""utopya test suite"""

import logging
import os
import uuid

from pkg_resources import resource_filename

# Set default log level to DEBUG
logging.basicConfig(level=logging.DEBUG)

# Silence some modules that are too verbose
logging.getLogger("matplotlib").setLevel(logging.INFO)
logging.getLogger("paramspace").setLevel(logging.INFO)

logging.getLogger("utopya.task").setLevel(logging.INFO)
logging.getLogger("utopya.reporter").setLevel(logging.INFO)

# -- Shared utilities or definitions ------------------------------------------
# .. Function defintions ......................................................

get_cfg_fpath = lambda filename: resource_filename("tests", f"cfg/{filename}")
"""Simplifies importing config files used in tests"""


def _str2bool(val: str) -> bool:
    """Copy of strtobool from deprecated distutils package"""
    val = val.lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return True
    elif val in ("n", "no", "f", "false", "off", "0"):
        return False
    raise ValueError(f"Invalid truth value {repr(val)}!")


# .. Model names and directory paths ..........................................
DUMMY_MODEL = "MinimalModel"
"""Dummy model to use for testing basic functionality"""

ADVANCED_MODEL = "ExtendedModel"
"""Model to use for testing advanced functionality"""

DEMO_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), "../demo"))
"""Directory the demo models are located in"""

TEST_PROJECT_NAME = f"_utopyaTestProject_{uuid.uuid4().hex}"
"""Name of the test project used throughout these tests"""

TEST_LABEL = f"_test_label_{uuid.uuid4().hex}"
"""A label to use for testing temporarily registered models"""


# .. Test-related variables ...................................................

TEST_VERBOSITY: int = int(os.environ.get("UTOPYA_TEST_VERBOSITY", 2))
"""A verbosity-controlling value. This can be interpreted in various ways by
the individual tests, but 0 should mean very low verbosity and 3 should be the
maximum verbosity."""

USE_TEST_OUTPUT_DIR: bool = _str2bool(
    os.environ.get("UTOPYA_USE_TEST_OUTPUT_DIR", "false")
)
"""Whether to use the test output directory. Can be set via the environment
variable ``UTOPYA_USE_TEST_OUTPUT_DIR``.

NOTE It depends on the tests if they actually take this flag into account!
     If using the ``tmpdir_or_local_dir`` fixture, this will be used to decide
     whether to return a tmpdir or a path within ``TEST_OUTPUT_DIR``.
"""

ABBREVIATE_TEST_OUTPUT_DIR: bool = _str2bool(
    os.environ.get("UTOPYA_ABBREVIATE_TEST_OUTPUT_DIR", "false")
)
"""If true, will use shorter directory names within the output directory, not
including test module names for instance. This is used for figure generation
as part of the documentation."""

TEST_OUTPUT_DIR: str = os.path.join(os.path.dirname(__file__), "_output")
"""An output directory that *can* be used to locally store data, e.g. for
looking at plot output. By default, this will be in the ``tests`` directory
itself, but if the ``UTOPYA_TEST_OUTPUT_DIR`` environment variable is set, will
use that path instead.
"""

if os.environ.get("UTOPYA_TEST_OUTPUT_DIR"):
    TEST_OUTPUT_DIR = os.environ["UTOPYA_TEST_OUTPUT_DIR"]
    print(
        "Using test output directory set from environment variable:\n"
        f"  {TEST_OUTPUT_DIR}\n"
    )
