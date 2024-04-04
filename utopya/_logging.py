"""Sets up logging, based on dantro's logging features"""

import os

import coloredlogs as _coloredlogs
from dantro.logging import REMARK as _DEFAULT_LOG_LEVEL
from dantro.logging import getLogger as _getLogger

_log = _getLogger("utopya")
"""The utopya root logger"""

_DEFAULT_LOG_FORMAT = "%(levelname)-8s %(module)-16s  %(message)s"
"""The default logging format"""

# Add colour logging to the root logger
# See API reference:  https://coloredlogs.readthedocs.io/en/latest/api.html
_coloredlogs.install(
    logger=_log,
    level=_DEFAULT_LOG_LEVEL,
    fmt=_DEFAULT_LOG_FORMAT,
    level_styles=dict(
        trace=dict(faint=True),
        debug=dict(faint=True),
        remark=dict(color=246),  # grey
        note=dict(color="cyan"),
        info=dict(bright=True),
        progress=dict(color="green"),
        caution=dict(color=202),  # orange
        hilight=dict(color="yellow", bold=True),
        success=dict(color="green", bold=True),
        warning=dict(color=202, bold=True),  # orange
        error=dict(color="red"),
        critical=dict(color="red", bold=True),
    ),
    field_styles=dict(
        levelname=dict(bold=True, faint=True), module=dict(faint=True)
    ),
)
_log.debug("Logging configured.")
