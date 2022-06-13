"""utopya test suite"""

import logging
import os
import uuid

# Set default log level to DEBUG
logging.basicConfig(level=logging.DEBUG)

# Silence some modules that are too verbose
logging.getLogger("matplotlib").setLevel(logging.INFO)
logging.getLogger("paramspace").setLevel(logging.INFO)

logging.getLogger("utopya.task").setLevel(logging.INFO)
logging.getLogger("utopya.reporter").setLevel(logging.INFO)

# -- Shared utilities or definitions ------------------------------------------
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

# Simplify importing config files used in tests
from pkg_resources import resource_filename

get_cfg_fpath = lambda filename: resource_filename("tests", f"cfg/{filename}")
