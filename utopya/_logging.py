"""Sets up logging, based on dantro's logging features"""

import logging

import coloredlogs as _coloredlogs
from dantro.logging import REMARK as _DEFAULT_LOG_LEVEL
from dantro.logging import getLogger as _getLogger

# -----------------------------------------------------------------------------


class ShortNameFilter(logging.Filter):
    """A logging filter that adds the ``shortname`` attribute with just the
    module name to the logging record.

    This allows the log format to show, for example, 'multiverse' instead of
    'utopya.multiverse'.
    """

    def filter(self, record):
        record.shortname = (
            record.name.split(".")[-1] if "." in record.name else record.name
        )
        return True


# -- Logger Setup -------------------------------------------------------------

_log = _getLogger("utopya")
"""The utopya root logger"""

# Add colour logging to the root logger
# See API reference:  https://coloredlogs.readthedocs.io/en/latest/api.html
_coloredlogs.install(
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

# Also install the filter on (existing) handlers; need to do this as some
# handlers (of other modules) are already set up and may thus lack the filter.
_shortname_filter = ShortNameFilter()
for handler in logging.root.handlers:
    handler.addFilter(_shortname_filter)

_log.debug("Logging configured.")
