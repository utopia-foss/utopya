"""The utopya package implements the frontend of Utopia"""

# Specify the version
__version__ = "1.0.0a2"

# Use the dantro-provided logging module (with additional log levels)
from dantro.logging import REMARK as DEFAULT_LOG_LEVEL
from dantro.logging import getLogger as _getLogger

log = _getLogger(__name__)

# Add colour logging to the root logger
# See API reference:  https://coloredlogs.readthedocs.io/en/latest/api.html
import coloredlogs as _coloredlogs

_coloredlogs.install(
    logger=log,
    level=DEFAULT_LOG_LEVEL,
    fmt="%(levelname)-8s %(module)-15s %(message)s",
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
log.debug("Logging configured.")

# -- The most frequently used objects -----------------------------------------

from .eval import DataManager, MultiverseGroup, UniverseGroup
from .model import Model
from .model_registry import MODELS
from .multiverse import FrozenMultiverse, Multiverse
