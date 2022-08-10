"""**DEPRECATED** module that provides backwards-compatibility for the old
utopya module structure.

.. deprecated:: 1.0.0

    This module will be removed soon, please use :py:mod:`utopya.eval` instead.
"""
import warnings

from .eval import MultiverseGroup, PlotManager, UniverseGroup
from .eval.plotcreators import MultiversePlotCreator, UniversePlotCreator
from .eval.plothelper import PlotHelper
from .eval.plots import is_plot_func
from .eval.transform import register_operation

warnings.warn(
    "The utopya.plotting module has been deprecated and will be removed. "
    "Please adapt your imports to use the utopya.eval module instead.",
    DeprecationWarning,
)
