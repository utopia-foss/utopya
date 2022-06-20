"""The plot_funcs subpackage supplies general plotting functions.

These can be used via the plotting framework and its ExternalPlotCreator, of
which this subpackage is the base package to use for relative module imports.

It extends those capabilities provided by the dantro plotting framework.
"""

from dantro.plot import is_plot_func

from ..plotcreators import MultiversePlotCreator, UniversePlotCreator
from ..plothelper import PlotHelper
