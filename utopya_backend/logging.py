"""Implements logging-related infrastructure"""

import logging as _logging
from typing import Dict

# -----------------------------------------------------------------------------

LOG_LEVELS: Dict[str, int] = {
    "trace": 5,
    "debug": _logging.DEBUG,
    "info": _logging.INFO,
    "warn": _logging.WARN,
    "warning": _logging.WARNING,
    "error": _logging.ERROR,
    "critical": _logging.CRITICAL,
    "fatal": _logging.FATAL,
    "not_set": _logging.NOTSET,
    "notset": _logging.NOTSET,
    "none": _logging.NOTSET,
}
"""A map of log level names to actual level values"""

# TODO add trace level and other intermediate levels?

DEFAULT_LOG_FORMAT = "%(levelname)-7s %(message)s"
"""The default logging format to use; can also include ``%(name)-14s`` here to
show the logger's name."""

_logging.basicConfig(
    format=DEFAULT_LOG_FORMAT,
    level=LOG_LEVELS["info"],
)

backend_logger = _logging.getLogger()
"""A backend-wide logger instance which is the same as the root logger.

.. note::

    The :py:class:`~utopya_backend.model.base.BaseModel` may adjust the level
    of this logger.
"""

# -----------------------------------------------------------------------------


def get_level(s: str) -> int:
    """Returns the integer log level from a string, looking it up in
    :py:data:`~utopya_backend.logging.LOG_LEVELS`.

    Args:
        s (str): Name of the log level, not case-sensitive.

    Returns:
        int: The desired log level
    """
    return LOG_LEVELS[s.lower()]
