"""The utopya package implements a versatile simulation runner and manager"""

__version__ = "1.0.0a6"
"""The utopya package version"""

# .. Logging ..................................................................
# TODO Consider setting up logging elsewhere -- but needs to be done first!
from dantro.logging import REMARK as _DEFAULT_LOG_LEVEL
from dantro.logging import getLogger as _getLogger

_log = _getLogger(__name__)

# Add colour logging to the root logger
# See API reference:  https://coloredlogs.readthedocs.io/en/latest/api.html
import coloredlogs as _coloredlogs

_coloredlogs.install(
    logger=_log,
    level=_DEFAULT_LOG_LEVEL,
    fmt="%(levelname)-8s %(module)-16s  %(message)s",
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

# .. The most important part of the utopya interface ..........................

from .eval import DataManager, MultiverseGroup, UniverseGroup
from .model import Model
from .model_registry import MODELS
from .multiverse import FrozenMultiverse, Multiverse
from .project_registry import PROJECTS
from .testtools import ModelTest
