"""The :py:mod:`utopya` package provides a simulation management and
evaluation framework with the following components:

.. default-domain:: utopya

- A registry framework for models (:py:mod:`.model_registry`)
  and projects (:py:class:`~.project_registry.ProjectRegistry`)
- A configuration manager and simulation runner,
  the :py:class:`~.multiverse.Multiverse`:

  - Contains a multi-level configuration interface
  - Parallel simulation execution via
    :py:class:`~.workermanager.WorkerManager`.
  - A :py:mod:`parameter validation framework <.parameter>`

- Coupling to the :py:mod:`dantro` data evaluation pipeline, integrated via
  :py:mod:`utopya.eval`:

  - Custom data :py:mod:`groups <.eval.groups>`
    and :py:mod:`containers <.eval.containers>`
  - A :py:class:`.eval.plotmanager.PlotManager` that takes into account
    project- or model-specific plot function definitions.

- The :py:class:`.model.Model` abstraction which allows convenient interactive work with utopya and registered models.

  - The :py:class:`.testtools.ModelTest` class, containing specializations
    that make it more convenient to implement model tests using utopya.

- Batch simulation running and evaluation via :py:mod:`.batch`

For a real-world example of how utopya can be integrated, have a look at the
`Utopia modelling framework <https://utopia-project.org>`_ which uses
utopya as its frontend.
For model implementations, the :py:mod:`utopya_backend` package can assist in building Python-based models that use :py:mod:`utopya` as a frontend.

Also visit :ref:`the user manual front page <welcome>` for more information.
"""

__version__ = "1.1.0b1"
"""The :py:mod:`utopya` package version"""

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

from .eval import DataManager, MultiverseGroup, PlotManager, UniverseGroup
from .model import Model
from .model_registry import MODELS
from .multiverse import FrozenMultiverse, Multiverse
from .project_registry import PROJECTS
from .testtools import ModelTest
