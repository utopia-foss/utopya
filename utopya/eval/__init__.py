"""Implements a dantro-based simulation data evaluation pipeline."""

from dantro.plot_creators import is_plot_func

from .datamanager import DataManager
from .groups import MultiverseGroup, UniverseGroup
from .plotmanager import PlotManager
from .transform import register_operation
