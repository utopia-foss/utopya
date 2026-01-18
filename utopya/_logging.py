"""Sets up logging, based on dantro's logging features"""

import logging

import coloredlogs as _coloredlogs
from dantro.logging import REMARK as _DEFAULT_LOG_LEVEL
from dantro.logging import getLogger as _getLogger

# -----------------------------------------------------------------------------
# Set up a custom LogRecord factory that adds the `shortname` attribute to the
# log record directly. This ensures ALL log records have the `shortname`,
# regardless of which handler processes them (making things much easier with
# other packages, e.g. compatibility with pytest's log capturing) ...

_original_LogRecordFactory = logging.getLogRecordFactory()


def _utopya_LogRecordFactory(*args, **kwargs):
    """Custom log record factory.

    When building the log record object, adds ``shortname`` in addition.
    """
    record = _original_LogRecordFactory(*args, **kwargs)
    record.shortname = (
        record.name.split(".")[-1] if "." in record.name else record.name
    )
    return record


logging.setLogRecordFactory(_utopya_LogRecordFactory)

# -- Logger Setup -------------------------------------------------------------

_log = _getLogger("utopya")
"""The utopya root logger"""

# Add colour logging to the utopya logger
# See API reference:  https://coloredlogs.readthedocs.io/en/latest/api.html
_coloredlogs.install(
    logger=_log,
    level=_DEFAULT_LOG_LEVEL,
    fmt="%(levelname)-8s %(shortname)-16s  %(message)s",
    level_styles=dict(
        trace=dict(faint=True),
        debug=dict(faint=True),
        remark=dict(color=246),  # grey
        note=dict(color="cyan"),
        info=dict(bright=True),
        ping=dict(color="yellow", bright=True),
        progress=dict(color="green"),
        caution=dict(color=202),  # orange
        hilight=dict(color="yellow", bold=True),
        success=dict(color="green", bold=True),
        warning=dict(color=202, bold=True),  # orange
        error=dict(color="red"),
        critical=dict(color="red", bold=True),
    ),
    field_styles=dict(
        levelname=dict(bold=True, faint=True),
        module=dict(faint=True),
        name=dict(faint=True),
        shortname=dict(faint=True),
    ),
)

_log.debug("Logging configured.")
