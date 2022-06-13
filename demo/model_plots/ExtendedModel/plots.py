"""Model-specific plot function definitions"""

import logging

import numpy as np
import xarray as xr

from utopya.eval import PlotHelper, is_plot_func

log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


@is_plot_func(use_dag=True, required_dag_tags=("data_to_plot",))
def my_custom_plot_function(
    *,
    data: dict,
    hlpr: PlotHelper,
    **plot_kwargs,
):
    """An example plot function implementation that uses the dantro data
    transformation framework for data selection and preprocessing.
    """
    data_to_plot = data["data_to_plot"]

    hlpr.ax.plot(data_to_plot, **plot_kwargs)
