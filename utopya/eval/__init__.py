"""Implements a dantro-based simulation data evaluation pipeline."""

from dantro.plot_creators import is_plot_func

from .containers import GridDC, NumpyDC, XarrayDC, XarrayYamlDC
from .datamanager import DataManager
from .groups import MultiverseGroup, UniverseGroup
from .plotcreators import MultiversePlotCreator, UniversePlotCreator
from .plothelper import PlotHelper
from .plotmanager import PlotManager
from .transform import register_operation
