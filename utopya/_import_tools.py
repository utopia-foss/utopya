"""Helper module that contains tools useful for module imports or manipulation
of the system path.
These are not implemented here but in :py:mod:`dantro._import_tools`.

.. deprecated:: 1.0.1

    This module is deprecated. Use :py:mod:`dantro._import_tools` instead.

"""

import warnings

from dantro._import_tools import *

warnings.warn(
    "The utopya._import_tools module has been deprecated and will be removed. "
    "If you really need to, use dantro._import_tools instead.",
    DeprecationWarning,
)
# TODO Update this and docstring in case utopya_backend includes a tool
