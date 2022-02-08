"""DEPRECATED module that provides backwards-compatibility for the old utopya
module structure.

.. deprecated:: 1.0.0
"""

from .eval import MultiverseGroup, PlotManager, UniverseGroup
from .eval.plotcreators import MultiversePlotCreator, UniversePlotCreator
from .eval.plothelper import PlotHelper
from .eval.plots import is_plot_func
from .eval.transform import register_operation
