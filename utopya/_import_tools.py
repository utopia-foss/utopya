"""Helper module that contains tools useful for module imports or manipulation
of the system path.
These are not implemented here but in :py:mod:`dantro._import_tools`.

.. deprecated:: 1.0.1

    This module is deprecated. Use :py:mod:`dantro._import_tools` or
    :py:func:`utopya_backend.tools.import_package_from_dir` instead.
"""

import warnings

from dantro._import_tools import *

warnings.warn(
    "The utopya._import_tools module has been deprecated and will be removed. "
    "Have a look at `dantro._import_tools` for alternatives. You can also use "
    "the `utopya_backend.tools.import_package_from_dir` function to import "
    "a locally accessible package.",
    DeprecationWarning,
)
